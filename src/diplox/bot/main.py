"""Telegram bot initialization and middleware."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from diplox.config import Settings
from diplox.services.user_context import UserContext, UserContextService

logger = logging.getLogger(__name__)


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    from diplox.bot.handlers import ask, chat, do, document, menu, notes, process, start, text, tools, voice

    dp = Dispatcher(storage=MemoryStorage())

    # Order matters:
    # 1. Commands first
    dp.include_router(start.router)
    dp.include_router(ask.router)
    dp.include_router(do.router)
    dp.include_router(process.router)
    # 2. Tools (FSM states + callbacks)
    dp.include_router(tools.router)
    # 3. Chat (FSM state)
    dp.include_router(chat.router)
    # 4. Notes (callbacks)
    dp.include_router(notes.router)
    # 5. Menu (reply keyboard buttons — BEFORE catch-all text)
    dp.include_router(menu.router)
    # 6. Catch-all handlers last
    dp.include_router(voice.router)
    dp.include_router(document.router)
    dp.include_router(text.router)

    return dp


MiddlewareHandler = Callable[[Update, dict[str, Any]], Awaitable[Any]]
MiddlewareType = Callable[[MiddlewareHandler, Update, dict[str, Any]], Awaitable[Any]]


def create_user_context_middleware(
    user_ctx_service: UserContextService,
    settings: Settings,
) -> MiddlewareType:
    """Middleware that resolves telegram_id -> UserContext for every request."""

    async def middleware(
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        user = None
        message_text = None

        if event.message:
            user = event.message.from_user
            message_text = event.message.text
        elif event.callback_query:
            user = event.callback_query.from_user

        if not user:
            return None

        # Let /start pass through without user context (onboarding)
        if message_text and message_text.startswith("/start"):
            return await handler(event, data)

        # Resolve user context
        user_ctx = await user_ctx_service.get_or_none(user.id)

        if user_ctx is None:
            # Unregistered user
            if event.message:
                await event.message.answer(
                    "👋 Привет! Для доступа к боту нужно зарегистрироваться.\n\n"
                    f"Перейди на <b>{settings.landing_url}</b> и введи инвайт-код."
                )
            return None

        # Inject user context into handler data
        data["user_ctx"] = user_ctx
        return await handler(event, data)

    return middleware
