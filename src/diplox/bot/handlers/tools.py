"""Handlers for Diplox tools: outline, grammar, rewrite, summarize, sources."""

import html
import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from diplox.bot.formatters import format_error, format_llm_response, truncate_html
from diplox.bot.keyboards import (
    get_cancel_keyboard,
    get_rewrite_mode_keyboard,
    get_summary_length_keyboard,
    get_tools_menu,
    get_work_type_keyboard,
    WORK_TYPES,
)
from diplox.bot.states import (
    GrammarState,
    OutlineState,
    RewriteState,
    SourcesState,
    SummarizeState,
)
from diplox.services.diplox_api import DiploxAPI

router = Router(name="tools")
logger = logging.getLogger(__name__)

_WORK_TYPE_LABELS = {wt_id: label for wt_id, label in WORK_TYPES}


# ── Cancel ───────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "cancel_tool")
async def cancel_tool(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Отменено")
    await callback.message.edit_text(
        "🎓 <b>Инструменты</b>\n\nВыбери инструмент:",
        reply_markup=get_tools_menu(),
    )


@router.callback_query(lambda c: c.data == "back_tools")
async def back_to_tools(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "🎓 <b>Инструменты</b>\n\nВыбери инструмент:",
        reply_markup=get_tools_menu(),
    )


# ══════════════════════════════════════════════════════════════
# 1. OUTLINE — генерация плана работы
# ══════════════════════════════════════════════════════════════

@router.callback_query(lambda c: c.data == "tool_outline")
async def outline_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "📑 <b>План работы</b>\n\nВыбери тип работы:",
        reply_markup=get_work_type_keyboard("outline"),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("outline_wt_"))
