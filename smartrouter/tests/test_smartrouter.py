"""SmartRouter — Tests.

Run: pytest tests/test_smartrouter.py -v
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from smartrouter import (
    SmartRouter,
    TaskClassifier,
    CircuitBreaker,
    RoutingEngine,
    TaskType,
    Complexity,
    ProviderID,
    ProviderStatus,
    TaskClassification,
)


# ── TaskClassifier Tests ─────────────────────────────────────────────────────

class TestTaskClassifier:
    def setup_method(self):
        self.classifier = TaskClassifier()

    def test_coding_complex(self):
        result = self.classifier.classify(
            "Implement a LangGraph pipeline with multi-step orchestration"
        )
        assert result.task_type == TaskType.CODING_COMPLEX

    def test_coding_clean(self):
        result = self.classifier.classify(
            "Create a Pydantic schema and pytest tests for IntelItem"
        )
        assert result.task_type == TaskType.CODING_CLEAN

    def test_validation(self):
        result = self.classifier.classify(
            "Quick validate and classify this output"
        )
        assert result.task_type == TaskType.VALIDATION

    def test_long_context(self):
        result = self.classifier.classify(
            "Analyze the entire codebase and consolidate all files"
        )
        assert result.task_type == TaskType.LONG_CONTEXT

    def test_deep_reasoning(self):
        result = self.classifier.classify(
            "Debug the root cause of this edge case logic error"
        )
        assert result.task_type == TaskType.DEEP_REASONING

    def test_architecture(self):
        result = self.classifier.classify(
            "Review the architecture and design pattern for Qdrant integration"
        )
        assert result.task_type == TaskType.ARCHITECTURE

    def test_sensitive_data_override(self):
        """Sensitive data should ALWAYS override other classifications."""
        result = self.classifier.classify(
            "Implement a module to process CPF and LGPD employee data"
        )
        assert result.task_type == TaskType.SENSITIVE_DATA
        assert result.has_sensitive_data is True

    def test_iteration(self):
        result = self.classifier.classify(
            "Draft and explore different prompt experiments"
        )
        assert result.task_type == TaskType.ITERATION

    def test_general_fallback(self):
        result = self.classifier.classify("Hello, how are you?")
        assert result.task_type == TaskType.GENERAL

    def test_portuguese_keywords(self):
        result = self.classifier.classify(
            "Implementar um módulo para orquestrar agentes"
        )
        assert result.task_type == TaskType.CODING_COMPLEX

    def test_complexity_high(self):
        result = self.classifier.classify(
            "Refactor and migrate the entire pipeline integration"
        )
        assert result.complexity == Complexity.HIGH

    def test_complexity_medium(self):
        result = self.classifier.classify(
            "Implement a new class for the agent module"
        )
        assert result.complexity == Complexity.MEDIUM

    def test_complexity_low(self):
        result = self.classifier.classify("What is the weather today?")
        assert result.complexity == Complexity.LOW

    def test_confidence_high_with_many_keywords(self):
        result = self.classifier.classify(
            "Implement a LangGraph pipeline to orchestrate multi-step agents"
        )
        assert result.confidence >= 0.9

    def test_confidence_low_with_few_keywords(self):
        result = self.classifier.classify("Try something new")
        assert result.confidence < 1.0


# ── CircuitBreaker Tests ─────────────────────────────────────────────────────

class TestCircuitBreaker:
    def setup_method(self):
        self.cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)

    def test_initially_available(self):
        assert self.cb.is_available(ProviderID.KIMI) is True

    def test_opens_after_threshold(self):
        for _ in range(3):
            self.cb.record_failure(ProviderID.KIMI)
        assert self.cb.is_available(ProviderID.KIMI) is False

    def test_resets_on_success(self):
        self.cb.record_failure(ProviderID.KIMI)
        self.cb.record_failure(ProviderID.KIMI)
        self.cb.record_success(ProviderID.KIMI)
        assert self.cb.is_available(ProviderID.KIMI) is True

    def test_other_providers_unaffected(self):
        for _ in range(3):
            self.cb.record_failure(ProviderID.KIMI)
        assert self.cb.is_available(ProviderID.QWEN) is True

    def test_status_report(self):
        self.cb.record_failure(ProviderID.GROQ)
        status = self.cb.get_status()
        assert "1 failures" in status[ProviderID.GROQ.value]

    def test_half_open_after_timeout(self):
        """After recovery_timeout, circuit should be half-open."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.0)
        cb.record_failure(ProviderID.KIMI)
        # With timeout=0, should immediately be available again
        assert cb.is_available(ProviderID.KIMI) is True


# ── RoutingEngine Tests ──────────────────────────────────────────────────────

