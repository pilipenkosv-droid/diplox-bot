"""Session persistence service in JSONL format."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class SessionStore:
    """Persistent session storage in JSONL format.

    Each user gets their own session file at vault/.sessions/{user_id}.jsonl.
    """

    def __init__(self, vault_path: Path | str) -> None:
        self.sessions_dir = Path(vault_path) / ".sessions"
        self.sessions_dir.mkdir(exist_ok=True)

    def _get_session_file(self, user_id: int) -> Path:
        return self.sessions_dir / f"{user_id}.jsonl"

    def append(self, user_id: int, entry_type: str, **data: Any) -> None:
        entry = {
            "ts": datetime.now().astimezone().isoformat(),
            "type": entry_type,
            **data,
        }
        path = self._get_session_file(user_id)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_recent(self, user_id: int, limit: int = 50) -> list[dict]:
        path = self._get_session_file(user_id)
        if not path.exists():
            return []

        entries = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries[-limit:]

    def get_today(self, user_id: int) -> list[dict]:
        today = datetime.now().date().isoformat()
        return [
            e
            for e in self.get_recent(user_id, limit=200)
            if e.get("ts", "").startswith(today)
        ]

    def get_stats(self, user_id: int, days: int = 7) -> dict[str, int]:
        from datetime import timedelta

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        entries = self.get_recent(user_id, limit=1000)

        stats: dict[str, int] = {}
        for entry in entries:
            if entry.get("ts", "") >= cutoff:
                entry_type = entry.get("type", "unknown")
                stats[entry_type] = stats.get(entry_type, 0) + 1

        return stats
