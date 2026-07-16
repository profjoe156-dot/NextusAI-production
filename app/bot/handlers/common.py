import logging

from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.bot.keyboards import back_menu, main_menu
from app.bot.utils import escape
from app.core.config import Settings
from app.repositories.users import UserRepository
from app.services.users import UserService

logger = logging.getLogger(__name__)

WELCOME = (
    "<b>Welcome to NexusAI</b>\n\n"
    "Your intelligent workspace inside Telegram. Chat with AI, discover useful tools, "
    "follow important AI news, and reuse expert prompts from one clean menu.\n\n"
    "Choose an option below to begin."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    database = context.application.bot_data["database"]
    referral_code = context.args[0].strip().upper() if context.args else None
    async with database.sessions() as session:
        result = await UserService(session).register_or_update(
            telegram_id=update.effective_user.id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name,
            language_code=update.effective_user.language_code,
            referral_code=referral_code,
        )
    if context.user_data is not None:
        context.user_data["chat_mode"] = False
    referral_note = "\n\nYour referral was applied." if result.referral_applied else ""
    await update.effective_message.reply_text(
        WELCOME + referral_note,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data is not None:
        context.user_data["chat_mode"] = False
    if update.effective_message:
        await update.effective_message.reply_text(
            "<b>NexusAI menu</b>\n\nWhat would you like to do?",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(
            "<b>NexusAI commands</b>\n\n"
            "/start — register or restart\n"
            "/menu — open the main menu\n"
            "/new — start a fresh AI conversation\n"
            "/account — view your plan and usage\n"
            "/referral — get your invite link\n"
            "/help — show this guide",
            parse_mode=ParseMode.HTML,
            reply_markup=back_menu(),
        )


async def account_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    database = context.application.bot_data["database"]
    settings: Settings = context.application.bot_data["settings"]
    async with database.sessions() as session:
        user = await UserRepository(session).get_by_telegram_id(update.effective_user.id)
        if not user:
            await update.effective_message.reply_text("Use /start to register first.")
            return
        referrals = await UserRepository(session).referral_count(user.id)
    limit = settings.premium_daily_messages if user.is_premium else settings.free_daily_messages
    plan = "Premium" if user.is_premium else "Free"
    expiry = user.premium_until.strftime("%Y-%m-%d") if user.premium_until else "—"
    await update.effective_message.reply_text(
        f"<b>My account</b>\n\n"
        f"Name: {escape(user.first_name)}\n"
        f"Plan: <b>{plan}</b>\n"
        f"Daily AI allowance: {limit}\n"
        f"Premium until: {expiry}\n"
        f"Successful referrals: {referrals}\n"
        f"Referral code: <code>{user.referral_code}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=back_menu(),
    )


async def home_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if context.user_data is not None:
        context.user_data["chat_mode"] = False
    await query.edit_message_text(
        "<b>NexusAI menu</b>\n\nWhat would you like to do?",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(
            "I don't recognize that command. Open /menu to continue.", reply_markup=main_menu()
        )


async def post_init(application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Register and open NexusAI"),
            BotCommand("menu", "Open the main menu"),
            BotCommand("new", "Start a new AI conversation"),
            BotCommand("account", "View account and plan"),
            BotCommand("referral", "Get your referral link"),
            BotCommand("help", "Show help"),
        ]
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Telegram update failed", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Something went wrong. Please try again in a moment or open /menu."
            )
        except Exception:
            logger.exception("Could not send Telegram error response")
