"""SmartRouter — Core Engine.

Task classification, circuit breaker, unified LLM client, and routing logic.
All providers use OpenAI-compatible API — only base_url and api_key change.

Usage:
    from smartrouter import SmartRouter

    router = SmartRouter()
    result = await router.route("Implement a Pydantic schema for IntelItem")
    print(result.response)
    print(f"Provider: {result.provider_used}, Latency: {result.latency_ms}ms")
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from dotenv import load_dotenv
load_dotenv()
from collections import defaultdict
from typing import Optional

from openai import AsyncOpenAI

from .config import (
    CLASSIFICATION_KEYWORDS,
    COST_PER_MILLION_TOKENS,
    PROVIDERS,
    ROUTING_RULES,
)
from .schemas import (
    Complexity,
    ProviderConfig,
    ProviderID,
    ProviderStatus,
    RoutingResult,
    TaskClassification,
    TaskType,
)

logger = logging.getLogger("smartrouter")


# ── Task Classifier (Phase 1: Rules-based) ──────────────────────────────────

class TaskClassifier:
    """Classifies tasks using keyword matching.

    Phase 1: Pure regex/heuristics. Fast, deterministic, zero API calls.
    Phase 2: Will add Cerebras LLM classification for ambiguous cases.
    """

    def classify(self, task: str) -> TaskClassification:
        task_lower = task.lower()
        scores: dict[TaskType, int] = defaultdict(int)

        for task_type, keywords in CLASSIFICATION_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in task_lower:
                    scores[task_type] += 1

        # Pick highest scoring type, or GENERAL as fallback
        if scores:
            best_type = max(scores, key=scores.get)
            max_score = scores[best_type]
            confidence = min(1.0, max_score / 3.0)  # 3+ keywords = full confidence
        else:
            best_type = TaskType.GENERAL
            confidence = 0.5

        # Estimate complexity from task length and keywords
        complexity = self._estimate_complexity(task_lower)

        # Check for sensitive data indicators
        has_sensitive = scores.get(TaskType.SENSITIVE_DATA, 0) > 0
        if has_sensitive and best_type != TaskType.SENSITIVE_DATA:
            # Override: sensitive data always takes priority
            best_type = TaskType.SENSITIVE_DATA
            confidence = 1.0

        # Check for long context indicators
        requires_long_ctx = scores.get(TaskType.LONG_CONTEXT, 0) > 0

        # Estimate tokens (rough heuristic)
        estimated_tokens = min(8000, max(500, len(task.split()) * 50))

        return TaskClassification(
            task_type=best_type,
            complexity=complexity,
            requires_long_context=requires_long_ctx,
            has_sensitive_data=has_sensitive,
            estimated_tokens=estimated_tokens,
            confidence=confidence,
        )

    def _estimate_complexity(self, task_lower: str) -> Complexity:
        high_indicators = [
            "pipeline", "orchestrat", "multi-step", "langgraph",
            "integration", "integração", "refactor", "migrate",
        ]
        medium_indicators = [
            "implement", "class", "module", "test", "agent",
        ]

        if any(kw in task_lower for kw in high_indicators):
            return Complexity.HIGH
        if any(kw in task_lower for kw in medium_indicators):
            return Complexity.MEDIUM
        return Complexity.LOW


# ── Circuit Breaker ──────────────────────────────────────────────────────────

class CircuitBreaker:
    """Per-provider circuit breaker.

    After `failure_threshold` consecutive failures, the provider is blocked
    for `recovery_timeout` seconds. Prevents cascading failures.

    Pattern: Closed → Open (after N failures) → Half-Open (after timeout) → Closed
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 600.0,  # 10 minutes
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures: dict[ProviderID, int] = defaultdict(int)
        self._last_failure_time: dict[ProviderID, float] = {}
        self._open_circuits: set[ProviderID] = set()

    def is_available(self, provider_id: ProviderID) -> bool:
        """Check if provider circuit is closed (available)."""
        if provider_id not in self._open_circuits:
            return True

        # Check if recovery timeout has elapsed (half-open)
        last_fail = self._last_failure_time.get(provider_id, 0)
        if time.time() - last_fail > self.recovery_timeout:
            logger.info(f"Circuit half-open for {provider_id.value}, allowing retry")
            self._open_circuits.discard(provider_id)
            self._failures[provider_id] = 0
            return True

        return False

    def record_success(self, provider_id: ProviderID) -> None:
        """Reset failure count on success."""
        self._failures[provider_id] = 0
        self._open_circuits.discard(provider_id)

    def record_failure(self, provider_id: ProviderID) -> None:
        """Record failure and potentially open circuit."""
        self._failures[provider_id] += 1
        self._last_failure_time[provider_id] = time.time()

        if self._failures[provider_id] >= self.failure_threshold:
            self._open_circuits.add(provider_id)
            logger.warning(
                f"Circuit OPEN for {provider_id.value} "
                f"({self._failures[provider_id]} consecutive failures). "
                f"Blocked for {self.recovery_timeout}s."
            )

    def get_status(self) -> dict[str, str]:
        """Return circuit status for all providers — for observability."""
        status = {}
        for pid in ProviderID:
            if pid in self._open_circuits:
                status[pid.value] = "OPEN (blocked)"
            elif self._failures.get(pid, 0) > 0:
                status[pid.value] = f"CLOSED ({self._failures[pid]} failures)"
            else:
                status[pid.value] = "CLOSED (healthy)"
        return status


