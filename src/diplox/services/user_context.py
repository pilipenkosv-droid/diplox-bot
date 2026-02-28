"""User context resolution and quota enforcement."""

from dataclasses import dataclass
from pathlib import Path

from diplox.services.database import Database

QUOTA_LIMITS: dict[str, int] = {
    "ask": 20,
    "do": 10,
    "process": 2,
}


@dataclass
class UserContext:
    user_id: str
    telegram_id: int
    name: str
    vault_path: Path
    daily_quota: int
    is_active: bool


class UserContextService:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def get_or_none(self, telegram_id: int) -> UserContext | None:
        user = await self._db.get_user_by_telegram_id(telegram_id)
        if user is None or not user.is_active:
            return None
        return UserContext(
            user_id=user.id,
            telegram_id=user.telegram_id,
            name=user.name,
            vault_path=Path(user.vault_path),
            daily_quota=user.daily_quota,
            is_active=user.is_active,
        )

    async def check_quota(
        self, user_id: str, action: str
    ) -> tuple[bool, int, int]:
        """Check if user can perform action. Returns (allowed, used, limit)."""
        limit = QUOTA_LIMITS.get(action, 0)
        if limit == 0:
            return True, 0, 0
        used = await self._db.get_daily_usage_count(user_id, action)
        return used < limit, used, limit
