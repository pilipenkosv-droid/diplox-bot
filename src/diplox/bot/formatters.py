"""Report formatters for Telegram messages."""

import html
import re
from typing import Any

ALLOWED_TAGS = {"b", "i", "code", "pre", "a", "s", "u"}


def sanitize_telegram_html(text: str) -> str:
    """Sanitize HTML for Telegram, keeping only allowed tags."""
    if not text:
        return ""

    result = []
    i = 0
    while i < len(text):
        if text[i] == "<":
            tag_match = re.match(r"</?([a-zA-Z]+)(?:\s[^>]*)?>", text[i:])
            if tag_match:
                tag_name = tag_match.group(1).lower()
                if tag_name in ALLOWED_TAGS:
                    result.append(tag_match.group(0))
                    i += len(tag_match.group(0))
                    continue
                else:
                    result.append("&lt;")
                    i += 1
                    continue
            else:
                result.append("&lt;")
                i += 1
                continue
        elif text[i] == ">":
            result.append("&gt;")
            i += 1
        elif text[i] == "&":
            entity_match = re.match(r"&(amp|lt|gt|quot|#\d+|#x[0-9a-fA-F]+);", text[i:])
            if entity_match:
                result.append(entity_match.group(0))
                i += len(entity_match.group(0))
            else:
                result.append("&amp;")
                i += 1
        else:
            result.append(text[i])
            i += 1

    return "".join(result)


def validate_telegram_html(text: str) -> bool:
    """Validate that HTML tags are properly closed."""
    tag_stack = []
    tag_pattern = re.compile(r"<(/?)([a-zA-Z]+)(?:\s[^>]*)?>")

    for match in tag_pattern.finditer(text):
        is_closing = match.group(1) == "/"
        tag_name = match.group(2).lower()

        if tag_name not in ALLOWED_TAGS:
            continue

        if is_closing:
            if not tag_stack or tag_stack[-1] != tag_name:
                return False
            tag_stack.pop()
        else:
            tag_stack.append(tag_name)

    return len(tag_stack) == 0


def truncate_html(text: str, max_length: int = 4096) -> str:
    """Truncate HTML text while keeping tags balanced."""
    if len(text) <= max_length:
        return text

    cut_point = max_length - 50

    last_open = text.rfind("<", 0, cut_point)
    last_close = text.rfind(">", 0, cut_point)

    if last_open > last_close:
        cut_point = last_open

    truncated = text[:cut_point]

    tag_pattern = re.compile(r"<(/?)([a-zA-Z]+)(?:\s[^>]*)?>")
    open_tags = []

    for match in tag_pattern.finditer(truncated):
        is_closing = match.group(1) == "/"
        tag_name = match.group(2).lower()

        if tag_name not in ALLOWED_TAGS:
            continue

        if is_closing and open_tags and open_tags[-1] == tag_name:
            open_tags.pop()
        elif not is_closing:
            open_tags.append(tag_name)

    closing_tags = "".join(f"</{tag}>" for tag in reversed(open_tags))
    return truncated + "..." + closing_tags


def format_llm_response(text: str) -> str:
    """Format LLM response for Telegram HTML."""
    sanitized = sanitize_telegram_html(text)
    if not validate_telegram_html(sanitized):
        return html.escape(text)
    return truncate_html(sanitized, max_length=4096)


def format_error(error: str) -> str:
    return f"❌ <b>Ошибка:</b> {html.escape(error)}"


def format_empty_daily() -> str:
    return (
        "📭 <b>Нет записей для обработки</b>\n\n"
        "<i>Добавь голосовые сообщения или текст в течение дня</i>"
    )
