"""SmartRouter — LangChain Adapter.

Makes SmartRouter a drop-in replacement for ChatGroq in LangChain/LangGraph
pipelines. Each SmartRouterLLM instance routes calls to the best provider
based on the configured task_type (or auto-classifies if not set).

Usage:
    from smartrouter.adapter import SmartRouterLLM
    from langchain_core.messages import HumanMessage, SystemMessage

    # With explicit task type (recommended for EII agents):
    llm = SmartRouterLLM(task_type="deep_reasoning")
    result = llm.invoke([HumanMessage(content="Diagnose S-1200 error")])

    # Force a specific provider (bypass routing):
    llm = SmartRouterLLM(task_type="validation", force_provider="cerebras")

    # Shared router (unified circuit breaker across agents):
    from smartrouter import SmartRouter
    router = SmartRouter()
    llm_a = SmartRouterLLM(task_type="deep_reasoning", router=router)
    llm_b = SmartRouterLLM(task_type="validation", router=router)
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import Any, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from .router import SmartRouter
from .schemas import ProviderID, TaskType

logger = logging.getLogger("smartrouter.adapter")

# String → TaskType enum lookup (values are the .value of each enum member)
_TASK_TYPE_MAP: dict[str, TaskType] = {t.value: t for t in TaskType}


def _lc_messages_to_task(
    messages: List[BaseMessage],
) -> tuple[str, Optional[str]]:
    """Convert LangChain messages list to (task_str, system_prompt).

    Extraction rules:
    - SystemMessage  → system_prompt (first one wins, rest ignored)
    - HumanMessage   → appended to task_str as-is
    - AIMessage      → appended to task_str prefixed with "Assistant: "
    - Other types    → appended to task_str as str(content)

    Args:
        messages: LangChain message list from invoke() / _generate().

    Returns:
        (task_str, system_prompt) ready to pass to SmartRouter.route().

    Example:
        task, sys = _lc_messages_to_task([
            SystemMessage("You are an EII agent."),
            HumanMessage("Analyze S-1200 error"),
        ])
        # task == "Analyze S-1200 error"
        # sys  == "You are an EII agent."
    """
    system_prompt: Optional[str] = None
    task_parts: list[str] = []

    for msg in messages:
        if isinstance(msg, SystemMessage):
            if system_prompt is None:          # first system message wins
                system_prompt = str(msg.content)
        elif isinstance(msg, HumanMessage):
            task_parts.append(str(msg.content))
        elif isinstance(msg, AIMessage):
            task_parts.append(f"Assistant: {msg.content}")
        else:
            # ToolMessage, FunctionMessage, ChatMessage, etc.
            task_parts.append(str(msg.content))

    return "\n".join(task_parts), system_prompt


class SmartRouterLLM(BaseChatModel):
    """LangChain BaseChatModel backed by SmartRouter multi-LLM orchestration.

    Drop-in replacement for ``ChatGroq`` (or any LangChain chat model).
    Routes each call to the best LLM provider based on ``task_type``.
    Supports both sync (``invoke``) and async (``ainvoke``) — LangGraph
    can call either path without extra configuration.

    Args:
        task_type: Pre-set task type string. When set, skips auto-classification
            and forces the router to use the designated provider for this type.
            Valid values match :class:`~smartrouter.schemas.TaskType` values:
            ``coding_complex``, ``coding_clean``, ``validation``,
            ``long_context``, ``deep_reasoning``, ``architecture``,
            ``sensitive_data``, ``iteration``, ``general``.
            If ``None``, SmartRouter auto-classifies the task.
        force_provider: Always use this provider ID string, bypassing routing
            entirely. Valid values match :class:`~smartrouter.schemas.ProviderID`
            values: ``groq``, ``cerebras``, ``deepseek``, ``kimi``, etc.
        router: Shared :class:`~smartrouter.router.SmartRouter` instance.
            If ``None``, a new router is created for this LLM instance.
            **Pass the same instance to multiple agents to share circuit
            breaker state** — provider failures detected by one agent
            immediately affect routing in all other agents.

    Example::

        # Before (ChatGroq):
        from langchain_groq import ChatGroq
        llm = ChatGroq(model="llama-3.3-70b-versatile")

        # After (SmartRouterLLM):
        from smartrouter.adapter import SmartRouterLLM
        llm = SmartRouterLLM(task_type="deep_reasoning")

        # Usage is identical — zero change in agent code:
        result = llm.invoke([HumanMessage(content="Diagnose S-1200 error")])
        print(result.content)
    """

    task_type: Optional[str] = None
    force_provider: Optional[str] = None
    router: Optional[Any] = None  # SmartRouter — Any avoids Pydantic serialization issues

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        task_type: Optional[str] = None,
        force_provider: Optional[str] = None,
        router: Optional[SmartRouter] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            task_type=task_type,
            force_provider=force_provider,
            router=router if router is not None else SmartRouter(),
            **kwargs,
        )

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _resolve_task_type(self) -> Optional[TaskType]:
        """Resolve task_type string to TaskType enum, or None for auto-classify."""
        if self.task_type is None:
            return None
        tt = _TASK_TYPE_MAP.get(self.task_type)
        if tt is None:
            raise ValueError(
                f"Unknown task_type '{self.task_type}'. "
                f"Valid values: {sorted(_TASK_TYPE_MAP.keys())}"
            )
        return tt

    def _resolve_force_provider(self) -> Optional[ProviderID]:
        """Resolve force_provider string to ProviderID enum, or None."""
        if self.force_provider is None:
            return None
        try:
            return ProviderID(self.force_provider)
        except ValueError:
            valid = sorted(p.value for p in ProviderID)
            raise ValueError(
                f"Unknown force_provider '{self.force_provider}'. "
                f"Valid values: {valid}"
            )

    # ── Core async logic ──────────────────────────────────────────────────────

    async def _agenerate_core(self, messages: List[BaseMessage]) -> ChatResult:
        """Shared async implementation called by both sync and async paths.

        Converts LangChain messages → SmartRouter.route() → ChatResult.
        Attaches provider/latency metadata to the returned AIMessage.
        """
        task_str, system_prompt = _lc_messages_to_task(messages)

        if not task_str.strip():
            raise ValueError(
                "SmartRouterLLM received no user content in messages. "
                "Provide at least one HumanMessage."
            )

        result = await self.router.route(
            task=task_str,
            system_prompt=system_prompt,
            force_type=self._resolve_task_type(),
            force_provider=self._resolve_force_provider(),
        )

        if not result.response:
            raise RuntimeError(
                f"SmartRouter returned empty response from "
                f"{result.provider_used.value}. "
                f"Status: {result.status.value}. "
                f"Error: {result.error_message}"
            )

        logger.debug(
            "SmartRouter routed to %s (task_type=%s, fallback=%s, %dms)",
            result.provider_used.value,
            result.classification.task_type.value,
            result.was_fallback,
            result.latency_ms,
        )

        ai_message = AIMessage(
            content=result.response,
            response_metadata={
                "provider": result.provider_used.value,
                "task_type": result.classification.task_type.value,
                "was_fallback": result.was_fallback,
                "latency_ms": result.latency_ms,
                "tokens_used": result.tokens_used,
                "cost_usd": result.cost_estimate_usd,
                "status": result.status.value,
            },
        )

        return ChatResult(generations=[ChatGeneration(message=ai_message)])

    # ── LangChain / LangGraph interface ──────────────────────────────────────

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Synchronous generation.

        Detects whether an event loop is already running (e.g., inside Jupyter
        or an async LangGraph node calling sync code) and adapts accordingly:
        - No running loop → ``asyncio.run()`` directly.
        - Loop already running → offload to a ``ThreadPoolExecutor`` thread
          so a fresh loop can be created there without conflicting with the
          parent loop.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # Async context: run in a separate thread with its own event loop
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, self._agenerate_core(messages))
                return future.result()
        else:
            return asyncio.run(self._agenerate_core(messages))

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Asynchronous generation — direct path for LangGraph async nodes."""
        return await self._agenerate_core(messages)

    # ── LangChain metadata ────────────────────────────────────────────────────

    @property
    def _llm_type(self) -> str:
        return "smartrouter"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "force_provider": self.force_provider,
        }
