"""SmartRouter Adapter — Tests.

Run: pytest smartrouter/tests/test_adapter.py -v

Covers:
- SmartRouterLLM._generate() invokes SmartRouter.route() correctly
- LangChain message conversion (System/Human/AI → task + system_prompt)
- task_type mapping resolves to correct TaskType enum
- force_provider bypass works end-to-end
- create_eii_llms() returns correct structure and shared circuit breaker
- Async path (_agenerate) works with pytest-asyncio
- Error handling for empty responses
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from smartrouter import SmartRouter, TaskType, ProviderID, ProviderStatus
from smartrouter.adapter import SmartRouterLLM, _lc_messages_to_task
from smartrouter.eii_integration import create_eii_llms, EII_AGENT_TASK_TYPES
from smartrouter.schemas import (
    Complexity,
    RoutingResult,
    TaskClassification,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_routing_result(
    response: str = "Mocked LLM response",
    provider: ProviderID = ProviderID.GROQ,
    task_type: TaskType = TaskType.GENERAL,
    was_fallback: bool = False,
    tokens: int = 150,
) -> RoutingResult:
    """Build a RoutingResult with sensible defaults for tests."""
    return RoutingResult(
        task_input="test task",
        classification=TaskClassification(
            task_type=task_type,
            complexity=Complexity.MEDIUM,
        ),
        provider_used=provider,
        was_fallback=was_fallback,
        status=ProviderStatus.OK,
        response=response,
        latency_ms=42.0,
        tokens_used=tokens,
        cost_estimate_usd=0.0,
    )


# ── _lc_messages_to_task ──────────────────────────────────────────────────────

class TestLcMessagesToTask:
    def test_human_message_becomes_task(self):
        task, sys = _lc_messages_to_task([HumanMessage(content="Hello")])
        assert task == "Hello"
        assert sys is None

    def test_system_message_extracted(self):
        task, sys = _lc_messages_to_task([
            SystemMessage(content="You are a bot."),
            HumanMessage(content="Hi"),
        ])
        assert task == "Hi"
        assert sys == "You are a bot."

    def test_ai_message_prefixed(self):
        task, sys = _lc_messages_to_task([
            HumanMessage(content="Question"),
            AIMessage(content="Answer"),
            HumanMessage(content="Follow-up"),
        ])
        assert "Assistant: Answer" in task
        assert "Question" in task
        assert "Follow-up" in task

    def test_only_system_message_returns_empty_task(self):
        task, sys = _lc_messages_to_task([SystemMessage(content="Sys only")])
        assert task == ""
        assert sys == "Sys only"

    def test_first_system_message_wins(self):
        """Only the first SystemMessage should become system_prompt."""
        task, sys = _lc_messages_to_task([
            SystemMessage(content="First"),
            SystemMessage(content="Second"),
            HumanMessage(content="Q"),
        ])
        assert sys == "First"

    def test_empty_messages_returns_empty_strings(self):
        task, sys = _lc_messages_to_task([])
        assert task == ""
        assert sys is None

    def test_multiple_human_messages_joined(self):
        task, _ = _lc_messages_to_task([
            HumanMessage(content="Part 1"),
            HumanMessage(content="Part 2"),
        ])
        assert task == "Part 1\nPart 2"


# ── SmartRouterLLM construction ───────────────────────────────────────────────

class TestSmartRouterLLMInit:
    def test_default_creates_new_router(self):
        llm = SmartRouterLLM()
        assert isinstance(llm.router, SmartRouter)
        assert llm.task_type is None
        assert llm.force_provider is None

    def test_task_type_stored(self):
        llm = SmartRouterLLM(task_type="deep_reasoning")
        assert llm.task_type == "deep_reasoning"

    def test_force_provider_stored(self):
        llm = SmartRouterLLM(force_provider="groq")
        assert llm.force_provider == "groq"

    def test_shared_router_accepted(self):
        router = SmartRouter()
        llm = SmartRouterLLM(router=router)
        assert llm.router is router

    def test_llm_type(self):
        assert SmartRouterLLM()._llm_type == "smartrouter"

    def test_invalid_task_type_raises(self):
        llm = SmartRouterLLM(task_type="not_a_real_type")
        with pytest.raises(ValueError, match="Unknown task_type"):
            llm._resolve_task_type()

    def test_invalid_force_provider_raises(self):
        llm = SmartRouterLLM(force_provider="not_a_provider")
        with pytest.raises(ValueError, match="Unknown force_provider"):
            llm._resolve_force_provider()


# ── _resolve_task_type ────────────────────────────────────────────────────────

class TestResolveTaskType:
    @pytest.mark.parametrize("task_type_str,expected_enum", [
        ("deep_reasoning",  TaskType.DEEP_REASONING),
        ("validation",      TaskType.VALIDATION),
        ("general",         TaskType.GENERAL),
        ("sensitive_data",  TaskType.SENSITIVE_DATA),
        ("iteration",       TaskType.ITERATION),
        ("coding_complex",  TaskType.CODING_COMPLEX),
        ("coding_clean",    TaskType.CODING_CLEAN),
        ("long_context",    TaskType.LONG_CONTEXT),
        ("architecture",    TaskType.ARCHITECTURE),
    ])
    def test_all_valid_task_types(self, task_type_str, expected_enum):
        llm = SmartRouterLLM(task_type=task_type_str)
        assert llm._resolve_task_type() == expected_enum

    def test_none_returns_none(self):
        llm = SmartRouterLLM(task_type=None)
        assert llm._resolve_task_type() is None


# ── _generate (sync) ──────────────────────────────────────────────────────────

class TestGenerate:
    def _make_llm_with_mock_router(
        self,
        task_type: str = "general",
        routing_result: RoutingResult | None = None,
    ) -> tuple[SmartRouterLLM, AsyncMock]:
        """Return (llm, mock_route) ready for assertions."""
        result = routing_result or _make_routing_result()
        mock_route = AsyncMock(return_value=result)

        router = SmartRouter()
        router.route = mock_route  # type: ignore[method-assign]

        llm = SmartRouterLLM(task_type=task_type, router=router)
        return llm, mock_route

    def test_generate_returns_chat_result(self):
        llm, _ = self._make_llm_with_mock_router()
        result = llm.invoke([HumanMessage(content="Diagnose S-1200 error")])
        assert result.content == "Mocked LLM response"

    def test_generate_calls_route_with_task(self):
        llm, mock_route = self._make_llm_with_mock_router()
        llm.invoke([HumanMessage(content="Check this")])
        mock_route.assert_called_once()
        call_kwargs = mock_route.call_args.kwargs
        assert call_kwargs["task"] == "Check this"

    def test_generate_passes_system_prompt(self):
        llm, mock_route = self._make_llm_with_mock_router()
        llm.invoke([
            SystemMessage(content="You are EII."),
            HumanMessage(content="Analyze error"),
        ])
        call_kwargs = mock_route.call_args.kwargs
        assert call_kwargs["system_prompt"] == "You are EII."
        assert call_kwargs["task"] == "Analyze error"

    def test_generate_passes_force_type(self):
        llm, mock_route = self._make_llm_with_mock_router(task_type="validation")
        llm.invoke([HumanMessage(content="Validate this")])
        call_kwargs = mock_route.call_args.kwargs
        assert call_kwargs["force_type"] == TaskType.VALIDATION

    def test_generate_passes_none_force_type_when_not_set(self):
        llm, mock_route = self._make_llm_with_mock_router(task_type=None)
        llm.invoke([HumanMessage(content="Generic task")])
        call_kwargs = mock_route.call_args.kwargs
        assert call_kwargs["force_type"] is None

    def test_response_metadata_populated(self):
        result_obj = _make_routing_result(
            provider=ProviderID.DEEPSEEK,
            task_type=TaskType.DEEP_REASONING,
            was_fallback=False,
            tokens=300,
        )
        llm, _ = self._make_llm_with_mock_router(
            task_type="deep_reasoning", routing_result=result_obj
        )
        response = llm.invoke([HumanMessage(content="Debug root cause")])
        meta = response.response_metadata
        assert meta["provider"] == "deepseek"
        assert meta["task_type"] == "deep_reasoning"
        assert meta["was_fallback"] is False
        assert meta["tokens_used"] == 300

    def test_empty_response_raises_runtime_error(self):
        empty_result = RoutingResult(
            task_input="test",
            classification=TaskClassification(
                task_type=TaskType.GENERAL, complexity=Complexity.LOW
            ),
            provider_used=ProviderID.GROQ,
            status=ProviderStatus.ERROR,
            response="",           # empty!
            error_message="API down",
        )
        llm, _ = self._make_llm_with_mock_router(routing_result=empty_result)
        with pytest.raises(RuntimeError, match="empty response"):
            llm.invoke([HumanMessage(content="Anything")])

    def test_empty_user_content_raises_value_error(self):
        llm, _ = self._make_llm_with_mock_router()
        with pytest.raises(ValueError, match="no user content"):
            llm.invoke([SystemMessage(content="sys only")])


# ── force_provider bypass ─────────────────────────────────────────────────────

class TestForceProvider:
    def test_force_provider_passed_to_route(self):
        result = _make_routing_result(provider=ProviderID.CEREBRAS)
        mock_route = AsyncMock(return_value=result)

        router = SmartRouter()
        router.route = mock_route  # type: ignore[method-assign]

        llm = SmartRouterLLM(force_provider="cerebras", router=router)
        llm.invoke([HumanMessage(content="Validate output")])

        call_kwargs = mock_route.call_args.kwargs
        assert call_kwargs["force_provider"] == ProviderID.CEREBRAS

    def test_force_provider_none_when_not_set(self):
        mock_route = AsyncMock(return_value=_make_routing_result())
        router = SmartRouter()
        router.route = mock_route  # type: ignore[method-assign]

        llm = SmartRouterLLM(router=router)
        llm.invoke([HumanMessage(content="Task")])

        call_kwargs = mock_route.call_args.kwargs
        assert call_kwargs["force_provider"] is None


# ── Async path ────────────────────────────────────────────────────────────────

class TestAgenerate:
    """Tests for the async path (_agenerate / ainvoke).

    Uses asyncio.run() directly — no pytest-asyncio or anyio plugin required.
    """

    def test_agenerate_returns_chat_result(self):
        async def _run():
            result = _make_routing_result(response="Async response")
            mock_route = AsyncMock(return_value=result)
            router = SmartRouter()
            router.route = mock_route  # type: ignore[method-assign]

            llm = SmartRouterLLM(task_type="general", router=router)
            return await llm.ainvoke([HumanMessage(content="Async test")])

        response = asyncio.run(_run())
        assert response.content == "Async response"

    def test_agenerate_preserves_system_prompt(self):
        async def _run():
            mock_route = AsyncMock(return_value=_make_routing_result())
            router = SmartRouter()
            router.route = mock_route  # type: ignore[method-assign]

            llm = SmartRouterLLM(router=router)
            await llm.ainvoke([
                SystemMessage(content="Sys prompt"),
                HumanMessage(content="Question"),
            ])
            return mock_route.call_args.kwargs

        kwargs = asyncio.run(_run())
        assert kwargs["system_prompt"] == "Sys prompt"
        assert kwargs["task"] == "Question"


# ── create_eii_llms ───────────────────────────────────────────────────────────

class TestCreateEiiLlms:
    def test_returns_all_expected_agents(self):
        llms = create_eii_llms()
        assert set(llms.keys()) == set(EII_AGENT_TASK_TYPES.keys())

    def test_all_values_are_smartrouter_llm(self):
        llms = create_eii_llms()
        for name, llm in llms.items():
            assert isinstance(llm, SmartRouterLLM), f"{name} is not SmartRouterLLM"

    def test_task_types_correctly_assigned(self):
        llms = create_eii_llms()
        for agent, expected_type in EII_AGENT_TASK_TYPES.items():
            assert llms[agent].task_type == expected_type, (
                f"Agent '{agent}' has task_type '{llms[agent].task_type}', "
                f"expected '{expected_type}'"
            )

    def test_all_agents_share_same_router_instance(self):
        """Unified circuit breaker: all agents must reference the same router."""
        llms = create_eii_llms()
        routers = [llm.router for llm in llms.values()]
        first = routers[0]
        for router in routers[1:]:
            assert router is first, "Agents do not share the same SmartRouter instance"

    def test_custom_router_is_shared(self):
        """When a router is passed in, all agents use it."""
        custom_router = SmartRouter()
        llms = create_eii_llms(router=custom_router)
        for llm in llms.values():
            assert llm.router is custom_router

    def test_diagnostic_uses_deep_reasoning(self):
        llms = create_eii_llms()
        assert llms["diagnostic"].task_type == "deep_reasoning"

    def test_evaluator_uses_validation(self):
        llms = create_eii_llms()
        assert llms["evaluator"].task_type == "validation"

    def test_ingest_uses_sensitive_data(self):
        llms = create_eii_llms()
        assert llms["ingest"].task_type == "sensitive_data"

    def test_mentor_uses_iteration(self):
        llms = create_eii_llms()
        assert llms["mentor"].task_type == "iteration"

    def test_escalation_uses_general(self):
        llms = create_eii_llms()
        assert llms["escalation"].task_type == "general"

    def test_circuit_breaker_shared_between_agents(self):
        """Circuit breaker state must propagate across agents via shared router."""
        llms = create_eii_llms()
        router = llms["diagnostic"].router

        # Trip the DeepSeek circuit (diagnostic's primary provider)
        for _ in range(3):
            router.circuit_breaker.record_failure(ProviderID.DEEPSEEK)

        # The evaluator's router should see the same tripped circuit
        evaluator_cb = llms["evaluator"].router.circuit_breaker
        assert evaluator_cb.is_available(ProviderID.DEEPSEEK) is False


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
