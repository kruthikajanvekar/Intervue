"""
Centralized application configuration, loaded from environment variables / .env.
Every other module imports `settings` from here rather than reading
os.environ directly, so behavior stays consistent and testable.
"""
from functools import lru_cache
from typing import List, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "ai-technical-interviewer"
    env: str = "development"
    debug: bool = True
    secret_key: str = "dev-secret-change-me"
    api_v1_prefix: str = "/api/v1"
    cors_origins: List[str] = ["http://localhost:3000"]

    # Mongo
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "ai_interviewer"

    # LLM
    llm_provider: Literal["openai", "gemini"] = "gemini"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    elevenlabs_model_id: str = "eleven_turbo_v2_5"
    elevenlabs_base_url: str = "https://api.elevenlabs.io/v1"

    # Transcription
    transcribe_provider: Literal["openai", "local"] = "openai"
    whisper_local_model_size: str = "base"

    # Interview behavior
    max_questions_per_interview: int = 8
    min_questions_per_interview: int = 5
    difficulty_levels: str = "easy,medium,hard"
    reports_dir: str = "./reports"

    @property
    def difficulty_ladder(self) -> List[str]:
        return [d.strip() for d in self.difficulty_levels.split(",") if d.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