async def outline_work_type_selected(callback: CallbackQuery, state: FSMContext) -> None:
    work_type = callback.data.replace("outline_wt_", "")
    await callback.answer()
    await state.set_state(OutlineState.waiting_for_topic)
    await state.update_data(outline_work_type=work_type)
    label = _WORK_TYPE_LABELS.get(work_type, work_type)
    await callback.message.edit_text(
        f"📑 <b>План работы</b> — {label}\n\n"
        "Введи тему работы.\n"
        "<i>Можно добавить предмет через дефис: Тема — Предмет</i>",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(OutlineState.waiting_for_topic)
async def outline_topic_input(
    message: Message,
    state: FSMContext,
    diplox_api: DiploxAPI,
) -> None:
    text = message.text
    if not text or len(text) < 5:
        await message.answer("❌ Тема слишком короткая (минимум 5 символов)")
        return

    data = await state.get_data()
    work_type = data.get("outline_work_type", "kursovaya")
    await state.clear()

    # Parse "topic — subject" format
    subject = None
    if " — " in text:
        parts = text.split(" — ", 1)
        text, subject = parts[0].strip(), parts[1].strip()
    elif " - " in text:
        parts = text.split(" - ", 1)
        text, subject = parts[0].strip(), parts[1].strip()

    status_msg = await message.answer("⏳ Генерирую план...")

    try:
        outline = await diplox_api.generate_outline(text, work_type, subject)
        formatted = format_llm_response(outline)
        await status_msg.edit_text(f"📑 <b>План работы</b>\n\n{formatted}")
    except Exception as e:
        logger.exception("Outline generation failed")
        await status_msg.edit_text(format_error(str(e)))


# ══════════════════════════════════════════════════════════════
# 2. GRAMMAR — проверка грамматики
# ══════════════════════════════════════════════════════════════

@router.callback_query(lambda c: c.data == "tool_grammar")
async def grammar_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.set_state(GrammarState.waiting_for_text)
    await callback.message.edit_text(
        "✏️ <b>Проверка текста</b>\n\n"
        "Отправь текст для проверки грамматики и орфографии.\n"
        "<i>От 10 до 100 000 символов</i>",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(GrammarState.waiting_for_text)
async def grammar_text_input(
    message: Message,
    state: FSMContext,
    diplox_api: DiploxAPI,
) -> None:
    text = message.text
    if not text or len(text) < 10:
        await message.answer("❌ Текст слишком короткий (минимум 10 символов)")
        return

    await state.clear()
    status_msg = await message.answer("⏳ Проверяю текст...")

    try:
        result = await diplox_api.check_grammar(text)

        if result.total == 0:
            await status_msg.edit_text("✅ <b>Ошибок не найдено!</b>\n\nТекст выглядит хорошо.")
            return

        lines = [f"✏️ <b>Найдено ошибок: {result.total}</b>\n"]
        for i, m in enumerate(result.matches[:15], 1):
            line = f"<b>{i}.</b> {html.escape(m.message)}"
            if m.replacements:
                suggestions = ", ".join(html.escape(r) for r in m.replacements)
                line += f"\n   💡 <i>{suggestions}</i>"
            lines.append(line)

        if result.total > 15:
            lines.append(f"\n<i>...и ещё {result.total - 15} ошибок</i>")

        response = "\n\n".join(lines)
        await status_msg.edit_text(truncate_html(response, 4096))
    except Exception as e:
        logger.exception("Grammar check failed")
        await status_msg.edit_text(format_error(str(e)))


# ══════════════════════════════════════════════════════════════
# 3. REWRITE — рерайт текста
# ══════════════════════════════════════════════════════════════

@router.callback_query(lambda c: c.data == "tool_rewrite")
async def rewrite_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.set_state(RewriteState.waiting_for_text)
    await callback.message.edit_text(
        "🔄 <b>Рерайт текста</b>\n\n"
        "Отправь текст для повышения уникальности.\n"
        "<i>От 50 до 50 000 символов</i>",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(RewriteState.waiting_for_text)
async def rewrite_text_input(message: Message, state: FSMContext) -> None:
    text = message.text
    if not text or len(text) < 50:
        await message.answer("❌ Текст слишком короткий (минимум 50 символов)")
        return

    await state.update_data(rewrite_text=text)
    await state.set_state(None)  # Wait for mode selection via callback
    await message.answer(
        "🔄 <b>Выбери режим рерайта:</b>\n\n"
        "🟢 <b>Лёгкий</b> — замена синонимов\n"
        "🟡 <b>Средний</b> — перестройка предложений\n"
        "🔴 <b>Сильный</b> — полная переработка",
        reply_markup=get_rewrite_mode_keyboard(),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("rewrite_mode_"))
async def rewrite_mode_selected(
    callback: CallbackQuery,
    state: FSMContext,
    diplox_api: DiploxAPI,
) -> None:
    mode = callback.data.replace("rewrite_mode_", "")
    await callback.answer()

    data = await state.get_data()
    text = data.get("rewrite_text", "")
    await state.clear()

    if not text:
        await callback.message.edit_text("❌ Текст потерян. Попробуй заново.")
        return

    await callback.message.edit_text("⏳ Переписываю текст...")

    try:
        rewritten = await diplox_api.rewrite(text, mode)
        formatted = format_llm_response(rewritten)
        await callback.message.edit_text(f"🔄 <b>Рерайт ({mode})</b>\n\n{formatted}")
    except Exception as e:
        logger.exception("Rewrite failed")
        await callback.message.edit_text(format_error(str(e)))


# ══════════════════════════════════════════════════════════════
# 4. SUMMARIZE — аннотация / реферат
# ══════════════════════════════════════════════════════════════

@router.callback_query(lambda c: c.data == "tool_summarize")
async def summarize_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.set_state(SummarizeState.waiting_for_text)
    await callback.message.edit_text(
        "📄 <b>Аннотация / Реферат</b>\n\n"
        "Отправь текст для сжатия.\n"
        "<i>От 50 до 50 000 символов</i>",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(SummarizeState.waiting_for_text)
async def summarize_text_input(message: Message, state: FSMContext) -> None:
    text = message.text
    if not text or len(text) < 50:
        await message.answer("❌ Текст слишком короткий (минимум 50 символов)")
        return

    await state.update_data(summarize_text=text)
    await state.set_state(None)
    await message.answer(
        "📄 <b>Выбери длину аннотации:</b>\n\n"
        "📄 <b>Короткая</b> — 100-200 слов\n"
        "📃 <b>Средняя</b> — 300-500 слов\n"
        "📑 <b>Подробная</b> — 800-1000 слов",
        reply_markup=get_summary_length_keyboard(),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("summary_len_"))
async def summary_length_selected(
    callback: CallbackQuery,
    state: FSMContext,
    diplox_api: DiploxAPI,
) -> None:
    length = callback.data.replace("summary_len_", "")
    await callback.answer()

    data = await state.get_data()
    text = data.get("summarize_text", "")
    await state.clear()

    if not text:
        await callback.message.edit_text("❌ Текст потерян. Попробуй заново.")
        return

    await callback.message.edit_text("⏳ Создаю аннотацию...")

    try:
        summary = await diplox_api.summarize(text, length)
        formatted = format_llm_response(summary)
        await callback.message.edit_text(f"📄 <b>Аннотация ({length})</b>\n\n{formatted}")
    except Exception as e:
        logger.exception("Summarize failed")
        await callback.message.edit_text(format_error(str(e)))


# ══════════════════════════════════════════════════════════════
# 5. SOURCES — поиск литературы
# ══════════════════════════════════════════════════════════════

@router.callback_query(lambda c: c.data == "tool_sources")
async def sources_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "📚 <b>Поиск литературы</b>\n\nВыбери тип работы:",
        reply_markup=get_work_type_keyboard("sources"),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("sources_wt_"))
async def sources_work_type_selected(callback: CallbackQuery, state: FSMContext) -> None:
    work_type = callback.data.replace("sources_wt_", "")
    await callback.answer()
    await state.set_state(SourcesState.waiting_for_topic)
    await state.update_data(sources_work_type=work_type)
    label = _WORK_TYPE_LABELS.get(work_type, work_type)
    await callback.message.edit_text(
        f"📚 <b>Поиск литературы</b> — {label}\n\n"
        "Введи тему для поиска научных источников.",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(SourcesState.waiting_for_topic)
async def sources_topic_input(
    message: Message,
    state: FSMContext,
    diplox_api: DiploxAPI,
) -> None:
    text = message.text
    if not text or len(text) < 5:
        await message.answer("❌ Тема слишком короткая (минимум 5 символов)")
        return

    data = await state.get_data()
    work_type = data.get("sources_work_type", "kursovaya")
    await state.clear()

    status_msg = await message.answer("⏳ Ищу научные источники...")

    try:
        result = await diplox_api.find_sources(text, work_type, count=10)

        if result.total == 0:
            await status_msg.edit_text(
                "📚 <b>Источники не найдены</b>\n\n"
                "<i>Попробуй изменить формулировку темы.</i>"
            )
            return

        lines = [f"📚 <b>Найдено источников: {result.total}</b>\n"]
        for i, s in enumerate(result.sources[:10], 1):
            lines.append(f"{i}. {html.escape(s.formatted)}")

        response = "\n\n".join(lines)
        await status_msg.edit_text(truncate_html(response, 4096))
    except Exception as e:
        logger.exception("Sources search failed")
        await status_msg.edit_text(format_error(str(e)))


# ══════════════════════════════════════════════════════════════
# 6. FORMAT — ссылка на форматирование
# ══════════════════════════════════════════════════════════════

@router.callback_query(lambda c: c.data == "tool_format")
async def format_redirect(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "📐 <b>Форматирование по ГОСТу</b>\n\n"
        "Для форматирования документа загрузи его на сайт:\n"
        "👉 <a href=\"https://diplox.online/create\">diplox.online/create</a>\n\n"
        "<i>Как пользователь бота, форматирование для тебя бесплатно!</i>",
        reply_markup=get_tools_menu(),
    )
