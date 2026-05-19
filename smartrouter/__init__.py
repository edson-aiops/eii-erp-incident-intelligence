"""
SmartRouter - Multi-LLM Orchestration for EII
Includes: Qwen supervisor, resilient failover, CRAG pipeline
"""

from smartrouter.qwen_adapter import QwenAdapter
from smartrouter.llm_resilient import ResilientLLM
from smartrouter.router import SmartRouter, TaskClassifier, CircuitBreaker, RoutingEngine
from smartrouter.schemas import (
    TaskType,
    Complexity,
    ProviderID,
    ProviderStatus,
    TaskClassification,
    ProviderConfig,
    RoutingRule,
    RoutingResult,
)

__all__ = [
    "QwenAdapter",
    "ResilientLLM",
    "SmartRouter",
    "TaskClassifier",
    "CircuitBreaker",
    "RoutingEngine",
    "TaskType",
    "Complexity",
    "ProviderID",
    "ProviderStatus",
    "TaskClassification",
    "ProviderConfig",
    "RoutingRule",
    "RoutingResult",
]
__version__ = "1.0.0"
