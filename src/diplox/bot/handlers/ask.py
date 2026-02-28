"""Handler for /ask — Q&A from vault using Gemini Flash."""

import logging

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from diplox.bot.formatters import format_error, format_llm_response
from diplox.bot.states import AskCommandState
from diplox.config import get_settings
from diplox.services.database import Database
from diplox.services.search import build_vault_context
from diplox.services.transcription import DeepgramTranscriber
from diplox.services.user_context import UserContext, UserContextService
from diplox.services.llm import LLMRouter

router = Router(name="ask")
logger = logging.getLogger(__name__)


@router.message(Command("ask"))
async def cmd_ask(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    user_ctx: UserContext,
    user_ctx_service: UserContextService,
    llm_router: LLMRouter,
    db: Database,
) -> None:
    if command.args:
        await process_ask(message, command.args, user_ctx, user_ctx_service, llm_router, db)
        return

    await state.set_state(AskCommandState.waiting_for_input)
    await message.answer(
        "❓ <b>Что хочешь узнать?</b>\n\n"
        "Отправь голосовое или текстовое сообщение с вопросом.\n"
        "<i>Я отвечу на основе твоих заметок.</i>"
    )


@router.message(AskCommandState.waiting_for_input)
async def handle_ask_input(
    message: Message,
    bot: Bot,
    state: FSMContext,
    user_ctx: UserContext,
    user_ctx_service: UserContextService,
    llm_router: LLMRouter,
    db: Database,
) -> None:
    await state.clear()

    question = None

    if message.voice:
        await message.chat.do(action="typing")
        settings = get_settings()
        transcriber = DeepgramTranscriber(settings.deepgram_api_key)

        try:
            file = await bot.get_file(message.voice.file_id)
            if not file.file_path:
                await message.answer("❌ Не удалось скачать голосовое")
                return
            file_bytes = await bot.download_file(file.file_path)
            if not file_bytes:
                await message.answer("❌ Не удалось скачать голосовое")
                return
            question = await transcriber.transcribe(file_bytes.read())
        except Exception as e:
            logger.exception("Failed to transcribe voice for /ask")
            await message.answer(f"❌ Не удалось транскрибировать: {e}")
            return

        if not question:
            await message.answer("❌ Не удалось распознать речь")
            return

        await message.answer(f"🎤 <i>{question}</i>")

    elif message.text:
        question = message.text
    else:
        await message.answer("❌ Отправь текст или голосовое сообщение")
        return

    await process_ask(message, question, user_ctx, user_ctx_service, llm_router, db)


async def process_ask(
    message: Message,
    question: str,
    user_ctx: UserContext,
    user_ctx_service: UserContextService,
    llm_router: LLMRouter,
    db: Database,
) -> None:
    # Check quota
    allowed, used, limit = await user_ctx_service.check_quota(user_ctx.user_id, "ask")
    if not allowed:
        await message.answer(
            f"⏳ Дневной лимит /ask исчерпан ({used}/{limit}).\n"
            "Попробуй завтра!"
        )
        return

    status_msg = await message.answer("🤔 Думаю...")

    try:
        vault_context = await build_vault_context(user_ctx.vault_path)
        response = await llm_router.ask(question, vault_context)

        await db.log_usage(
            user_ctx.user_id, "ask",
            response.model, response.input_tokens, response.output_tokens, response.cost_usd,
        )

        formatted = format_llm_response(response.text)
        try:
            await status_msg.edit_text(formatted)
        except Exception:
            try:
                await status_msg.edit_text(formatted, parse_mode=None)
            except Exception:
                await message.answer(formatted)

    except Exception as e:
        logger.exception("Error processing /ask")
        await status_msg.edit_text(format_error(str(e)))
