"""Handler for /do — arbitrary tasks using Claude Haiku with follow-up support."""

import logging

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from diplox.bot.formatters import format_error, format_llm_response
from diplox.bot.keyboards import get_followup_keyboard
from diplox.bot.states import DoCommandState
from diplox.config import get_settings
from diplox.services.database import Database
from diplox.services.search import build_vault_context
from diplox.services.transcription import DeepgramTranscriber
from diplox.services.user_context import UserContext, UserContextService
from diplox.services.llm import LLMRouter

router = Router(name="do")
logger = logging.getLogger(__name__)

_MAX_HISTORY_ENTRY = 3500
_MAX_HISTORY_LEN = 7


@router.message(Command("do"))
async def cmd_do(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    user_ctx: UserContext,
    user_ctx_service: UserContextService,
    llm_router: LLMRouter,
    db: Database,
) -> None:
    if command.args:
        raw = await process_request(
            message, command.args, user_ctx, user_ctx_service, llm_router, db
        )
        if raw:
            await state.update_data(
                do_history=[
                    {"role": "user", "content": command.args},
                    {"role": "assistant", "content": raw[:_MAX_HISTORY_ENTRY]},
                ]
            )
        return

    await state.set_state(DoCommandState.waiting_for_input)
    await message.answer(
        "🎯 <b>Что сделать?</b>\n\n"
        "Отправь голосовое или текстовое сообщение с запросом."
    )


@router.message(DoCommandState.waiting_for_input)
async def handle_do_input(
    message: Message,
    bot: Bot,
    state: FSMContext,
    user_ctx: UserContext,
    user_ctx_service: UserContextService,
    llm_router: LLMRouter,
    db: Database,
) -> None:
    await state.set_state(None)

    prompt = await _extract_prompt(message, bot)
    if not prompt:
        return

    raw = await process_request(message, prompt, user_ctx, user_ctx_service, llm_router, db)
    if raw:
        await state.update_data(
            do_history=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": raw[:_MAX_HISTORY_ENTRY]},
            ]
        )


@router.callback_query(lambda c: c.data == "do_followup")
async def handle_followup_button(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(DoCommandState.waiting_for_followup)
    await callback.message.answer(
        "✏️ <b>Что скорректировать?</b>\n\n"
        "Отправь текст или голосовое с уточнением."
    )


@router.message(DoCommandState.waiting_for_followup)
async def handle_followup_input(
    message: Message,
    bot: Bot,
    state: FSMContext,
    user_ctx: UserContext,
    user_ctx_service: UserContextService,
    llm_router: LLMRouter,
    db: Database,
) -> None:
    data = await state.get_data()
    history: list[dict[str, str]] = data.get("do_history", [])

    if not history:
        await state.clear()
        await message.answer("❌ Контекст потерян. Отправь запрос заново через /do")
        return

    await state.set_state(None)

    correction = await _extract_prompt(message, bot)
    if not correction:
        await state.set_state(DoCommandState.waiting_for_followup)
        return

    history.append({"role": "user", "content": correction})

    if len(history) > _MAX_HISTORY_LEN:
        history = [history[0]] + history[-(_MAX_HISTORY_LEN - 1):]

    raw = await process_request(
        message, correction, user_ctx, user_ctx_service, llm_router, db, history=history
    )
    if raw:
        history.append({"role": "assistant", "content": raw[:_MAX_HISTORY_ENTRY]})
        await state.update_data(do_history=history)


async def _extract_prompt(message: Message, bot: Bot) -> str | None:
    """Extract text from voice or text message."""
    if message.voice:
        await message.chat.do(action="typing")
        settings = get_settings()
        transcriber = DeepgramTranscriber(settings.deepgram_api_key)

        try:
            file = await bot.get_file(message.voice.file_id)
            if not file.file_path:
                await message.answer("❌ Не удалось скачать голосовое")
                return None
            file_bytes = await bot.download_file(file.file_path)
            if not file_bytes:
                await message.answer("❌ Не удалось скачать голосовое")
                return None
            prompt = await transcriber.transcribe(file_bytes.read())
        except Exception as e:
            logger.exception("Failed to transcribe voice for /do")
            await message.answer(f"❌ Не удалось транскрибировать: {e}")
            return None

        if not prompt:
            await message.answer("❌ Не удалось распознать речь")
            return None

        await message.answer(f"🎤 <i>{prompt}</i>")
        return prompt

    if message.text:
        return message.text

    await message.answer("❌ Отправь текст или голосовое сообщение")
    return None


async def process_request(
    message: Message,
    prompt: str,
    user_ctx: UserContext,
    user_ctx_service: UserContextService,
    llm_router: LLMRouter,
    db: Database,
    history: list[dict[str, str]] | None = None,
) -> str | None:
    """Process request with Claude Haiku. Returns raw response text."""
    # Check quota
    allowed, used, limit = await user_ctx_service.check_quota(user_ctx.user_id, "do")
    if not allowed:
        await message.answer(
            f"⏳ Дневной лимит /do исчерпан ({used}/{limit}).\n"
            "Попробуй завтра!"
        )
        return None

    status_msg = await message.answer("⏳ Выполняю...")

    try:
        vault_context = await build_vault_context(user_ctx.vault_path, max_chars=10_000)

        # Build effective prompt for follow-ups
        effective_history = None
        if history and len(history) > 1:
            effective_history = history[:-1]  # All except the current message

        response = await llm_router.do(prompt, vault_context, effective_history)

        await db.log_usage(
            user_ctx.user_id, "do",
            response.model, response.input_tokens, response.output_tokens, response.cost_usd,
        )

        formatted = format_llm_response(response.text)
        try:
            await status_msg.edit_text(formatted, reply_markup=get_followup_keyboard())
        except Exception:
            try:
                await status_msg.edit_text(
                    formatted, parse_mode=None, reply_markup=get_followup_keyboard()
                )
            except Exception:
                logger.exception("Failed to send /do response")

        return response.text

    except Exception as e:
        logger.exception("Error processing /do")
        await status_msg.edit_text(format_error(str(e)))
        return None
