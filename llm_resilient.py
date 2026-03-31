"""
ResilientLLM — Multi-provider LLM client with failover and circuit breaker.

Providers (in order):
  1. Groq            (primary)      — llama-3.x  via api.groq.com
  2. Anthropic/Claude (fallback 1)  — claude-haiku via api.anthropic.com
  3. OpenAI GPT      (fallback 2)   — gpt-4o-mini  via api.openai.com

Failover triggers : timeout >3s, HTTP 429, HTTP 5xx
Circuit breaker   : 3 consecutive Groq failures → block for 10 minutes

Design note — groq_caller injection
------------------------------------
When constructed with ``groq_caller=_groq`` (as done in crag_pipeline.py),
Groq HTTP requests are delegated to the existing _groq() function, which uses
``crag_pipeline.requests.post``.  This keeps unit-test mocks that patch
``crag_pipeline.requests.post`` fully functional without any changes to the
test suite.

When constructed without a groq_caller (standalone use), a direct HTTP call
with timeout=_TIMEOUT is made instead.
"""

import os
import json
import requests
from datetime import datetime, timedelta


# ─────────────────────────────────────────────────────────────────────────────
# Internal sentinel
# ─────────────────────────────────────────────────────────────────────────────

class _ProviderError(Exception):
    """Signals a retryable provider failure (timeout, rate-limit, server error)."""
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


# ─────────────────────────────────────────────────────────────────────────────
# Structured fallback logger
# ─────────────────────────────────────────────────────────────────────────────

