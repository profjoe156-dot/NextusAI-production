import html

from telegram import Message

TELEGRAM_SAFE_LENGTH = 3900


def escape(value: str | None) -> str:
    return html.escape(value or "")


def chunks(text: str, size: int = TELEGRAM_SAFE_LENGTH) -> list[str]:
    if len(text) <= size:
        return [text]
    parts: list[str] = []
    remaining = text
    while remaining:
        split_at = remaining.rfind("\n", 0, size)
        if split_at < size // 2:
            split_at = size
        parts.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip("\n")
    return parts


async def send_long(message: Message, text: str, **kwargs) -> None:
    for index, part in enumerate(chunks(text)):
        await message.reply_text(part, **kwargs if index == len(chunks(text)) - 1 else {})
