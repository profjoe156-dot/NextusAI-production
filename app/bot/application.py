from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from app.bot.handlers.chat import enter_chat, new_conversation, text_message
from app.bot.handlers.common import (
    account_command,
    error_handler,
    help_command,
    home_callback,
    menu_command,
    post_init,
    start,
    unknown_command,
)
from app.bot.handlers.content import (
    news_menu,
    prompt_view,
    prompts_category,
    prompts_menu,
    tools_category,
    tools_menu,
)
from app.bot.handlers.membership import (
    buy_premium,
    precheckout,
    premium_view,
    referral_view,
    successful_payment,
)


def build_telegram_application(settings) -> Application:
    application = (
        Application.builder()
        .token(settings.telegram_bot_token.get_secret_value())
        .updater(None)
        .post_init(post_init)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("account", account_command))
    application.add_handler(CommandHandler("new", new_conversation))
    application.add_handler(CommandHandler("referral", referral_view))
    application.add_handler(CallbackQueryHandler(home_callback, pattern=r"^menu:home$"))
    application.add_handler(CallbackQueryHandler(enter_chat, pattern=r"^menu:chat$"))
    application.add_handler(CallbackQueryHandler(new_conversation, pattern=r"^chat:reset$"))
    application.add_handler(CallbackQueryHandler(tools_menu, pattern=r"^menu:tools$"))
    application.add_handler(CallbackQueryHandler(tools_category, pattern=r"^tools:category:"))
    application.add_handler(CallbackQueryHandler(news_menu, pattern=r"^menu:news$"))
    application.add_handler(CallbackQueryHandler(prompts_menu, pattern=r"^menu:prompts$"))
    application.add_handler(CallbackQueryHandler(prompts_category, pattern=r"^prompts:category:"))
    application.add_handler(CallbackQueryHandler(prompt_view, pattern=r"^prompt:view:"))
    application.add_handler(CallbackQueryHandler(premium_view, pattern=r"^menu:premium$"))
    application.add_handler(CallbackQueryHandler(referral_view, pattern=r"^menu:referrals$"))
    application.add_handler(CallbackQueryHandler(buy_premium, pattern=r"^premium:buy$"))
    application.add_handler(PreCheckoutQueryHandler(precheckout))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    application.add_error_handler(error_handler)
    return application
