"""Entry point for running Diplox bot as a module."""

import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def main() -> None:
    import uvicorn

    from diplox.bot.main import create_bot, create_dispatcher, create_user_context_middleware
    from diplox.config import get_settings
    from diplox.services.database import Database, init_db
    from diplox.services.llm import LLMRouter
    from diplox.services.user_context import UserContextService
    from diplox.web.app import create_app

    settings = get_settings()
    logger.info("Diplox starting...")
    logger.info("Data dir: %s", settings.data_dir)

    # 1. Initialize database
    await init_db(settings.db_path)
    logger.info("Database initialized: %s", settings.db_path)

    # 2. Create services
    db = Database(settings.db_path)
    user_ctx_service = UserContextService(db)
    llm_router = LLMRouter(settings.gemini_api_key, settings.anthropic_api_key)

    # 3. Create bot + dispatcher
    bot = create_bot(settings)
    dp = create_dispatcher()
    dp.update.middleware(create_user_context_middleware(user_ctx_service, settings))

    # 4. Inject services into dispatcher for handler access
    dp["db"] = db
    dp["user_ctx_service"] = user_ctx_service
    dp["llm_router"] = llm_router
    dp["settings"] = settings

    # 5. Create FastAPI app
    fastapi_app = create_app(settings, db)

    # 6. Run bot polling + FastAPI concurrently
    uvicorn_config = uvicorn.Config(
        fastapi_app,
        host=settings.webapp_host,
        port=settings.webapp_port,
        log_level="info",
    )
    uvicorn_server = uvicorn.Server(uvicorn_config)

    try:
        await asyncio.gather(
            dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
            uvicorn_server.serve(),
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
