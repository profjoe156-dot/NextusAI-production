import logging

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes

from app.bot.keyboards import chat_menu
from app.bot.utils import chunks, escape
from app.repositories.users import UserRepository
from app.services.ai import AIProviderError
from app.services.chat import ChatService, QuotaExceededError, UserBlockedError
from app.services.rate_limit import RateLimitExceeded

logger = logging.getLogger(__name__)


async def enter_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if context.user_data is not None:
        context.user_data["chat_mode"] = True
    await query.edit_message_text(
        (
            "<b>AI Chat</b>\n\nSend any question or task. "
            "NexusAI remembers the recent context in this conversation."
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=chat_menu(),
    )


async def new_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return
    query = update.callback_query
    if query:
        await query.answer("New conversation started")
    database = context.application.bot_data["database"]
    async with database.sessions() as session:
        user = await UserRepository(session).get_by_telegram_id(update.effective_user.id)
        if user:
            service = ChatService(
                session,
                context.application.bot_data["cache"].client,
                context.application.bot_data["settings"],
                context.application.bot_data["ai_provider"],
            )
            await service.reset(user)
    if context.user_data is not None:
        context.user_data["chat_mode"] = True
    if update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="A fresh conversation is ready. What would you like to explore?",
            reply_markup=chat_menu(),
        )


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if (
        not update.effective_user
        or not update.effective_message
        or not update.effective_message.text
    ):
        return
    if context.user_data is None or not context.user_data.get("chat_mode"):
        await update.effective_message.reply_text(
            "Open <b>AI Chat</b> from /menu before sending a question.",
            parse_mode=ParseMode.HTML,
        )
        return

    if update.effective_chat:
        await update.effective_chat.send_action(ChatAction.TYPING)
    database = context.application.bot_data["database"]
    async with database.sessions() as session:
        user = await UserRepository(session).get_by_telegram_id(update.effective_user.id)
        if not user:
            await update.effective_message.reply_text("Use /start to register first.")
            return
        service = ChatService(
            session,
            context.application.bot_data["cache"].client,
            context.application.bot_data["settings"],
            context.application.bot_data["ai_provider"],
        )
        try:
            result = await service.reply(user, update.effective_message.text)
        except RateLimitExceeded as exc:
            await update.effective_message.reply_text(
                f"You're sending messages too quickly. Try again in {exc.retry_after} seconds."
            )
            return
        except QuotaExceededError as exc:
            await update.effective_message.reply_text(
                f"Your daily allowance of {exc.limit} AI messages is used. "
                "Open Premium from /menu for a higher limit."
            )
            return
        except UserBlockedError:
            await update.effective_message.reply_text("This account is currently restricted.")
            return
        except (ValueError, AIProviderError):
            logger.exception(
                "AI chat request failed", extra={"telegram_id": update.effective_user.id}
            )
            await update.effective_message.reply_text(
                "I couldn't complete that request. Check the message length and try again."
            )
            return

    safe_text = escape(result.content)
    response_parts = chunks(safe_text)
    for index, part in enumerate(response_parts):
        await update.effective_message.reply_text(
            part,
            parse_mode=ParseMode.HTML,
            reply_markup=chat_menu() if index == len(response_parts) - 1 else None,
            disable_web_page_preview=True,
        )
