import uuid
from urllib.parse import urlparse

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.bot.keyboards import back_menu, category_menu
from app.bot.utils import escape
from app.models.entities import AITool, Prompt
from app.repositories.content import ContentRepository
from app.repositories.users import UserRepository


def _safe_url(url: str) -> str | None:
    parsed = urlparse(url)
    return url if parsed.scheme in {"http", "https"} and parsed.netloc else None


async def tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    database = context.application.bot_data["database"]
    async with database.sessions() as session:
        categories = await ContentRepository(session).categories(AITool)
    await query.edit_message_text(
        "<b>AI Tools Directory</b>\n\nBrowse a curated collection by category.",
        parse_mode=ParseMode.HTML,
        reply_markup=category_menu("tools", categories),
    )


async def tools_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    category = query.data.split(":", 2)[2]
    database = context.application.bot_data["database"]
    async with database.sessions() as session:
        tools = await ContentRepository(session).list_tools(category=category, limit=10)
    rows = []
    lines = [f"<b>{escape(category)} AI tools</b>", ""]
    for tool in tools:
        lines.append(
            f"<b>{escape(tool.name)}</b> — {escape(tool.pricing)}\n{escape(tool.description)}"
        )
        safe = _safe_url(tool.url)
        if safe:
            rows.append([InlineKeyboardButton(f"Open {tool.name}"[:40], url=safe)])
    if not tools:
        lines.append("No tools are available in this category yet.")
    rows.append([InlineKeyboardButton("All categories", callback_data="menu:tools")])
    rows.append([InlineKeyboardButton("Back to menu", callback_data="menu:home")])
    await query.edit_message_text(
        "\n\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(rows),
        disable_web_page_preview=True,
    )


async def prompts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()
    database = context.application.bot_data["database"]
    async with database.sessions() as session:
        categories = await ContentRepository(session).categories(Prompt)
    await query.edit_message_text(
        "<b>Prompt Library</b>\n\nChoose a category and copy a battle-tested prompt.",
        parse_mode=ParseMode.HTML,
        reply_markup=category_menu("prompts", categories),
    )


async def prompts_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return
    await query.answer()
    category = query.data.split(":", 2)[2]
    database = context.application.bot_data["database"]
    async with database.sessions() as session:
        user = await UserRepository(session).get_by_telegram_id(update.effective_user.id)
        prompts = await ContentRepository(session).list_prompts(
            category=category, include_premium=bool(user and user.is_premium), limit=12
        )
    rows = [
        [InlineKeyboardButton(prompt.title[:45], callback_data=f"prompt:view:{prompt.id}")]
        for prompt in prompts
    ]
    rows.extend(
        [
            [InlineKeyboardButton("All categories", callback_data="menu:prompts")],
            [InlineKeyboardButton("Back to menu", callback_data="menu:home")],
        ]
    )
    await query.edit_message_text(
        f"<b>{escape(category)} prompts</b>\n\nSelect a prompt to view and copy it.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def prompt_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return
    await query.answer()
    try:
        prompt_id = uuid.UUID(query.data.rsplit(":", 1)[1])
    except ValueError:
        await query.edit_message_text("That prompt link is invalid.", reply_markup=back_menu())
        return
    database = context.application.bot_data["database"]
    async with database.sessions() as session:
        prompt = await ContentRepository(session).get_prompt(prompt_id)
        user = await UserRepository(session).get_by_telegram_id(update.effective_user.id)
    if not prompt or not prompt.is_active:
        await query.edit_message_text(
            "That prompt is no longer available.", reply_markup=back_menu()
        )
        return
    if prompt.is_premium and not (user and user.is_premium):
        await query.edit_message_text(
            "This prompt is available to Premium members.", reply_markup=back_menu()
        )
        return
    await query.edit_message_text(
        f"<b>{escape(prompt.title)}</b>\n\n{escape(prompt.description)}\n\n"
        f"<pre>{escape(prompt.content)}</pre>",
        parse_mode=ParseMode.HTML,
        reply_markup=back_menu(),
    )


async def news_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    database = context.application.bot_data["database"]
    async with database.sessions() as session:
        items = await ContentRepository(session).latest_news(limit=8)
    lines = ["<b>Latest AI News</b>", ""]
    rows = []
    for item in items:
        lines.append(
            f"<b>{escape(item.title)}</b>\n{escape(item.source_name)} · "
            f"{item.published_at.strftime('%Y-%m-%d')}"
        )
        safe = _safe_url(item.source_url)
        if safe:
            rows.append([InlineKeyboardButton(item.title[:45], url=safe)])
    if not items:
        lines.append("News is being refreshed. Please check again shortly.")
    rows.append([InlineKeyboardButton("Refresh", callback_data="menu:news")])
    rows.append([InlineKeyboardButton("Back to menu", callback_data="menu:home")])
    await query.edit_message_text(
        "\n\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(rows),
        disable_web_page_preview=True,
    )