class TestRoutingEngine:
    def setup_method(self):
        self.engine = RoutingEngine()
        self.cb = CircuitBreaker(failure_threshold=3)

    def test_coding_complex_routes_to_kimi(self):
        classification = TaskClassification(
            task_type=TaskType.CODING_COMPLEX,
            complexity=Complexity.HIGH,
        )
        provider, is_fallback = self.engine.select(classification, self.cb)
        assert provider == ProviderID.KIMI
        assert is_fallback is False

    def test_validation_routes_to_cerebras(self):
        classification = TaskClassification(
            task_type=TaskType.VALIDATION,
            complexity=Complexity.LOW,
        )
        provider, _ = self.engine.select(classification, self.cb)
        assert provider == ProviderID.CEREBRAS

    def test_architecture_routes_to_claude(self):
        classification = TaskClassification(
            task_type=TaskType.ARCHITECTURE,
            complexity=Complexity.HIGH,
        )
        provider, _ = self.engine.select(classification, self.cb)
        assert provider == ProviderID.CLAUDE

    def test_sensitive_data_routes_to_ollama(self):
        classification = TaskClassification(
            task_type=TaskType.SENSITIVE_DATA,
            complexity=Complexity.MEDIUM,
            has_sensitive_data=True,
        )
        provider, _ = self.engine.select(classification, self.cb)
        assert provider == ProviderID.OLLAMA

    def test_fallback_when_primary_down(self):
        """When primary circuit is open, should use fallback."""
        for _ in range(3):
            self.cb.record_failure(ProviderID.KIMI)

        classification = TaskClassification(
            task_type=TaskType.CODING_COMPLEX,
            complexity=Complexity.HIGH,
        )
        provider, is_fallback = self.engine.select(classification, self.cb)
        assert provider == ProviderID.QWEN
        assert is_fallback is True

    def test_emergency_fallback_to_groq(self):
        """When both primary and fallback are down, use Groq."""
        for _ in range(3):
            self.cb.record_failure(ProviderID.KIMI)
            self.cb.record_failure(ProviderID.QWEN)

        classification = TaskClassification(
            task_type=TaskType.CODING_COMPLEX,
            complexity=Complexity.HIGH,
        )
        provider, is_fallback = self.engine.select(classification, self.cb)
        assert provider == ProviderID.GROQ
        assert is_fallback is True

    def test_long_context_routes_to_gemini(self):
        classification = TaskClassification(
            task_type=TaskType.LONG_CONTEXT,
            complexity=Complexity.MEDIUM,
            requires_long_context=True,
        )
        provider, _ = self.engine.select(classification, self.cb)
        assert provider == ProviderID.GEMINI

    def test_deep_reasoning_routes_to_deepseek(self):
        classification = TaskClassification(
            task_type=TaskType.DEEP_REASONING,
            complexity=Complexity.HIGH,
        )
        provider, _ = self.engine.select(classification, self.cb)
        assert provider == ProviderID.DEEPSEEK


# ── Integration Tests (mocked API) ──────────────────────────────────────────

class TestSmartRouterIntegration:
    def setup_method(self):
        self.router = SmartRouter()

    @pytest.mark.asyncio
    async def test_full_route_mocked(self):
        """Full routing pipeline with mocked API call."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated code here"
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 500

        with patch.object(
            self.router.client, "call",
            new_callable=AsyncMock,
            return_value=("Generated code here", 500),
        ):
            result = await self.router.route(
                "Implement a Pydantic schema for IntelItem"
            )

        assert result.status == ProviderStatus.OK
        assert result.response == "Generated code here"
        assert result.tokens_used == 500
        assert result.classification.task_type == TaskType.CODING_CLEAN

    @pytest.mark.asyncio
    async def test_force_provider(self):
        """Force a specific provider, bypassing routing."""
        with patch.object(
            self.router.client, "call",
            new_callable=AsyncMock,
            return_value=("Response from Claude", 100),
        ):
            result = await self.router.route(
                "Simple question",
                force_provider=ProviderID.CLAUDE,
            )

        assert result.provider_used == ProviderID.CLAUDE

    @pytest.mark.asyncio
    async def test_force_type(self):
        """Force a task type, bypassing classification."""
        with patch.object(
            self.router.client, "call",
            new_callable=AsyncMock,
            return_value=("Response", 100),
        ):
            result = await self.router.route(
                "Do something",
                force_type=TaskType.ARCHITECTURE,
            )

        assert result.classification.task_type == TaskType.ARCHITECTURE
        assert result.provider_used == ProviderID.CLAUDE

    @pytest.mark.asyncio
    async def test_timeout_triggers_fallback(self):
        """Timeout on primary should auto-retry with fallback."""
        call_count = 0

        async def mock_call(config, messages, system_prompt=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("Kimi timeout")
            return ("Fallback response", 200)

        with patch.object(self.router.client, "call", side_effect=mock_call):
            result = await self.router.route(
                "Implement a LangGraph pipeline orchestration"
            )

        # Should have retried and succeeded
        assert result.status == ProviderStatus.OK
        assert result.response == "Fallback response"

    def test_stats_empty(self):
        stats = self.router.get_stats()
        assert stats["total_requests"] == 0

    @pytest.mark.asyncio
    async def test_stats_after_requests(self):
        with patch.object(
            self.router.client, "call",
            new_callable=AsyncMock,
            return_value=("Ok", 100),
        ):
            await self.router.route("Test task 1")
            await self.router.route("Test task 2")

        stats = self.router.get_stats()
        assert stats["total_requests"] == 2

    def test_history(self):
        assert self.router.get_history() == []


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
