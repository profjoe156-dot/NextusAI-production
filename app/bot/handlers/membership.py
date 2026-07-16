import secrets

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.bot.keyboards import back_menu
from app.bot.utils import escape
from app.repositories.users import UserRepository
from app.services.premium import PremiumService


async def referral_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return
    query = update.callback_query
    if query:
        await query.answer()
    elif not update.effective_chat:
        return
    database = context.application.bot_data["database"]
    async with database.sessions() as session:
        repo = UserRepository(session)
        user = await repo.get_by_telegram_id(update.effective_user.id)
        count = await repo.referral_count(user.id) if user else 0
    if not user:
        if query:
            await query.edit_message_text("Use /start to register first.")
        elif update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Use /start to register first.",
            )
        return
    bot_user = await context.bot.get_me()
    link = f"https://t.me/{bot_user.username}?start={user.referral_code}"
    text = (
        "<b>Invite friends to NexusAI</b>\n\n"
        "You receive <b>3 Premium days</b> when a new user joins through your link.\n\n"
        f"Successful referrals: {count}\n"
        f"Your link:\n<code>{escape(link)}</code>"
    )
    if query:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_menu())
    elif update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=back_menu(),
        )


async def premium_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()
    settings = context.application.bot_data["settings"]
    database = context.application.bot_data["database"]
    async with database.sessions() as session:
        user = await UserRepository(session).get_by_telegram_id(update.effective_user.id)
    status = "Active" if user and user.is_premium else "Free plan"
    rows = []
    if settings.telegram_payment_provider_token:
        rows.append([InlineKeyboardButton("Upgrade now", callback_data="premium:buy")])
    rows.append([InlineKeyboardButton("Back to menu", callback_data="menu:home")])
    await query.edit_message_text(
        "<b>NexusAI Premium</b>\n\n"
        f"Current status: <b>{status}</b>\n\n"
        f"• Up to {settings.premium_daily_messages} AI messages per day\n"
        "• Premium prompt library\n"
        "• Priority access to new tools\n"
        "• Referral bonus days\n\n"
        f"Price: {settings.premium_monthly_price_cents / 100:.2f} "
        f"{escape(settings.premium_currency)} / 30 days"
        + (
            ""
            if settings.telegram_payment_provider_token
            else (
                "\n\nPayment checkout is disabled until an administrator "
                "configures a provider token."
            )
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()
    settings = context.application.bot_data["settings"]
    provider = settings.telegram_payment_provider_token
    if not provider:
        await query.edit_message_text(
            "Payment checkout is not configured.", reply_markup=back_menu()
        )
        return
    payload = f"premium30:{update.effective_user.id}:{secrets.token_urlsafe(12)}"
    await context.bot.send_invoice(
        chat_id=update.effective_user.id,
        title="NexusAI Premium — 30 days",
        description="Premium prompts and a higher daily AI allowance.",
        payload=payload,
        provider_token=provider.get_secret_value(),
        currency=settings.premium_currency,
        prices=[LabeledPrice("Premium membership", settings.premium_monthly_price_cents)],
        start_parameter="nexusai-premium",
    )


async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.pre_checkout_query
    if not query:
        return
    valid = query.invoice_payload.startswith(f"premium30:{query.from_user.id}:")
    await query.answer(ok=valid, error_message=None if valid else "Invalid premium checkout.")


async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not message.successful_payment or not update.effective_user:
        return
    payment = message.successful_payment
    database = context.application.bot_data["database"]
    async with database.sessions() as session:
        user = await UserRepository(session).get_by_telegram_id(update.effective_user.id)
        if not user:
            await message.reply_text(
                "Payment received, but the account was not found. Contact support."
            )
            return
        reference = payment.telegram_payment_charge_id
        await PremiumService(session).activate(
            user=user,
            days=30,
            provider="telegram",
            provider_reference=reference,
            amount_cents=payment.total_amount,
            currency=payment.currency,
        )
        await session.commit()
    await message.reply_text(
        "<b>Premium activated</b>\n\nYour membership is active for 30 days.",
        parse_mode=ParseMode.HTML,
        reply_markup=back_menu(),
    )