# ── Unified LLM Client ──────────────────────────────────────────────────────

class UnifiedClient:
    """Single OpenAI SDK client that works with all 9 providers.

    The key insight: all providers are OpenAI-compatible.
    We only swap base_url and api_key. Zero code duplication.
    """

    def _get_client(self, config: ProviderConfig) -> AsyncOpenAI:
        """Create an AsyncOpenAI client for the given provider."""
        api_key = os.environ.get(config.api_key_env, "no-key-needed")

        # Special handling for providers that need different auth
        if config.id == ProviderID.GEMINI:
            # Gemini uses x-goog-api-key, but OpenAI compat wraps it
            api_key = os.environ.get(config.api_key_env, "")

        return AsyncOpenAI(
            base_url=config.base_url,
            api_key=api_key,
            timeout=config.timeout_seconds,
        )

    async def call(
        self,
        config: ProviderConfig,
        messages: list[dict],
        system_prompt: Optional[str] = None,
    ) -> tuple[str, int]:
        """Call any provider and return (response_text, tokens_used).

        Raises:
            TimeoutError: If provider exceeds timeout.
            Exception: Any other API error.
        """
        client = self._get_client(config)

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=config.model,
                    messages=full_messages,
                    max_tokens=config.max_tokens,
                    temperature=config.temperature,
                ),
                timeout=config.timeout_seconds,
            )

            text = response.choices[0].message.content or ""
            tokens = response.usage.total_tokens if response.usage else 0
            return text, tokens

        except asyncio.TimeoutError:
            raise TimeoutError(
                f"{config.id.value} timeout after {config.timeout_seconds}s"
            )


# ── Routing Engine ───────────────────────────────────────────────────────────

class RoutingEngine:
    """Maps TaskClassification → ProviderID using routing rules."""

    def __init__(self, rules: list[RoutingRule] | None = None):
        self._rules = {r.task_type: r for r in (rules or ROUTING_RULES)}

    def select(
        self,
        classification: TaskClassification,
        circuit_breaker: CircuitBreaker,
    ) -> tuple[ProviderID, bool]:
        """Select provider. Returns (provider_id, is_fallback).

        If primary circuit is open, returns fallback.
        If both are open, returns GROQ as emergency fallback.
        """
        rule = self._rules.get(classification.task_type)
        if not rule:
            rule = self._rules[TaskType.GENERAL]

        # Try primary
        if circuit_breaker.is_available(rule.primary):
            return rule.primary, False

        # Try fallback
        logger.info(
            f"Primary {rule.primary.value} unavailable, "
            f"falling back to {rule.fallback.value}"
        )
        if circuit_breaker.is_available(rule.fallback):
            return rule.fallback, True

        # Emergency: Groq as universal fallback
        logger.warning(
            f"Both {rule.primary.value} and {rule.fallback.value} unavailable. "
            "Emergency fallback to Groq."
        )
        return ProviderID.GROQ, True


# ── SmartRouter (Main API) ───────────────────────────────────────────────────

