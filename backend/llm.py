"""Single shared gateway to the Groq LLM API.

* one ``AsyncGroq`` client per process (connection reuse), created lazily;
* a concurrency semaphore plus an async sliding-window RPM limiter guarded by a lock
  (the previous limiter mutated global state without one, so concurrent callers
  raced past the limit);
* JSON mode (``response_format=json_object``) instead of scraping JSON out of
  markdown fences;
* when no API key is configured every call returns ``None`` immediately instead of
  burning retries against an unauthenticated endpoint.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from typing import Any

from config import get_settings

logger = logging.getLogger(__name__)

_MAX_PROMPT_CHARS = 12_000


class _RateLimiter:
    """Sliding-window limiter: at most ``rpm`` acquisitions in any 60 s window."""

    def __init__(self, rpm: int) -> None:
        self.rpm = rpm
        self._calls: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= 60.0:
                    self._calls.popleft()
                if len(self._calls) < self.rpm:
                    self._calls.append(now)
                    return
                wait = 60.0 - (now - self._calls[0])
            logger.info("LLM rate limit reached (%d rpm); waiting %.1fs", self.rpm, wait)
            await asyncio.sleep(wait)


class LLMClient:
    def __init__(self) -> None:
        s = get_settings()
        self.enabled = s.llm_enabled
        self.model = s.groq_model
        self.timeout = s.groq_timeout
        self._api_key = s.groq_api_key
        self._client = None
        self._semaphore = asyncio.Semaphore(s.groq_max_concurrency)
        self._limiter = _RateLimiter(s.groq_rate_limit_rpm)

    def _get_client(self):
        if self._client is None:
            from groq import AsyncGroq

            # The SDK retries 429/5xx with backoff itself; keep it modest so a
            # single slow paper cannot stall an orchestration for minutes.
            self._client = AsyncGroq(api_key=self._api_key, max_retries=2, timeout=self.timeout)
        return self._client

    async def chat_json(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> dict[str, Any] | None:
        """Return the model's JSON object, or ``None`` if disabled / failed / unparsable."""
        if not self.enabled:
            return None
        user = user[:_MAX_PROMPT_CHARS]
        await self._limiter.acquire()
        async with self._semaphore:
            try:
                res = await self._get_client().chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )
            except Exception as exc:  # network, auth, rate-limit after SDK retries
                logger.warning("LLM call failed: %s", exc)
                return None
        content = (res.choices[0].message.content or "").strip()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("LLM returned non-JSON content (%d chars)", len(content))
            return None
        return data if isinstance(data, dict) else None


_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm


def reset_llm() -> None:
    """Drop the cached client (tests / settings reload)."""
    global _llm
    _llm = None
