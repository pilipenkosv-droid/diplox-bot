"""Document handler — extract text from PDF/DOCX/XLSX/CSV and save to vault."""

import logging
from datetime import datetime

from aiogram import Bot, Router
from aiogram.types import Message

from diplox.services.document import DocumentExtractor
from diplox.services.session import SessionStore
from diplox.services.storage import VaultStorage
from diplox.services.user_context import UserContext

router = Router(name="document")
logger = logging.getLogger(__name__)

DOCUMENT_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
    "text/comma-separated-values",
    "application/csv",
}

DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".csv"}
MAX_FILE_SIZE = 20 * 1024 * 1024

FORMAT_ICONS = {
    ".pdf": "📕",
    ".docx": "📘",
    ".xlsx": "📊",
    ".csv": "📊",
}


def _make_summary(text: str, max_len: int = 120) -> str:
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("---") or line.startswith("|"):
            continue
        if len(line) > max_len:
            cut = line.rfind(". ", 0, max_len)
            if cut > max_len * 0.4:
                return line[: cut + 1]
            cut = line.rfind(" ", 0, max_len)
            if cut > 0:
                return line[:cut] + "..."
            return line[:max_len] + "..."
        return line
    return "документ обработан"


def is_supported_document(message: Message) -> bool:
    if not message.document:
        return False
    doc = message.document
    if doc.mime_type and doc.mime_type in DOCUMENT_MIME_TYPES:
        return True
    if doc.file_name:
        ext = "." + doc.file_name.rsplit(".", 1)[-1].lower() if "." in doc.file_name else ""
        if ext in DOCUMENT_EXTENSIONS:
            return True
    return False


@router.message(is_supported_document)
async def handle_document(message: Message, bot: Bot, user_ctx: UserContext) -> None:
    if not message.document or not message.from_user:
        return

    doc = message.document
    file_name = doc.file_name or "document"
    file_size = doc.file_size or 0
    ext = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

    if ext == ".xls":
        await message.answer(
            "❌ Формат <b>.xls</b> (Excel 97-2003) не поддерживается.\n"
            "<i>Сохрани файл как .xlsx и отправь снова.</i>"
        )
        return

    if file_size > MAX_FILE_SIZE:
        size_mb = file_size / (1024 * 1024)
        await message.answer(f"❌ Файл слишком большой ({size_mb:.0f} MB). Лимит: 20 MB.")
        return

    icon = FORMAT_ICONS.get(ext, "📄")
    size_mb = file_size / (1024 * 1024)
    status_msg = await message.answer(
        f"{icon} <b>Обрабатываю: {file_name}</b>\n"
        f"<i>Размер: {size_mb:.1f} MB. Извлекаю текст...</i>"
    )

    storage = VaultStorage(user_ctx.vault_path)
    extractor = DocumentExtractor()

    try:
        file = await bot.get_file(doc.file_id)
        if not file.file_path:
            await status_msg.edit_text("❌ Не удалось скачать файл")
            return

        file_bytes_io = await bot.download_file(file.file_path)
        if not file_bytes_io:
            await status_msg.edit_text("❌ Не удалось скачать файл")
            return

        file_bytes = file_bytes_io.read()

        try:
            extracted = await extractor.extract(file_bytes, file_name)
        except ValueError as e:
            await status_msg.edit_text(f"❌ <b>{file_name}</b>\n{e}")
            return

        if not extracted or not extracted.strip():
            await status_msg.edit_text(
                f"❌ Не удалось извлечь текст из <b>{file_name}</b>"
            )
            return

        timestamp = datetime.fromtimestamp(message.date.timestamp())
        attachment_path = storage.save_document_attachment(
            file_bytes, timestamp.date(), file_name
        )

        text_for_vault = extractor.truncate_for_vault(extracted, attachment_path)
        content = f"Документ: {file_name}\n\n{text_for_vault}"
        storage.append_to_daily(content, timestamp, f"[doc:{file_name}]")

        session = SessionStore(user_ctx.vault_path)
        session.append(
            message.from_user.id,
            "document",
            text=extracted[:500],
            file_name=file_name,
            file_size=file_size,
            msg_id=message.message_id,
        )

        char_count = len(extracted)
        summary = _make_summary(extracted)

        await status_msg.edit_text(
            f"{icon} <b>{file_name}</b> — {summary}\n\n"
            f"<i>{char_count} символов извлечено и сохранено</i> ✓"
        )

        logger.info("Document processed for user %s: %s, %d chars", user_ctx.user_id, file_name, char_count)

    except Exception as e:
        logger.exception("Error processing document: %s", file_name)
        await status_msg.edit_text(f"❌ Ошибка при обработке <b>{file_name}</b>:\n{e}")
