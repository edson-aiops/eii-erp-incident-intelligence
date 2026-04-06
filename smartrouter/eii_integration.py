"""SmartRouter — EII Integration Helpers.

Pre-configured :class:`~smartrouter.adapter.SmartRouterLLM` instances for
each EII agent role. All instances share a single :class:`~smartrouter.router.SmartRouter`
so the circuit breaker state is unified across the entire pipeline — if
DeepSeek trips during DiagnosticAgent, Kimi takes over immediately for
the next call without repeating failed attempts.

Agent → TaskType mapping
------------------------
+------------------+----------------+----------------------------------+
| EII Agent        | TaskType       | Primary Provider                 |
+==================+================+==================================+
| DiagnosticAgent  | deep_reasoning | DeepSeek R1 (chain-of-thought)  |
| EvaluatorAgent   | validation     | Cerebras (ultra-fast, 3k tok/s) |
| EscalationAgent  | general        | Groq (balanced speed/quality)   |
| IngestAgent      | sensitive_data | Ollama local (data stays local) |
| Mentor mode      | iteration      | Groq (fast drafts)              |
+------------------+----------------+----------------------------------+

Usage::

    from smartrouter.eii_integration import create_eii_llms
    from langchain_core.messages import SystemMessage, HumanMessage

    llms = create_eii_llms()

    # In any LangGraph node — identical to ChatGroq.invoke():
    response = llms["diagnostic"].invoke([
        SystemMessage("You are an EII diagnostic agent."),
        HumanMessage("Analyze S-1200 eSocial rejection: ..."),
    ])
    print(response.content)
    print(response.response_metadata["provider"])   # e.g. "deepseek"

    # Inspect shared circuit breaker state:
    router = llms["diagnostic"].router
    print(router.circuit_breaker.get_status())
"""

from __future__ import annotations

from typing import Optional

from .adapter import SmartRouterLLM
from .router import SmartRouter


# Canonical EII agent → task_type mapping.
# Changing a provider preference? Edit routing rules in config.py instead —
# this mapping only selects the *task category*, not the provider directly.
EII_AGENT_TASK_TYPES: dict[str, str] = {
    "diagnostic": "deep_reasoning",   # DeepSeek R1 / Kimi thinking — root cause analysis
    "evaluator": "validation",         # Cerebras — instant CRAG relevance checks
    "escalation": "general",           # Groq — balanced, good for routing decisions
    "ingest": "sensitive_data",        # Ollama local — CPF/CNPJ/eSocial never leaves network
    "mentor": "iteration",             # Groq — fast drafts for interactive mentor mode
}


def create_eii_llms(
    router: Optional[SmartRouter] = None,
) -> dict[str, SmartRouterLLM]:
    """Create pre-configured SmartRouterLLM instances for all EII agents.

    All returned LLMs share the same :class:`~smartrouter.router.SmartRouter`
    instance, ensuring a **unified circuit breaker** across the full pipeline.

    Args:
        router: Optional existing SmartRouter instance to reuse. When ``None``
            (default), a new SmartRouter is created internally. Pass an
            existing router to share history/stats with other components
            (e.g., a monitoring dashboard reading ``router.get_stats()``).

    Returns:
        Dict with keys ``diagnostic``, ``evaluator``, ``escalation``,
        ``ingest``, ``mentor`` — each mapped to a ready-to-use
        :class:`~smartrouter.adapter.SmartRouterLLM`.

    Example::

        # Minimal — auto-creates router:
        llms = create_eii_llms()

        # With an existing router (e.g., to inspect stats later):
        from smartrouter import SmartRouter
        router = SmartRouter()
        llms = create_eii_llms(router=router)

        # In a LangGraph node:
        result = llms["diagnostic"].invoke([HumanMessage("Debug S-1200")])

        # Check provider stats after the pipeline run:
        print(router.get_stats())
    """
    shared_router = router if router is not None else SmartRouter()

    return {
        agent: SmartRouterLLM(task_type=task_type, router=shared_router)
        for agent, task_type in EII_AGENT_TASK_TYPES.items()
    }
