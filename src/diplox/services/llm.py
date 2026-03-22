"""LLM router — Claude Haiku + Gemini Flash for all commands."""

import base64
import logging
from dataclasses import dataclass

import anthropic
from google import genai

logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5-20251001"
GEMINI_MODEL = "gemini-2.5-flash"

# Pricing per 1M tokens
HAIKU_INPUT_COST = 0.80  # $/1M input tokens
HAIKU_OUTPUT_COST = 4.00  # $/1M output tokens

VISION_PROMPT = (
    "Опиши изображение. Если это учебный материал (конспект, слайд, задача, формула) — "
    "извлеки текст и структурируй. Если это фото — опиши кратко. Отвечай на русском."
)


@dataclass
class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class LLMRouter:
    def __init__(self, gemini_api_key: str, anthropic_api_key: str) -> None:
        self._anthropic = anthropic.AsyncAnthropic(api_key=anthropic_api_key)
        self._gemini = genai.Client(api_key=gemini_api_key)

    def _calc_cost(self, input_tokens: int, output_tokens: int) -> float:
        return round(
            input_tokens * HAIKU_INPUT_COST / 1_000_000
            + output_tokens * HAIKU_OUTPUT_COST / 1_000_000,
            6,
        )

    async def ask(
        self,
        question: str,
        vault_context: str,
        system: str = "",
    ) -> LLMResponse:
        """Q&A using Claude Haiku."""
        if not system:
            system = (
                "Ты — AI-ассистент для студентов. Отвечай на вопросы, "
                "используя контекст из заметок студента. "
                "Отвечай на русском, кратко и по делу. "
                "Если в заметках нет ответа — скажи об этом честно."
            )

        if vault_context:
            system += f"\n\n=== ЗАМЕТКИ СТУДЕНТА ===\n{vault_context}\n=== КОНЕЦ ЗАМЕТОК ==="

        response = await self._anthropic.messages.create(
            model=HAIKU_MODEL,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": question}],
        )

        text = response.content[0].text if response.content else ""
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        return LLMResponse(
            text=text,
            model=HAIKU_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self._calc_cost(input_tokens, output_tokens),
        )

    async def do(
        self,
        prompt: str,
        vault_context: str,
        history: list[dict] | None = None,
    ) -> LLMResponse:
        """Execute arbitrary task using Claude Haiku."""
        system = (
            "Ты — AI-ассистент для студентов. Помогай с учебными задачами: "
            "написание текстов, анализ материалов, подготовка к экзаменам, "
            "структурирование заметок. Отвечай на русском."
        )

        if vault_context:
            system += f"\n\nКонтекст из заметок студента:\n{vault_context[:10000]}"

        messages: list[dict] = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        response = await self._anthropic.messages.create(
            model=HAIKU_MODEL,
            max_tokens=4096,
            system=system,
            messages=messages,
        )

        text = response.content[0].text if response.content else ""
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        return LLMResponse(
            text=text,
            model=HAIKU_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self._calc_cost(input_tokens, output_tokens),
        )

    async def process(
        self,
        daily_content: str,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Process daily entries using Claude Haiku."""
        if not system_prompt:
            system_prompt = (
                "Ты — AI-ассистент для студентов. Проанализируй записи за день и создай:\n"
                "1. Краткое резюме дня (что было сделано, что изучено)\n"
                "2. Ключевые концепции и определения\n"
                "3. Нерешённые вопросы\n"
                "4. Рекомендации на следующий день\n\n"
                "Формат: HTML для Telegram (используй <b>, <i>, <code>). "
                "Отвечай на русском."
            )

        response = await self._anthropic.messages.create(
            model=HAIKU_MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": f"Записи за день:\n\n{daily_content}"}],
        )

        text = response.content[0].text if response.content else ""
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        return LLMResponse(
            text=text,
            model=HAIKU_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self._calc_cost(input_tokens, output_tokens),
        )

    async def describe_image(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        caption: str | None = None,
    ) -> LLMResponse:
        """Describe image using Gemini Flash (primary) with Haiku fallback."""
        prompt = VISION_PROMPT
        if caption:
            prompt = f"{VISION_PROMPT}\n\nПодпись пользователя: {caption}"

        # --- Try Gemini Flash (free tier) ---
        try:
            response = await self._gemini.aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    genai.types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    genai.types.Part.from_text(text=prompt),
                ],
            )
            text = response.text or ""
            if text:
                logger.info("Vision: Gemini Flash OK")
                return LLMResponse(
                    text=text,
                    model=GEMINI_MODEL,
                    input_tokens=getattr(response.usage_metadata, "prompt_token_count", 0) or 0,
                    output_tokens=getattr(response.usage_metadata, "candidates_token_count", 0) or 0,
                    cost_usd=0.0,  # free tier
                )
        except Exception as e:
            logger.warning("Vision: Gemini Flash failed (%s), falling back to Haiku", e)

        # --- Fallback: Claude Haiku ---
        b64_data = base64.standard_b64encode(image_bytes).decode()
        haiku_response = await self._anthropic.messages.create(
            model=HAIKU_MODEL,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": mime_type, "data": b64_data},
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        text = haiku_response.content[0].text if haiku_response.content else ""
        input_tokens = haiku_response.usage.input_tokens
        output_tokens = haiku_response.usage.output_tokens
        logger.info("Vision: Haiku fallback used")
        return LLMResponse(
            text=text,
            model=HAIKU_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self._calc_cost(input_tokens, output_tokens),
        )
