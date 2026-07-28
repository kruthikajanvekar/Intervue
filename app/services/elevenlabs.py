"""
ElevenLabs text-to-speech integration. Converts the interviewer's next
message into spoken audio (base64 mp3) so the frontend can play it directly.
"""
import base64
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logger import logger


class ElevenLabsError(RuntimeError):
    pass


class ElevenLabsService:
    def __init__(self):
        self.base_url = settings.elevenlabs_base_url
        self.api_key = settings.elevenlabs_api_key
        self.voice_id = settings.elevenlabs_voice_id
        self.model_id = settings.elevenlabs_model_id

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6))
    async def synthesize(self, text: str, voice_id: Optional[str] = None) -> str:
        """Returns base64-encoded MP3 audio for the given text."""
        if not self.api_key:
            logger.warning("ELEVENLABS_API_KEY not set - skipping TTS synthesis")
            return ""

        url = f"{self.base_url}/text-to-speech/{voice_id or self.voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.35, "use_speaker_boost": True},
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.error("ElevenLabs TTS failed [{}]: {}", resp.status_code, resp.text[:300])
                raise ElevenLabsError(f"ElevenLabs TTS failed with status {resp.status_code}")
            return base64.b64encode(resp.content).decode("utf-8")

    async def list_voices(self) -> list[dict]:
        if not self.api_key:
            return []
        url = f"{self.base_url}/voices"
        headers = {"xi-api-key": self.api_key}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json().get("voices", [])


_elevenlabs_service: Optional[ElevenLabsService] = None


def get_elevenlabs_service() -> ElevenLabsService:
    global _elevenlabs_service
    if _elevenlabs_service is None:
        _elevenlabs_service = ElevenLabsService()
    return _elevenlabs_service
