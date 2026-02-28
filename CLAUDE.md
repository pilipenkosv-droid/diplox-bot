# Diplox Alpha Bot

Multi-tenant AI-assistant for students. Telegram bot + FastAPI backend.

## Tech Stack
- Python 3.12+, uv
- aiogram 3.x (Telegram bot)
- FastAPI + uvicorn (web API + landing)
- SQLite + aiosqlite (database)
- Gemini Flash (free Q&A via google-genai)
- Claude Haiku (tasks via anthropic SDK)
- Deepgram Nova-3 (STT)

## Project Structure
```
src/diplox/
  __main__.py        # Entry point
  config.py          # Pydantic Settings
  bot/               # Telegram bot
    main.py          # Bot init, dispatcher, middleware
    handlers/        # Command handlers
  web/               # FastAPI
    app.py           # Registration + admin API
    static/          # Landing page
  services/          # Business logic
    database.py      # SQLite
    user_context.py  # Multi-tenant context
    llm.py           # LLM router
    storage.py       # Vault storage
    transcription.py # Deepgram STT
    document.py      # PDF/DOCX extraction
    session.py       # JSONL sessions
    search.py        # Vault context builder
```

## Running
```bash
cp .env.example .env  # Fill in API keys
uv sync
uv run python -m diplox
```

## Key Commands
- `/start` — onboarding via deep link
- `/ask` — Q&A by vault (Gemini Flash)
- `/do` — arbitrary tasks (Claude Haiku)
- `/process` — daily processing (Claude Haiku)
- `/status` — quota check
- `/help` — help

## Admin
```bash
# Generate invites
curl -X POST http://localhost:8080/api/admin/invites \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"count": 20, "prefix": "alpha"}'

# Check usage
curl http://localhost:8080/api/admin/usage -H "X-Admin-Key: $ADMIN_API_KEY"
```
