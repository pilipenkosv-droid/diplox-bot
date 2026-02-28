"""Handler for notes viewing — today, week, process."""

import html
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiogram import Router
from aiogram.types import CallbackQuery

from diplox.bot.formatters import truncate_html
from diplox.bot.keyboards import get_notes_menu
from diplox.services.user_context import UserContext

router = Router(name="notes")
logger = logging.getLogger(__name__)


def _read_daily_file(vault_path: str, date: datetime) -> str | None:
    """Read a single daily file."""
    path = Path(vault_path) / "daily" / f"{date.strftime('%Y-%m-%d')}.md"
    if path.exists():
        content = path.read_text(encoding="utf-8").strip()
        return content if content else None
    return None


@router.callback_query(lambda c: c.data == "notes_today")
async def notes_today(callback: CallbackQuery, user_ctx: UserContext) -> None:
    await callback.answer()
    today = datetime.now(timezone.utc)
    content = _read_daily_file(user_ctx.vault_path, today)

    if not content:
        await callback.message.edit_text(
            "📋 <b>Заметки за сегодня</b>\n\n"
            "<i>Пока пусто. Отправь текст или голосовое — я сохраню.</i>",
            reply_markup=get_notes_menu(),
        )
        return

    # Truncate and show
    preview = html.escape(content[:3000])
    lines = preview.split("\n")
    formatted_lines = []
    for line in lines:
        if line.startswith("## "):
            formatted_lines.append(f"<b>{line[3:]}</b>")
        elif line.startswith("- "):
            formatted_lines.append(f"• {line[2:]}")
        else:
            formatted_lines.append(line)

    text = "\n".join(formatted_lines)
    await callback.message.edit_text(
        truncate_html(f"📋 <b>Заметки за {today.strftime('%d.%m.%Y')}</b>\n\n{text}", 4096),
        reply_markup=get_notes_menu(),
    )


@router.callback_query(lambda c: c.data == "notes_week")
async def notes_week(callback: CallbackQuery, user_ctx: UserContext) -> None:
    await callback.answer()
    today = datetime.now(timezone.utc)
    days_with_notes = []

    for i in range(7):
        date = today - timedelta(days=i)
        content = _read_daily_file(user_ctx.vault_path, date)
        if content:
            line_count = len(content.split("\n"))
            char_count = len(content)
            days_with_notes.append((date, line_count, char_count))

    if not days_with_notes:
        await callback.message.edit_text(
            "📅 <b>Заметки за неделю</b>\n\n"
            "<i>За последние 7 дней заметок нет.</i>",
            reply_markup=get_notes_menu(),
        )
        return

    lines = ["📅 <b>Заметки за неделю</b>\n"]
    for date, line_count, char_count in days_with_notes:
        day_label = date.strftime("%d.%m (%a)")
        lines.append(f"• <b>{day_label}</b> — {line_count} записей, {char_count} символов")

    total_entries = sum(lc for _, lc, _ in days_with_notes)
    lines.append(f"\n<i>Всего: {len(days_with_notes)} дней, {total_entries} записей</i>")

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=get_notes_menu(),
    )


@router.callback_query(lambda c: c.data == "notes_process")
async def notes_process_redirect(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "🔄 <b>Обработка дня</b>\n\n"
        "Отправь /process чтобы я проанализировал записи за сегодня:\n"
        "• Резюме дня\n"
        "• Ключевые концепции\n"
        "• Нерешённые вопросы\n"
        "• Рекомендации"
    )
