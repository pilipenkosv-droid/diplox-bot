"""Deepgram transcription service."""

import logging

from deepgram import AsyncDeepgramClient

logger = logging.getLogger(__name__)


class DeepgramTranscriber:
    """Service for transcribing audio using Deepgram Nova-3."""

    def __init__(self, api_key: str) -> None:
        self.client = AsyncDeepgramClient(api_key=api_key)

    async def transcribe(self, audio_bytes: bytes) -> str:
        logger.info("Starting transcription, audio size: %d bytes", len(audio_bytes))

        response = await self.client.listen.v1.media.transcribe_file(
            request=audio_bytes,
            model="nova-3",
            language="ru",
            punctuate=True,
            smart_format=True,
        )

        transcript = (
            response.results.channels[0].alternatives[0].transcript
            if response.results
            and response.results.channels
            and response.results.channels[0].alternatives
            else ""
        )

        # Strip surrogate characters that Deepgram occasionally returns
        transcript = transcript.encode("utf-8", errors="ignore").decode("utf-8")

        logger.info("Transcription complete: %d chars", len(transcript))
        return transcript
