"""Photo handler — describe image via Vision API and save to vault."""

import logging
from datetime import datetime

from aiogram import Bot, Router
from aiogram.types import Message

from diplox.config import get_settings
from diplox.services.database import Database
from diplox.services.llm import LLMRouter
from diplox.services.session import SessionStore
from diplox.services.storage import VaultStorage
from diplox.services.user_context import UserContext

router = Router(name="photo")
logger = logging.getLogger(__name__)


@router.message(lambda m: m.photo is not None)
async def handle_photo(message: Message, bot: Bot, user_ctx: UserContext, db: Database) -> None:
    if not message.photo or not message.from_user:
        return

    await message.chat.do(action="typing")

    settings = get_settings()
    storage = VaultStorage(user_ctx.vault_path)
    llm = LLMRouter(settings.gemini_api_key, settings.anthropic_api_key)

    try:
        # Get the largest photo size
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        if not file.file_path:
            await message.answer("❌ Не удалось скачать фото")
            return

        file_bytes_io = await bot.download_file(file.file_path)
        if not file_bytes_io:
            await message.answer("❌ Не удалось скачать фото")
            return

        image_bytes = file_bytes_io.read()
        caption = message.caption

        status_msg = await message.answer("🔍 Анализирую изображение...")

        response = await llm.describe_image(image_bytes, "image/jpeg", caption)

        # Save to vault
        timestamp = datetime.fromtimestamp(message.date.timestamp())
        vault_text = f"Фото: {response.text}"
        if caption:
            vault_text = f"Фото (подпись: {caption}): {response.text}"
        storage.append_to_daily(vault_text, timestamp, "[photo]")

        # Log to session
        session = SessionStore(user_ctx.vault_path)
        session.append(
            message.from_user.id,
            "photo",
            text=response.text[:500],
            caption=caption,
            model=response.model,
            msg_id=message.message_id,
        )

        # Log usage
        await db.log_usage(
            user_ctx.user_id,
            "photo",
            response.model,
            response.input_tokens,
            response.output_tokens,
            response.cost_usd,
        )

        # Reply
        reply = f"📷 {response.text}"
        if len(reply) > 4096:
            reply = reply[:4093] + "..."

        await status_msg.edit_text(f"{reply}\n\n✓ Сохранено")

        logger.info(
            "Photo processed for user %s: model=%s, %d chars",
            user_ctx.user_id,
            response.model,
            len(response.text),
        )

    except Exception as e:
        logger.exception("Error processing photo")
        await message.answer(f"❌ Ошибка при обработке фото: {e}")
