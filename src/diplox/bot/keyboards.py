"""Keyboards for Telegram bot — reply menu + inline menus."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# ── Reply keyboard constants (button labels) ────────────────
BTN_TOOLS = "🎓 Инструменты"
BTN_AI = "🤖 AI-помощник"
BTN_NOTES = "📝 Мои заметки"
BTN_PROFILE = "📊 Профиль"

MENU_BUTTONS = {BTN_TOOLS, BTN_AI, BTN_NOTES, BTN_PROFILE}

# ── Work types for outline & sources ─────────────────────────
WORK_TYPES = [
    ("diplom", "🎓 Диплом"),
    ("kursovaya", "📘 Курсовая"),
    ("vkr", "🎓 ВКР"),
    ("magisterskaya", "🎓 Магистерская"),
    ("referat", "📝 Реферат"),
    ("esse", "✏️ Эссе"),
    ("otchet-po-praktike", "📋 Отчёт по практике"),
]

REWRITE_MODES = [
    ("light", "🟢 Лёгкий"),
    ("medium", "🟡 Средний"),
    ("heavy", "🔴 Сильный"),
]

SUMMARY_LENGTHS = [
    ("short", "📄 Короткая"),
    ("medium", "📃 Средняя"),
    ("detailed", "📑 Подробная"),
]


# ── Reply keyboard (always visible) ─────────────────────────

def get_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_TOOLS), KeyboardButton(text=BTN_AI)],
            [KeyboardButton(text=BTN_NOTES), KeyboardButton(text=BTN_PROFILE)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# ── Inline keyboards for sub-menus ──────────────────────────

def get_tools_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📑 План работы", callback_data="tool_outline")],
        [InlineKeyboardButton(text="✏️ Проверить текст", callback_data="tool_grammar")],
        [InlineKeyboardButton(text="🔄 Рерайт", callback_data="tool_rewrite")],
        [InlineKeyboardButton(text="📄 Аннотация", callback_data="tool_summarize")],
        [InlineKeyboardButton(text="📚 Найти литературу", callback_data="tool_sources")],
        [InlineKeyboardButton(text="📐 Форматирование", callback_data="tool_format")],
    ])


def get_ai_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="ai_ask")],
        [InlineKeyboardButton(text="✍️ Выполнить задание", callback_data="ai_do")],
        [InlineKeyboardButton(text="💬 Свободный чат", callback_data="ai_chat")],
    ])


def get_notes_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 За сегодня", callback_data="notes_today")],
        [InlineKeyboardButton(text="📅 За неделю", callback_data="notes_week")],
        [InlineKeyboardButton(text="🔄 Обработать день", callback_data="notes_process")],
    ])


def get_profile_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Статистика", callback_data="profile_stats")],
        [InlineKeyboardButton(text="🔗 Открыть Diplox", url="https://diplox.online")],
    ])


# ── Tool-specific keyboards ─────────────────────────────────

def get_work_type_keyboard(callback_prefix: str) -> InlineKeyboardMarkup:
    """Work type selector for outline/sources. callback_prefix: 'outline' or 'sources'."""
    rows = []
    for i in range(0, len(WORK_TYPES), 2):
        row = []
        for wt_id, wt_label in WORK_TYPES[i : i + 2]:
            row.append(InlineKeyboardButton(
                text=wt_label,
                callback_data=f"{callback_prefix}_wt_{wt_id}",
            ))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="back_tools")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_rewrite_mode_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for mode_id, mode_label in REWRITE_MODES:
        rows.append([InlineKeyboardButton(
            text=mode_label,
            callback_data=f"rewrite_mode_{mode_id}",
        )])
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="back_tools")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_summary_length_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for length_id, length_label in SUMMARY_LENGTHS:
        rows.append([InlineKeyboardButton(
            text=length_label,
            callback_data=f"summary_len_{length_id}",
        )])
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="back_tools")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_tool")],
    ])


# ── Existing ─────────────────────────────────────────────────

def get_followup_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Скорректировать", callback_data="do_followup")],
    ])
