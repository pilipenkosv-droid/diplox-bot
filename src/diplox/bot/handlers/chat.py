"""Handler for free chat — general AI conversation without vault context."""

import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from diplox.bot.formatters import format_error, format_llm_response
from diplox.bot.states import ChatState
from diplox.services.database import Database
from diplox.services.llm import LLMRouter
from diplox.services.user_context import UserContext, UserContextService

router = Router(name="chat")
logger = logging.getLogger(__name__)

_MAX_HISTORY = 10
_MAX_ENTRY = 3000

_CHAT_SYSTEM = (
    "Ты — Diplox, дружелюбный AI-ассистент для студентов. "
    "Помогай с любыми вопросами: учёба, наука, карьера, жизнь. "
    "Отвечай на русском, кратко и по делу. "
    "Если не знаешь — честно скажи."
)


@router.callback_query(lambda c: c.data == "ai_chat")
async def chat_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.set_state(ChatState.chatting)
    await state.update_data(chat_history=[])
    await callback.message.edit_text(
        "💬 <b>Свободный чат</b>\n\n"
        "Спрашивай что угодно — я помогу.\n"
        "Для выхода нажми любую кнопку меню."
    )


@router.message(ChatState.chatting)
async def chat_message(
    message: Message,
    state: FSMContext,
    user_ctx: UserContext,
    user_ctx_service: UserContextService,
    llm_router: LLMRouter,
    db: Database,
) -> None:
    text = message.text
    if not text:
        await message.answer("💬 Отправь текстовое сообщение.")
        return

    # Check quota (uses 'ask' quota)
    allowed, used, limit = await user_ctx_service.check_quota(user_ctx.user_id, "ask")
    if not allowed:
        await message.answer(f"⏳ Лимит чата исчерпан ({used}/{limit}). Попробуй завтра!")
        return

    data = await state.get_data()
    history: list[dict] = data.get("chat_history", [])

    status_msg = await message.answer("💬 Думаю...")

    try:
        response = await llm_router.do(text, vault_context="", history=history or None)

        await db.log_usage(
            user_ctx.user_id, "ask",
            response.model, response.input_tokens, response.output_tokens, response.cost_usd,
        )

        # Update history
        history.append({"role": "user", "content": text[:_MAX_ENTRY]})
        history.append({"role": "assistant", "content": response.text[:_MAX_ENTRY]})
        if len(history) > _MAX_HISTORY * 2:
            history = history[-_MAX_HISTORY * 2 :]
        await state.update_data(chat_history=history)

        formatted = format_llm_response(response.text)
        try:
            await status_msg.edit_text(formatted)
        except Exception:
            await status_msg.edit_text(formatted, parse_mode=None)
    except Exception as e:
        logger.exception("Chat error")
        await status_msg.edit_text(format_error(str(e)))
