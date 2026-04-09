"""
SmartRouter - Multi-LLM Orchestration for EII
Includes: Qwen supervisor, resilient failover, CRAG pipeline
"""

from smartrouter.qwen_adapter import QwenAdapter
from smartrouter.llm_resilient import ResilientLLM

__all__ = ["QwenAdapter", "ResilientLLM"]
__version__ = "1.0.0"