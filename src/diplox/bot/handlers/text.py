"""Text message handler — save to vault."""

import logging
from datetime import datetime

from aiogram import Router
from aiogram.types import Message

from diplox.services.session import SessionStore
from diplox.services.storage import VaultStorage
from diplox.services.user_context import UserContext

router = Router(name="text")
logger = logging.getLogger(__name__)


@router.message(lambda m: m.text is not None and not m.text.startswith("/"))
async def handle_text(message: Message, user_ctx: UserContext) -> None:
    if not message.text or not message.from_user:
        return

    storage = VaultStorage(user_ctx.vault_path)
    timestamp = datetime.fromtimestamp(message.date.timestamp())
    storage.append_to_daily(message.text, timestamp, "[text]")

    session = SessionStore(user_ctx.vault_path)
    session.append(
        message.from_user.id,
        "text",
        text=message.text,
        msg_id=message.message_id,
    )

    await message.answer("✓ Сохранено")
    logger.info("Text saved for user %s: %d chars", user_ctx.user_id, len(message.text))
