"""SQLite database service for multi-tenant user management."""

import secrets
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    telegram_id INTEGER UNIQUE,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    vault_path TEXT NOT NULL,
    daily_quota INTEGER DEFAULT 20,
    is_active BOOLEAN DEFAULT TRUE,
    onboarding_token TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT REFERENCES users(id),
    action TEXT NOT NULL,
    model TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invites (
    code TEXT PRIMARY KEY,
    used_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    used_at TIMESTAMP
);
"""


@dataclass
class UserRow:
    id: str
    telegram_id: int | None
    name: str
    email: str
    vault_path: str
    daily_quota: int
    is_active: bool
    onboarding_token: str | None
    created_at: str


class Database:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def _connect(self) -> aiosqlite.Connection:
        conn = await aiosqlite.connect(self._db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # --- User CRUD ---

    async def create_user(
        self,
        name: str,
        email: str,
        vault_path: str,
    ) -> UserRow:
        user_id = str(uuid.uuid4())
        token = secrets.token_urlsafe(32)
        async with await self._connect() as db:
            await db.execute(
                """INSERT INTO users (id, name, email, vault_path, onboarding_token)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, name, email, vault_path, token),
            )
            await db.commit()
        return UserRow(
            id=user_id,
            telegram_id=None,
            name=name,
            email=email,
            vault_path=vault_path,
            daily_quota=20,
            is_active=True,
            onboarding_token=token,
            created_at=datetime.now().isoformat(),
        )

    async def get_user_by_telegram_id(self, telegram_id: int) -> UserRow | None:
        async with await self._connect() as db:
            cursor = await db.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            )
            row = await cursor.fetchone()
            return self._row_to_user(row) if row else None

    async def get_user_by_token(self, token: str) -> UserRow | None:
        async with await self._connect() as db:
            cursor = await db.execute(
                "SELECT * FROM users WHERE onboarding_token = ?", (token,)
            )
            row = await cursor.fetchone()
            return self._row_to_user(row) if row else None

    async def get_user_by_email(self, email: str) -> UserRow | None:
        async with await self._connect() as db:
            cursor = await db.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            )
            row = await cursor.fetchone()
            return self._row_to_user(row) if row else None

    async def link_telegram(self, user_id: str, telegram_id: int) -> None:
        async with await self._connect() as db:
            await db.execute(
                """UPDATE users SET telegram_id = ?, onboarding_token = NULL
                   WHERE id = ?""",
                (telegram_id, user_id),
            )
            await db.commit()

    # --- Invites ---

    async def validate_invite(self, code: str) -> bool:
        async with await self._connect() as db:
            cursor = await db.execute(
                "SELECT code FROM invites WHERE code = ? AND used_by IS NULL",
                (code,),
            )
            return await cursor.fetchone() is not None

    async def use_invite(self, code: str, user_id: str) -> None:
        async with await self._connect() as db:
            await db.execute(
                "UPDATE invites SET used_by = ?, used_at = CURRENT_TIMESTAMP WHERE code = ?",
                (user_id, code),
            )
            await db.commit()

    async def generate_invites(self, count: int, prefix: str = "alpha") -> list[str]:
        codes = [f"{prefix}-{secrets.token_hex(3)}" for _ in range(count)]
        async with await self._connect() as db:
            await db.executemany(
                "INSERT OR IGNORE INTO invites (code) VALUES (?)",
                [(c,) for c in codes],
            )
            await db.commit()
        return codes

    # --- Usage ---

    async def log_usage(
        self,
        user_id: str,
        action: str,
        model: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0,
    ) -> None:
        async with await self._connect() as db:
            await db.execute(
                """INSERT INTO usage_log (user_id, action, model, input_tokens, output_tokens, cost_usd)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, action, model, input_tokens, output_tokens, cost_usd),
            )
            await db.commit()

    async def get_daily_usage_count(self, user_id: str, action: str) -> int:
        today = date.today().isoformat()
        async with await self._connect() as db:
            cursor = await db.execute(
                """SELECT COUNT(*) FROM usage_log
                   WHERE user_id = ? AND action = ? AND date(created_at) = ?""",
                (user_id, action, today),
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_total_daily_usage(self, user_id: str) -> int:
        today = date.today().isoformat()
        async with await self._connect() as db:
            cursor = await db.execute(
                """SELECT COUNT(*) FROM usage_log
                   WHERE user_id = ? AND action IN ('ask', 'do', 'process')
                   AND date(created_at) = ?""",
                (user_id, today),
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    # --- Admin ---

    async def list_users(self) -> list[UserRow]:
        async with await self._connect() as db:
            cursor = await db.execute("SELECT * FROM users ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            return [self._row_to_user(r) for r in rows]

    async def get_usage_stats(self) -> dict:
        today = date.today().isoformat()
        async with await self._connect() as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total_users = (await cursor.fetchone())[0]

            cursor = await db.execute(
                """SELECT COUNT(DISTINCT user_id) FROM usage_log
                   WHERE date(created_at) = ?""",
                (today,),
            )
            active_today = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM usage_log WHERE date(created_at) = ?",
                (today,),
            )
            requests_today = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) FROM usage_log WHERE date(created_at) = ?",
                (today,),
            )
            cost_today = (await cursor.fetchone())[0]

            cursor = await db.execute(
                """SELECT COALESCE(SUM(cost_usd), 0) FROM usage_log
                   WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')"""
            )
            cost_month = (await cursor.fetchone())[0]

        return {
            "total_users": total_users,
            "active_today": active_today,
            "requests_today": requests_today,
            "cost_today_usd": round(cost_today, 4),
            "cost_month_usd": round(cost_month, 4),
        }

    @staticmethod
    def _row_to_user(row: aiosqlite.Row) -> UserRow:
        return UserRow(
            id=row["id"],
            telegram_id=row["telegram_id"],
            name=row["name"],
            email=row["email"],
            vault_path=row["vault_path"],
            daily_quota=row["daily_quota"],
            is_active=bool(row["is_active"]),
            onboarding_token=row["onboarding_token"],
            created_at=row["created_at"],
        )


async def init_db(db_path: Path) -> None:
    """Initialize database schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.executescript(SCHEMA)
        await db.commit()
