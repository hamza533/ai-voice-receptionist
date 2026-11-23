"""The only module that talks to a text LLM (post-call summaries, eval judge).

Switching provider (OpenAI, Azure OpenAI, Vertex AI) only changes this file.
"""

from __future__ import annotations

import functools
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import LLMUsage
from app.services.retry import PermanentError, retry_call

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

# Paid-tier list prices in USD per 1M tokens, used for cost estimates only.
# Gemini 2.5 Flash text: $0.30 input / $2.50 output.
PRICE_PER_M = {"input": 0.30, "output": 2.50}


class LLMUnavailable(RuntimeError):
    pass


@dataclass
class LLMResult[M: BaseModel]:
    value: M
    input_tokens: int
    output_tokens: int
    latency_ms: int
    model: str

    @property
    def cost_usd(self) -> float:
        return (
            self.input_tokens * PRICE_PER_M["input"] + self.output_tokens * PRICE_PER_M["output"]
        ) / 1_000_000


class LLM:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: Any = None

    @property
    def available(self) -> bool:
        return bool(self.settings.gemini_api_key)

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=self.settings.gemini_api_key,
                http_options=types.HttpOptions(
                    timeout=int(self.settings.llm_timeout_s * 1000), api_version="v1beta"
                ),
            )
        return self._client

    def generate_json(
        self,
        prompt: str,
        schema: type[T],
        *,
        system: str = "",
        temperature: float = 0.2,
    ) -> LLMResult[T]:
        if not self.available:
            raise LLMUnavailable("GEMINI_API_KEY is not set")
        from google.genai import types

        client = self._get_client()
        config = types.GenerateContentConfig(
            system_instruction=system or None,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=temperature,
        )

        def _call(model: str) -> Any:
            from google.genai import errors

            try:
                return client.models.generate_content(model=model, contents=prompt, config=config)
            except errors.ClientError as exc:
                # 4xx other than rate limiting will never succeed: don't retry it.
                if getattr(exc, "code", 0) != 429:
                    raise PermanentError(str(exc)[:300]) from exc
                raise

        # Primary model, then fallbacks: free-tier models are regularly "high demand" (503)
        # or retired for new keys (404), and a busy model must not block call summaries.
        models = [self.settings.llm_model, *self.settings.llm_fallback_models]
        started = time.perf_counter()
        last: Exception | None = None
        resp = None
        used = models[0]
        for model in dict.fromkeys(m for m in models if m):
            try:
                resp = retry_call(
                    functools.partial(_call, model), what="llm.generate_json", attempts=2, base=1.0
                )
                used = model
                break
            except Exception as exc:
                last = exc
                log.warning("llm model failed, trying next", extra={"model": model})
        if resp is None:
            assert last is not None
            raise last
        latency = int((time.perf_counter() - started) * 1000)
        parsed = resp.parsed if isinstance(resp.parsed, schema) else None
        if parsed is None:
            parsed = schema.model_validate(json.loads(resp.text or "{}"))
        usage = resp.usage_metadata
        return LLMResult(
            value=parsed,
            input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
            output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
            latency_ms=latency,
            model=used,
        )


def record_usage(
    db: Session, result: LLMResult[BaseModel], *, purpose: str, call_id: uuid.UUID | None
) -> None:
    db.add(
        LLMUsage(
            call_id=call_id,
            purpose=purpose,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            est_cost_usd=result.cost_usd,
        )
    )
    log.info(
        "llm usage",
        extra={
            "purpose": purpose,
            "model": result.model,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "latency_ms": result.latency_ms,
        },
    )