def _log_fallback(provider: str, reason: str, next_action: str = "") -> None:
    """Emits a structured JSON log line on stdout when a provider falls back."""
    print(json.dumps({
        "event":     "llm_fallback",
        "provider":  provider,
        "reason":    reason,
        "next":      next_action,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }), flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# ResilientLLM
# ─────────────────────────────────────────────────────────────────────────────

class ResilientLLM:
    """
    Multi-provider LLM wrapper with automatic failover and a per-Groq
    circuit breaker.

    >>> llm = ResilientLLM()
    >>> text = llm.call([{"role": "user", "content": "Hello"}])
    """

    _TIMEOUT             = 3     # seconds — direct HTTP timeout / failover threshold
    _GROQ_FAIL_THRESHOLD = 3     # consecutive failures before opening circuit
    _GROQ_BLOCK_SECS     = 600   # circuit-open duration (10 minutes)

    _ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
    _OPENAI_MODEL    = "gpt-4o-mini"

    def __init__(self, groq_caller=None):
        """
        Parameters
        ----------
        groq_caller : callable, optional
            A function with the signature:
                groq_caller(messages, system="", max_tokens=800, model="...") -> str
            When provided, ResilientLLM delegates Groq calls to it.
            Pass ``_groq`` from crag_pipeline to preserve test-mock compatibility.
            When None, a direct HTTP call with _TIMEOUT is used.
        """
        self._groq_caller = groq_caller
        self._groq_failures: int = 0
        self._groq_blocked_until: datetime | None = None

    # ── circuit breaker ──────────────────────────────────────────────────────

    def _circuit_is_open(self) -> bool:
        """Return True if Groq is blocked by the circuit breaker."""
        if self._groq_blocked_until is None:
            return False
        if datetime.now() >= self._groq_blocked_until:
            # Auto-reset after block period expires
            self._groq_blocked_until = None
            self._groq_failures = 0
            return False
        return True

    def _record_groq_failure(self) -> None:
        self._groq_failures += 1
        if self._groq_failures >= self._GROQ_FAIL_THRESHOLD:
            self._groq_blocked_until = datetime.now() + timedelta(seconds=self._GROQ_BLOCK_SECS)
            _log_fallback(
                "groq", "circuit_open",
                f"blocked {self._GROQ_BLOCK_SECS}s after "
                f"{self._GROQ_FAIL_THRESHOLD} consecutive failures",
            )

    def _record_groq_success(self) -> None:
        self._groq_failures = 0
        self._groq_blocked_until = None

    # ── Groq provider ────────────────────────────────────────────────────────

    def _call_groq(self, messages: list, system: str, max_tokens: int,
                   model: str) -> str:
        """
        Invoke Groq. Delegates to the injected groq_caller when available
        (test-mock-safe path); otherwise makes a direct HTTP call.
        """
        if self._groq_caller is not None:
            result = self._groq_caller(
                messages,
                system=system,
                max_tokens=max_tokens,
                model=model,
            )
            # _groq() signals errors via "❌ ..." return strings (never raises)
            if isinstance(result, str) and result.startswith("❌"):
                raise _ProviderError(result)
            return result

        # ── direct HTTP (standalone / no groq_caller injected) ────────────
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise _ProviderError("GROQ_API_KEY not configured")

        full_messages = (
            [{"role": "system", "content": system}] if system else []
        ) + messages
        payload = {
            "model":       model,
            "messages":    full_messages,
            "max_tokens":  max_tokens,
            "temperature": 0.05,
        }
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json=payload,
                timeout=self._TIMEOUT,
            )
        except requests.exceptions.Timeout:
            raise _ProviderError(f"timeout >{self._TIMEOUT}s")
        except Exception as exc:
            raise _ProviderError(str(exc))

        if r.status_code == 429 or r.status_code >= 500:
            raise _ProviderError(f"HTTP {r.status_code}", status_code=r.status_code)
        if r.status_code != 200:
            raise _ProviderError(
                f"HTTP {r.status_code}: {r.text[:200]}", status_code=r.status_code
            )
        return r.json()["choices"][0]["message"]["content"]

    # ── Anthropic provider ───────────────────────────────────────────────────

    def _call_anthropic(self, messages: list, system: str, max_tokens: int) -> str:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise _ProviderError("ANTHROPIC_API_KEY not configured")

        payload: dict = {
            "model":      self._ANTHROPIC_MODEL,
            "max_tokens": max_tokens,
            "messages":   messages,
        }
        if system:
            payload["system"] = system

        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key":         api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type":      "application/json",
                },
                json=payload,
                timeout=self._TIMEOUT,
            )
        except requests.exceptions.Timeout:
            raise _ProviderError(f"timeout >{self._TIMEOUT}s")
        except Exception as exc:
            raise _ProviderError(str(exc))

        if r.status_code == 429 or r.status_code >= 500:
            raise _ProviderError(f"HTTP {r.status_code}", status_code=r.status_code)
        if r.status_code != 200:
            raise _ProviderError(
                f"HTTP {r.status_code}: {r.text[:200]}", status_code=r.status_code
            )
        return r.json()["content"][0]["text"]

    # ── OpenAI provider ──────────────────────────────────────────────────────

    def _call_openai(self, messages: list, system: str, max_tokens: int) -> str:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise _ProviderError("OPENAI_API_KEY not configured")

        full_messages = (
            [{"role": "system", "content": system}] if system else []
        ) + messages
        payload = {
            "model":       self._OPENAI_MODEL,
            "messages":    full_messages,
            "max_tokens":  max_tokens,
            "temperature": 0.05,
        }
        try:
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json=payload,
                timeout=self._TIMEOUT,
            )
        except requests.exceptions.Timeout:
            raise _ProviderError(f"timeout >{self._TIMEOUT}s")
        except Exception as exc:
            raise _ProviderError(str(exc))

        if r.status_code == 429 or r.status_code >= 500:
            raise _ProviderError(f"HTTP {r.status_code}", status_code=r.status_code)
        if r.status_code != 200:
            raise _ProviderError(
                f"HTTP {r.status_code}: {r.text[:200]}", status_code=r.status_code
            )
        return r.json()["choices"][0]["message"]["content"]

    # ── main entry point ─────────────────────────────────────────────────────

    def call(self, messages: list, system: str = "", max_tokens: int = 1000,
             model: str = None) -> str:
        """
        Call the best available provider and return the text response.

        Parameters
        ----------
        messages   : list[dict] — OpenAI-compatible message list
        system     : system prompt (empty string → no system message)
        max_tokens : maximum tokens for the response
        model      : Groq model name override; ignored by Anthropic/OpenAI fallbacks

        Returns
        -------
        str — LLM response text, or "❌ ..." if every provider fails.
        """
        groq_model = model or "llama-3.3-70b-versatile"

        # ── 1. Groq — primary ────────────────────────────────────────────────
        if self._circuit_is_open():
            _log_fallback("groq", "circuit_open", "skipping to anthropic")
        else:
            try:
                text = self._call_groq(messages, system, max_tokens, groq_model)
                self._record_groq_success()
                return text
            except _ProviderError as exc:
                self._record_groq_failure()
                _log_fallback("groq", str(exc), "trying anthropic")

        # ── 2. Anthropic — fallback 1 ────────────────────────────────────────
        try:
            text = self._call_anthropic(messages, system, max_tokens)
            return text
        except _ProviderError as exc:
            if "not configured" not in str(exc):
                _log_fallback("anthropic", str(exc), "trying openai")

        # ── 3. OpenAI — fallback 2 ───────────────────────────────────────────
        try:
            text = self._call_openai(messages, system, max_tokens)
            return text
        except _ProviderError as exc:
            if "not configured" not in str(exc):
                _log_fallback("openai", str(exc), "all providers exhausted")

        return (
            "❌ Todos os providers LLM falharam. "
            "Verifique as API keys (GROQ_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY) "
            "e a conectividade de rede."
        )
