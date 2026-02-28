"""Vault context builder — inline search replacement for Khoj."""

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


async def build_vault_context(vault_path: Path, max_chars: int = 30_000) -> str:
    """Read all .md files from user vault and concatenate as LLM context.

    Files are sorted by modification time (most recent first).
    For alpha with small vaults (10-50 notes), this is sufficient.
    """

    def _read_files() -> str:
        md_files = sorted(
            vault_path.rglob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if not md_files:
            return ""

        parts: list[str] = []
        total_chars = 0

        for md_file in md_files:
            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception:
                continue

            relative = md_file.relative_to(vault_path)
            part = f"--- {relative} ---\n{content}"

            if total_chars + len(part) > max_chars:
                remaining = max_chars - total_chars
                if remaining > 100:
                    parts.append(part[:remaining] + "\n[...]")
                break

            parts.append(part)
            total_chars += len(part)

        return "\n\n".join(parts)

    context = await asyncio.to_thread(_read_files)
    logger.info(
        "Built vault context: %d chars from %s", len(context), vault_path
    )
    return context
