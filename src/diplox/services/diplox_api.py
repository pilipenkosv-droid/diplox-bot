"""HTTP client for Diplox web app API (outline, grammar, rewrite, summarize, sources)."""

import logging
from dataclasses import dataclass

import aiohttp

logger = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=60)


@dataclass
class GrammarMatch:
    message: str
    context: str
    offset: int
    length: int
    replacements: list[str]


@dataclass
class GrammarResult:
    matches: list[GrammarMatch]
    total: int


@dataclass
class Source:
    formatted: str  # GOST-formatted citation


@dataclass
class SourcesResult:
    sources: list[Source]
    total: int


class DiploxAPI:
    """Thin async client for Diplox web-app tool endpoints."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def _post(self, path: str, json: dict) -> dict:
        url = f"{self._base_url}{path}"
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.post(url, json=json) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error("Diplox API %s returned %d: %s", path, resp.status, body[:500])
                    raise RuntimeError(f"Ошибка сервиса ({resp.status})")
                return await resp.json()

    # ── Outline ──────────────────────────────────────────────
    async def generate_outline(
        self,
        topic: str,
        work_type: str,
        subject: str | None = None,
        requirements: str | None = None,
    ) -> str:
        payload: dict = {"topic": topic, "workType": work_type}
        if subject:
            payload["subject"] = subject
        if requirements:
            payload["additionalRequirements"] = requirements
        data = await self._post("/api/generate-outline", payload)
        return data.get("outline", "")

    # ── Grammar ──────────────────────────────────────────────
    async def check_grammar(self, text: str, language: str = "ru-RU") -> GrammarResult:
        data = await self._post("/api/check-grammar", {"text": text, "language": language})
        matches = []
        for m in data.get("matches", data.get("errors", [])):
            matches.append(GrammarMatch(
                message=m.get("message", ""),
                context=m.get("context", {}).get("text", "") if isinstance(m.get("context"), dict) else str(m.get("context", "")),
                offset=m.get("offset", 0),
                length=m.get("length", 0),
                replacements=[r.get("value", r) if isinstance(r, dict) else str(r) for r in m.get("replacements", [])[:3]],
            ))
        return GrammarResult(matches=matches, total=len(matches))

    # ── Rewrite ──────────────────────────────────────────────
    async def rewrite(
        self,
        text: str,
        mode: str = "medium",
        preserve_terms: str | None = None,
    ) -> str:
        payload: dict = {"text": text, "mode": mode}
        if preserve_terms:
            payload["preserveTerms"] = preserve_terms
        data = await self._post("/api/rewrite", payload)
        return data.get("rewritten", "")

    # ── Summarize ────────────────────────────────────────────
    async def summarize(self, text: str, target_length: str = "medium") -> str:
        data = await self._post("/api/summarize", {"text": text, "targetLength": target_length})
        return data.get("summary", "")

    # ── Sources ──────────────────────────────────────────────
    async def find_sources(
        self,
        topic: str,
        work_type: str,
        count: int = 10,
    ) -> SourcesResult:
        data = await self._post(
            "/api/find-sources",
            {"topic": topic, "workType": work_type, "count": count},
        )
        sources = []
        for s in data.get("sources", []):
            if isinstance(s, dict):
                formatted = s.get("gostFormatted", s.get("formatted", s.get("title", "")))
            else:
                formatted = str(s)
            sources.append(Source(formatted=formatted))
        return SourcesResult(sources=sources, total=len(sources))
