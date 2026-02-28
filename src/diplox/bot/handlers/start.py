"""Handler for /start — onboarding via deep link + /help, /status."""

import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from diplox.bot.keyboards import get_main_menu
from diplox.config import get_settings
from diplox.services.database import Database
from diplox.services.user_context import UserContext, UserContextService

router = Router(name="start")
logger = logging.getLogger(__name__)


@router.message(Command("start"))
async def cmd_start(
    message: Message,
    command: CommandObject,
    db: Database,
    user_ctx_service: UserContextService,
) -> None:
    """Handle /start with optional deep link token."""
    if not message.from_user:
        return

    telegram_id = message.from_user.id
    token = command.args

    if not token:
        # No token — check if already registered
        existing = await db.get_user_by_telegram_id(telegram_id)
        if existing:
            await message.answer(
                f"👋 С возвратом, <b>{existing.name}</b>!\n\n"
                "Используй меню внизу для навигации 👇",
                reply_markup=get_main_menu(),
            )
        else:
            settings = get_settings()
            await message.answer(
                "👋 Привет! Я <b>Diplox</b> — AI-ассистент для студентов.\n\n"
                f"Для доступа зарегистрируйся на <b>{settings.landing_url}</b> "
                "с инвайт-кодом, а потом нажми кнопку «Открыть бота»."
            )
        return

    # Validate onboarding token
    user = await db.get_user_by_token(token)
    if not user:
        await message.answer(
            "❌ Ссылка недействительна или уже использована.\n"
            "Попробуй зарегистрироваться заново."
        )
        return

    if user.telegram_id is not None:
        await message.answer(
            f"✅ Ты уже зарегистрирован, <b>{user.name}</b>!\n"
            "Отправь текст или голосовое — я сохраню."
        )
        return

    # Link Telegram account
    await db.link_telegram(user.id, telegram_id)

    # Ensure vault directories exist
    from pathlib import Path

    vault = Path(user.vault_path)
    (vault / "daily").mkdir(parents=True, exist_ok=True)
    (vault / "attachments").mkdir(parents=True, exist_ok=True)
    (vault / "docs").mkdir(parents=True, exist_ok=True)
    (vault / ".sessions").mkdir(parents=True, exist_ok=True)

    await message.answer(
        f"🎉 Добро пожаловать, <b>{user.name}</b>!\n\n"
        "Я твой AI-ассистент для учёбы. Вот что я умею:\n\n"
        "📝 <b>Отправь текст</b> — сохраню заметку\n"
        "🎤 <b>Отправь голосовое</b> — транскрибирую и сохраню\n"
        "📄 <b>Отправь документ</b> (PDF, DOCX) — извлеку текст\n\n"
        "Используй меню внизу для навигации 👇",
        reply_markup=get_main_menu(),
    )

    logger.info("User onboarded: %s (tg: %d)", user.name, telegram_id)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "📖 <b>Diplox — AI-ассистент для студентов</b>\n\n"
        "<b>📝 Заметки:</b>\n"
        "• Отправь текст — сохраню как заметку\n"
        "• Отправь голосовое — транскрибирую и сохраню\n"
        "• Отправь PDF/DOCX — извлеку текст\n\n"
        "<b>🤖 AI-команды:</b>\n"
        "/ask — задать вопрос по заметкам\n"
        "/do — выполнить задачу\n"
        "/process — обработать записи за день\n\n"
        "<b>🎓 Инструменты:</b>\n"
        "• План работы (диплом, курсовая, ВКР...)\n"
        "• Проверка грамматики\n"
        "• Рерайт для уникальности\n"
        "• Аннотация / реферат\n"
        "• Поиск литературы\n"
        "• Форматирование по ГОСТу\n\n"
        "Используй меню внизу 👇",
        reply_markup=get_main_menu(),
    )


@router.message(Command("status"))
async def cmd_status(message: Message, db: Database, user_ctx: UserContext) -> None:
    ask_used = await db.get_daily_usage_count(user_ctx.user_id, "ask")
    do_used = await db.get_daily_usage_count(user_ctx.user_id, "do")
    process_used = await db.get_daily_usage_count(user_ctx.user_id, "process")

    await message.answer(
        f"📊 <b>Статус — {user_ctx.name}</b>\n\n"
        f"<b>Квота сегодня:</b>\n"
        f"• /ask: {ask_used}/20\n"
        f"• /do: {do_used}/10\n"
        f"• /process: {process_used}/2\n\n"
        f"<i>Сохранение текста и голоса — без ограничений</i>"
    )
