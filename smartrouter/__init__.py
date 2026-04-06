"""SmartRouter — Multi-LLM Orchestrator for EII.

Routes tasks to the best LLM provider based on competency profiling.
9 providers: 7 free + 1 paid + 1 local. All OpenAI-compatible.

Quick start:
    from smartrouter import SmartRouter

    router = SmartRouter()
    result = await router.route("Implement a Pydantic schema for IntelItem")
    print(result.response)
    print(f"Provider: {result.provider_used}, Latency: {result.latency_ms}ms")
"""

from .config import PROVIDERS, ROUTING_RULES, COST_PER_MILLION_TOKENS
from .router import SmartRouter, TaskClassifier, CircuitBreaker, RoutingEngine
from .schemas import (
    TaskType,
    Complexity,
    ProviderID,
    ProviderStatus,
    TaskClassification,
    ProviderConfig,
    RoutingRule,
    RoutingResult,
)
from .adapter import SmartRouterLLM
from .eii_integration import create_eii_llms, EII_AGENT_TASK_TYPES

__all__ = [
    # Main API
    "SmartRouter",
    # LangChain adapter
    "SmartRouterLLM",
    # EII integration helpers
    "create_eii_llms",
    "EII_AGENT_TASK_TYPES",
    # Components
    "TaskClassifier",
    "CircuitBreaker",
    "RoutingEngine",
    # Config
    "PROVIDERS",
    "ROUTING_RULES",
    "COST_PER_MILLION_TOKENS",
    # Schemas
    "TaskType",
    "Complexity",
    "ProviderID",
    "ProviderStatus",
    "TaskClassification",
    "ProviderConfig",
    "RoutingRule",
    "RoutingResult",
]

__version__ = "0.1.0"
