"""
Speech-to-text. Two backends are supported via TRANSCRIBE_PROVIDER:

- "openai": calls OpenAI's hosted Whisper API (simple, no local model weights).
- "local": runs faster-whisper locally (no external call, useful offline / for
  cost control, but needs the model weights downloaded on first use).
"""
import base64
import io
import tempfile
from typing import Optional

from app.core.config import settings
from app.core.logger import logger


class TranscriptionError(RuntimeError):
    pass


class WhisperService:
    def __init__(self):
        self.provider = settings.transcribe_provider
        self._local_model = None
        if self.provider == "openai":
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    def _get_local_model(self):
        if self._local_model is None:
            from faster_whisper import WhisperModel

            logger.info("Loading local faster-whisper model ({})", settings.whisper_local_model_size)
            self._local_model = WhisperModel(settings.whisper_local_model_size, device="cpu", compute_type="int8")
        return self._local_model

    async def transcribe_base64_audio(self, audio_base64: str, audio_format: str = "webm") -> str:
        if not audio_base64:
            raise TranscriptionError("No audio provided")
        try:
            audio_bytes = base64.b64decode(audio_base64)
        except Exception as exc:
            raise TranscriptionError(f"Invalid base64 audio: {exc}") from exc

        if self.provider == "openai":
            return await self._transcribe_openai(audio_bytes, audio_format)
        return self._transcribe_local(audio_bytes, audio_format)

    async def _transcribe_openai(self, audio_bytes: bytes, audio_format: str) -> str:
        buf = io.BytesIO(audio_bytes)
        buf.name = f"answer.{audio_format}"
        resp = await self._client.audio.transcriptions.create(
            model="whisper-1",
            file=buf,
        )
        return (resp.text or "").strip()

    def _transcribe_local(self, audio_bytes: bytes, audio_format: str) -> str:
        model = self._get_local_model()
        with tempfile.NamedTemporaryFile(suffix=f".{audio_format}") as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            segments, _info = model.transcribe(tmp.name, beam_size=5)
            return " ".join(seg.text.strip() for seg in segments).strip()


_whisper_service: Optional[WhisperService] = None


def get_whisper_service() -> WhisperService:
    global _whisper_service
    if _whisper_service is None:
        _whisper_service = WhisperService()
    return _whisper_service
