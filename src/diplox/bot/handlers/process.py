"""Handler for /process — daily entries processing using Claude Haiku."""

import logging
from datetime import date

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from diplox.bot.formatters import format_empty_daily, format_error, format_llm_response
from diplox.services.database import Database
from diplox.services.storage import VaultStorage
from diplox.services.user_context import UserContext, UserContextService
from diplox.services.llm import LLMRouter

router = Router(name="process")
logger = logging.getLogger(__name__)


@router.message(Command("process"))
async def cmd_process(
    message: Message,
    user_ctx: UserContext,
    user_ctx_service: UserContextService,
    llm_router: LLMRouter,
    db: Database,
) -> None:
    # Check quota
    allowed, used, limit = await user_ctx_service.check_quota(user_ctx.user_id, "process")
    if not allowed:
        await message.answer(
            f"⏳ Дневной лимит /process исчерпан ({used}/{limit}).\n"
            "Попробуй завтра!"
        )
        return

    storage = VaultStorage(user_ctx.vault_path)
    daily_content = storage.read_daily(date.today())

    if not daily_content.strip():
        await message.answer(format_empty_daily())
        return

    status_msg = await message.answer("⏳ Обрабатываю записи за день...")

    try:
        response = await llm_router.process(daily_content)

        await db.log_usage(
            user_ctx.user_id, "process",
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
        logger.exception("Error processing /process")
        await status_msg.edit_text(format_error(str(e)))
