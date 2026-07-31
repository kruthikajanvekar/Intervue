"""
Thin, provider-agnostic LLM client. Agents call `llm_service.complete_json(...)`
and get back a parsed dict - they never touch the OpenAI/Gemini SDKs
directly. Swapping providers is a one-line env var change (LLM_PROVIDER).
"""
import json
import re
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logger import logger


class LLMError(RuntimeError):
    pass


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


class LLMService:
    def __init__(self):
        self.provider = settings.llm_provider
        if self.provider == "openai":
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
            self._model = settings.openai_model
        elif self.provider == "gemini":
            from google import genai

            self._client = genai.Client(api_key=settings.gemini_api_key)
            self._model = settings.gemini_model
        else:
            raise LLMError(f"Unsupported LLM provider: {self.provider}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.4,
    ) -> dict:
        """Call the LLM and parse a strict-JSON response. Retries on malformed JSON."""
        raw = await self._complete_raw(system_prompt, user_prompt, max_tokens, temperature)
        cleaned = _strip_code_fences(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            # Try to salvage a JSON object embedded in extra prose.
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            logger.error("LLM returned non-JSON payload: {}", raw[:500])
            raise LLMError(f"Failed to parse LLM JSON response: {exc}") from exc

    async def _complete_raw(
        self, system_prompt: str, user_prompt: str, max_tokens: int, temperature: float
    ) -> str:
        if self.provider == "openai":
            resp = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return resp.choices[0].message.content or ""

        # gemini
        from google.genai import types

        resp = await self._client.aio.models.generate_content(
            model=self._model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=max_tokens,
                temperature=temperature,
                response_mime_type="application/json",
            ),
        )
        return resp.text or ""


_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
