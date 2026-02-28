"""Voice message handler — transcribe and save to vault."""

import logging
from datetime import datetime

from aiogram import Bot, Router
from aiogram.types import Message

from diplox.config import get_settings
from diplox.services.session import SessionStore
from diplox.services.storage import VaultStorage
from diplox.services.transcription import DeepgramTranscriber
from diplox.services.user_context import UserContext

router = Router(name="voice")
logger = logging.getLogger(__name__)


@router.message(lambda m: m.voice is not None)
async def handle_voice(message: Message, bot: Bot, user_ctx: UserContext) -> None:
    if not message.voice or not message.from_user:
        return

    await message.chat.do(action="typing")

    settings = get_settings()
    storage = VaultStorage(user_ctx.vault_path)
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

        audio_bytes = file_bytes.read()
        transcript = await transcriber.transcribe(audio_bytes)

        if not transcript:
            await message.answer("❌ Не удалось распознать речь")
            return

        timestamp = datetime.fromtimestamp(message.date.timestamp())
        storage.append_to_daily(transcript, timestamp, "[voice]")

        session = SessionStore(user_ctx.vault_path)
        session.append(
            message.from_user.id,
            "voice",
            text=transcript,
            duration=message.voice.duration,
            msg_id=message.message_id,
        )

        reply_text = f"🎤 {transcript}\n\n✓ Сохранено"
        if len(reply_text) <= 4096:
            await message.answer(reply_text)
        else:
            # Split long transcripts
            chunks = []
            remaining = transcript
            while remaining:
                if len(remaining) <= 4000:
                    chunks.append(remaining)
                    break
                split_at = remaining.rfind(". ", 0, 4000)
                if split_at == -1:
                    split_at = remaining.rfind(" ", 0, 4000)
                if split_at == -1:
                    split_at = 4000
                else:
                    split_at += 1
                chunks.append(remaining[:split_at])
                remaining = remaining[split_at:].lstrip()

            for i, chunk in enumerate(chunks):
                if i == 0:
                    await message.answer(f"🎤 {chunk}")
                elif i == len(chunks) - 1:
                    await message.answer(f"{chunk}\n\n✓ Сохранено")
                else:
                    await message.answer(chunk)

        logger.info("Voice saved for user %s: %d chars", user_ctx.user_id, len(transcript))

    except Exception as e:
        logger.exception("Error processing voice message")
        await message.answer(f"❌ Ошибка: {e}")
