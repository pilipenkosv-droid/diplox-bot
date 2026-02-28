"""Handler for reply keyboard menu buttons + inline menu navigation."""

import logging
from datetime import datetime, timezone

from aiogram import Router
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from diplox.bot.keyboards import (
    BTN_AI,
    BTN_NOTES,
    BTN_PROFILE,
    BTN_TOOLS,
    MENU_BUTTONS,
    get_ai_menu,
    get_notes_menu,
    get_profile_menu,
    get_tools_menu,
)
from diplox.services.database import Database
from diplox.services.user_context import UserContext

router = Router(name="menu")
logger = logging.getLogger(__name__)


class MenuButtonFilter(Filter):
    """Filter for reply keyboard button presses."""

    async def __call__(self, message: Message) -> bool:
        return bool(message.text and message.text in MENU_BUTTONS)


# ── Reply keyboard handlers ─────────────────────────────────

@router.message(MenuButtonFilter())
async def handle_menu_button(message: Message, state: FSMContext, user_ctx: UserContext, db: Database) -> None:
    # Clear any active FSM state when switching menus
    await state.clear()

    text = message.text

    if text == BTN_TOOLS:
        await message.answer(
            "🎓 <b>Инструменты</b>\n\nВыбери инструмент:",
            reply_markup=get_tools_menu(),
        )

    elif text == BTN_AI:
        await message.answer(
            "🤖 <b>AI-помощник</b>\n\nЧто хочешь сделать?",
            reply_markup=get_ai_menu(),
        )

    elif text == BTN_NOTES:
        await message.answer(
            "📝 <b>Мои заметки</b>\n\nВыбери период:",
            reply_markup=get_notes_menu(),
        )

    elif text == BTN_PROFILE:
        ask_used = await db.get_daily_usage_count(user_ctx.user_id, "ask")
        do_used = await db.get_daily_usage_count(user_ctx.user_id, "do")
        process_used = await db.get_daily_usage_count(user_ctx.user_id, "process")
        today = datetime.now(timezone.utc).strftime("%d.%m.%Y")

        await message.answer(
            f"📊 <b>Профиль — {user_ctx.name}</b>\n\n"
            f"📅 Дата: {today}\n\n"
            f"<b>Квота сегодня:</b>\n"
            f"• /ask: {ask_used}/20\n"
            f"• /do: {do_used}/10\n"
            f"• /process: {process_used}/2\n"
            f"• Инструменты: ♾ без ограничений\n\n"
            f"<i>Сохранение заметок — без ограничений</i>",
            reply_markup=get_profile_menu(),
        )


# ── Inline menu callbacks (AI section) ──────────────────────

@router.callback_query(lambda c: c.data == "ai_ask")
async def ai_ask_redirect(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "❓ <b>Задать вопрос</b>\n\n"
        "Отправь /ask и свой вопрос.\n"
        "Я поищу ответ в твоих заметках.\n\n"
        "<i>Пример: /ask Что такое дифференциальное уравнение?</i>"
    )


@router.callback_query(lambda c: c.data == "ai_do")
async def ai_do_redirect(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "✍️ <b>Выполнить задание</b>\n\n"
        "Отправь /do и описание задачи.\n\n"
        "<i>Пример: /do Напиши введение для курсовой по экономике</i>"
    )


# ── Profile callbacks ────────────────────────────────────────

@router.callback_query(lambda c: c.data == "profile_stats")
async def profile_stats(callback: CallbackQuery, user_ctx: UserContext, db: Database) -> None:
    await callback.answer()
    ask_used = await db.get_daily_usage_count(user_ctx.user_id, "ask")
    do_used = await db.get_daily_usage_count(user_ctx.user_id, "do")
    process_used = await db.get_daily_usage_count(user_ctx.user_id, "process")

    await callback.message.edit_text(
        f"📈 <b>Статистика — {user_ctx.name}</b>\n\n"
        f"<b>Использовано сегодня:</b>\n"
        f"• Вопросы: {ask_used}/20\n"
        f"• Задания: {do_used}/10\n"
        f"• Обработка дня: {process_used}/2\n"
        f"• Инструменты: ♾\n\n"
        f"<i>Квота обновляется ежедневно</i>",
        reply_markup=get_profile_menu(),
    )
