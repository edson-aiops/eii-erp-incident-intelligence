import logging
from typing import Dict, Any
from src.deep_agents.state import AgentState

logger = logging.getLogger(__name__)


async def smart_router_node(state: AgentState) -> Dict[str, Any]:
    """Routes to the appropriate SmartRouter task_type based on LGPD safety flag.

    routing_decision values map to SmartRouterLLM(task_type=...) in generate_node:
      - "deep_reasoning"  → heavy remote/local model, critical/high severity incidents
      - "simple_search"   → lighter model, medium/low severity
      - "sensitive_data"  → local Ollama (LGPD: PII detected and not safe for remote)
    """
    context = state.get("context")

    if context is None:
        logger.warning("router_node: no context from parse — defaulting to sensitive_data")
        return {"routing_decision": "sensitive_data", "model_used": None}

    is_safe = state.get("is_safe_for_remote", False)
    severidade = state.get("severidade", "baixa")

    # Fail-closed: se PII não seguro, força processamento local
    if not is_safe:
        decision = "sensitive_data"
    elif severidade in ("critica", "alta"):
        decision = "deep_reasoning"
    else:
        decision = "simple_search"

    logger.info(
        "router_node: evento=%s, erro=%s, severity=%s, is_safe=%s => routing_decision=%s",
        context.evento, context.codigo_erro, severidade, is_safe, decision,
    )

    try:
        from observability import add_run_metadata
        add_run_metadata({
            "incident_id": state.get("incident_id"),
            "evento": context.evento,
            "codigo_erro": context.codigo_erro,
            "severity": severidade,
            "is_safe_for_remote": is_safe,
            "routing_decision": decision,
        })
    except Exception:
        pass

    return {"routing_decision": decision, "model_used": None}
