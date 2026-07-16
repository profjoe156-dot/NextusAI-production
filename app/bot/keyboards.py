from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("AI Chat", callback_data="menu:chat"),
                InlineKeyboardButton("AI Tools", callback_data="menu:tools"),
            ],
            [
                InlineKeyboardButton("AI News", callback_data="menu:news"),
                InlineKeyboardButton("Prompt Library", callback_data="menu:prompts"),
            ],
            [
                InlineKeyboardButton("Premium", callback_data="menu:premium"),
                InlineKeyboardButton("Referrals", callback_data="menu:referrals"),
            ],
            [InlineKeyboardButton("My Account", callback_data="menu:account")],
        ]
    )


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Back to menu", callback_data="menu:home")]])


def chat_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("New conversation", callback_data="chat:reset")],
            [InlineKeyboardButton("Exit chat", callback_data="menu:home")],
        ]
    )


def category_menu(prefix: str, categories: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(category, callback_data=f"{prefix}:category:{category}"[:64])]
        for category in categories[:12]
    ]
    rows.append([InlineKeyboardButton("Back to menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)