class SmartRouter:
    """Multi-LLM orchestrator with competency-based routing.

    Usage:
        router = SmartRouter()
        result = await router.route("Implement a Pydantic schema for IntelItem")
        print(result.response)

    Or with explicit task type override:
        result = await router.route(
            "Analyze this codebase",
            force_type=TaskType.LONG_CONTEXT,
        )
    """

    def __init__(
        self,
        providers: dict[str, ProviderConfig] | None = None,
        rules: list[RoutingRule] | None = None,
        failure_threshold: int = 3,
        recovery_timeout: float = 600.0,
    ):
        self.providers = providers or PROVIDERS
        self.classifier = TaskClassifier()
        self.routing_engine = RoutingEngine(rules)
        self.circuit_breaker = CircuitBreaker(failure_threshold, recovery_timeout)
        self.client = UnifiedClient()
        self._history: list[RoutingResult] = []

    async def route(
        self,
        task: str,
        system_prompt: Optional[str] = None,
        force_type: Optional[TaskType] = None,
        force_provider: Optional[ProviderID] = None,
    ) -> RoutingResult:
        """Route a task to the best LLM provider and return the result.

        Args:
            task: The task description / prompt.
            system_prompt: Optional system prompt prepended to messages.
            force_type: Override automatic classification.
            force_provider: Skip routing, use this provider directly.

        Returns:
            RoutingResult with response, provider info, latency, cost.
        """
        # Step 1: Classify
        if force_type:
            classification = TaskClassification(
                task_type=force_type,
                complexity=Complexity.MEDIUM,
                confidence=1.0,
            )
        else:
            classification = self.classifier.classify(task)

        logger.info(
            f"Classification: {classification.task_type.value} "
            f"(confidence={classification.confidence:.2f})"
        )

        # Step 2: Route
        if force_provider:
            provider_id = force_provider
            is_fallback = False
        else:
            provider_id, is_fallback = self.routing_engine.select(
                classification, self.circuit_breaker
            )

        config = self.providers.get(provider_id)
        if not config or not config.enabled:
            # Shouldn't happen, but safety first
            config = self.providers[ProviderID.GROQ]
            provider_id = ProviderID.GROQ
            is_fallback = True

        logger.info(
            f"Routing to {provider_id.value} "
            f"({'fallback' if is_fallback else 'primary'})"
        )

        # Step 3: Call
        messages = [{"role": "user", "content": task}]
        start_time = time.time()

        try:
            response_text, tokens_used = await self.client.call(
                config, messages, system_prompt
            )
            latency_ms = (time.time() - start_time) * 1000

            self.circuit_breaker.record_success(provider_id)

            # Estimate cost
            cost_rates = COST_PER_MILLION_TOKENS.get(
                provider_id, {"input": 0, "output": 0}
            )
            cost_estimate = (tokens_used / 1_000_000) * (
                cost_rates["input"] + cost_rates["output"]
            ) / 2  # rough average

            result = RoutingResult(
                task_input=task[:200],       # truncate for logging
                classification=classification,
                provider_used=provider_id,
                was_fallback=is_fallback,
                status=ProviderStatus.OK,
                response=response_text,
                latency_ms=round(latency_ms, 1),
                tokens_used=tokens_used,
                cost_estimate_usd=round(cost_estimate, 6),
            )

        except TimeoutError as e:
            latency_ms = (time.time() - start_time) * 1000
            self.circuit_breaker.record_failure(provider_id)
            logger.warning(f"Timeout on {provider_id.value}: {e}")

            result = RoutingResult(
                task_input=task[:200],
                classification=classification,
                provider_used=provider_id,
                was_fallback=is_fallback,
                status=ProviderStatus.TIMEOUT,
                latency_ms=round(latency_ms, 1),
                error_message=str(e),
            )

            # Auto-retry with fallback if not already on fallback
            if not is_fallback and not force_provider:
                logger.info("Auto-retrying with fallback provider...")
                return await self.route(
                    task,
                    system_prompt=system_prompt,
                    force_type=classification.task_type,
                    force_provider=self.routing_engine.select(
                        classification, self.circuit_breaker
                    )[0],
                )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self.circuit_breaker.record_failure(provider_id)
            logger.error(f"Error on {provider_id.value}: {e}")

            result = RoutingResult(
                task_input=task[:200],
                classification=classification,
                provider_used=provider_id,
                was_fallback=is_fallback,
                status=ProviderStatus.ERROR,
                latency_ms=round(latency_ms, 1),
                error_message=str(e),
            )

            # Auto-retry with fallback
            if not is_fallback and not force_provider:
                logger.info("Auto-retrying with fallback provider...")
                return await self.route(
                    task,
                    system_prompt=system_prompt,
                    force_type=classification.task_type,
                    force_provider=self.routing_engine.select(
                        classification, self.circuit_breaker
                    )[0],
                )

        self._history.append(result)
        return result

    # ── Observability ────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return routing statistics for dashboard / LangSmith."""
        if not self._history:
            return {"total_requests": 0}

        by_provider: dict[str, list[RoutingResult]] = defaultdict(list)
        for r in self._history:
            by_provider[r.provider_used.value].append(r)

        stats = {
            "total_requests": len(self._history),
            "total_cost_usd": sum(r.cost_estimate_usd for r in self._history),
            "fallback_rate": sum(
                1 for r in self._history if r.was_fallback
            ) / len(self._history),
            "avg_latency_ms": sum(
                r.latency_ms for r in self._history
            ) / len(self._history),
            "by_provider": {
                pid: {
                    "count": len(results),
                    "avg_latency_ms": sum(r.latency_ms for r in results) / len(results),
                    "errors": sum(
                        1 for r in results if r.status != ProviderStatus.OK
                    ),
                }
                for pid, results in by_provider.items()
            },
            "circuit_breaker": self.circuit_breaker.get_status(),
        }
        return stats

    def get_history(self, last_n: int = 10) -> list[RoutingResult]:
        """Return last N routing results."""
        return self._history[-last_n:]
