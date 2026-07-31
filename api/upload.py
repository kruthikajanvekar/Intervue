"""
Standalone transcription endpoint - useful for a frontend that wants to
transcribe-and-preview an answer before submitting it, or for testing the
whisper service in isolation from the interview flow.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.services.whisper import get_whisper_service

router = APIRouter(prefix="/upload", tags=["upload"])


class TranscribeRequest(BaseModel):
    audio_base64: str
    audio_format: str = "webm"


class TranscribeResponse(BaseModel):
    text: str


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(payload: TranscribeRequest):
    whisper = get_whisper_service()
    try:
        text = await whisper.transcribe_base64_audio(payload.audio_base64, payload.audio_format)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return TranscribeResponse(text=text)
