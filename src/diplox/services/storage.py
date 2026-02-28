"""Vault storage service for saving user entries."""

from datetime import date, datetime
from pathlib import Path


class VaultStorage:
    """Service for storing entries in per-user vault."""

    def __init__(self, vault_path: Path) -> None:
        self.vault_path = Path(vault_path)
        self.daily_path = self.vault_path / "daily"
        self.attachments_path = self.vault_path / "attachments"

    def _ensure_dirs(self) -> None:
        self.daily_path.mkdir(parents=True, exist_ok=True)
        self.attachments_path.mkdir(parents=True, exist_ok=True)

    def get_daily_file(self, day: date) -> Path:
        self._ensure_dirs()
        return self.daily_path / f"{day.isoformat()}.md"

    def read_daily(self, day: date) -> str:
        file_path = self.get_daily_file(day)
        if not file_path.exists():
            return ""
        return file_path.read_text(encoding="utf-8")

    def append_to_daily(
        self,
        text: str,
        timestamp: datetime,
        msg_type: str,
    ) -> str:
        self._ensure_dirs()
        file_path = self.get_daily_file(timestamp.date())

        time_str = timestamp.strftime("%H:%M")
        entry = f"\n## {time_str} {msg_type}\n{text}\n"

        with file_path.open("a", encoding="utf-8") as f:
            f.write(entry)

        return f"daily/{timestamp.date().isoformat()}.md"

    def get_attachments_dir(self, day: date) -> Path:
        dir_path = self.attachments_path / day.isoformat()
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path

    def save_attachment(
        self,
        data: bytes,
        day: date,
        timestamp: datetime,
        extension: str = "jpg",
    ) -> str:
        dir_path = self.get_attachments_dir(day)
        time_str = timestamp.strftime("%H%M%S")
        filename = f"img-{time_str}.{extension}"
        file_path = dir_path / filename
        file_path.write_bytes(data)
        return f"attachments/{day.isoformat()}/{filename}"

    def save_document_attachment(
        self,
        data: bytes,
        day: date,
        file_name: str,
    ) -> str:
        dir_path = self.get_attachments_dir(day)
        file_path = dir_path / file_name

        if file_path.exists():
            stem = file_path.stem
            suffix = file_path.suffix
            counter = 1
            while file_path.exists():
                file_path = dir_path / f"{stem}_{counter}{suffix}"
                counter += 1

        file_path.write_bytes(data)
        return f"attachments/{day.isoformat()}/{file_path.name}"
