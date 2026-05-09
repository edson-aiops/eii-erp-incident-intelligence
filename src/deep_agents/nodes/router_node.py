import logging
from typing import Dict, Any
from src.deep_agents.state import AgentState

logger = logging.getLogger(__name__)

# eSocial events that require deep reasoning (complex payroll/employment impacts)
_CRITICAL_EVENTS = {
    "S-1200", "S-2200", "S-2400", "S-2300",
    "S-5001", "S-5002", "S-5011", "S-5012",
}
_HIGH_EVENTS = {"S-2230", "S-2299", "S-3000", "S-5003"}

# Error codes by severity
_CRITICAL_ERRORS = {"E500", "E001", "E002", "E003", "E428"}
_HIGH_ERRORS = {"E469", "E214", "E312", "E401"}


def _classify_severity(evento: str, codigo_erro: str) -> str:
    ev = (evento or "").upper()
    err = (codigo_erro or "").upper()

    if ev == "PARSE_ERROR":
        return "CRITICAL"
    if any(e in ev for e in _CRITICAL_EVENTS):
        return "CRITICAL"
    if any(e in err for e in _CRITICAL_ERRORS):
        return "CRITICAL"
    if any(e in ev for e in _HIGH_EVENTS):
        return "HIGH"
    if any(e in err for e in _HIGH_ERRORS):
        return "HIGH"
    return "MEDIUM"


async def smart_router_node(state: AgentState) -> Dict[str, Any]:
    """Routes to the appropriate SmartRouter task_type based on eSocial event severity.

    routing_decision values map to SmartRouterLLM(task_type=...) in generate_node:
      - "deep_reasoning"  → 70b model, critical/high severity incidents
      - "validation"      → 8b model, medium/low severity
      - "sensitive_data"  → local Ollama (LGPD: PII detected)
    """
    context = state.get("context")

    if context is None:
        logger.warning("router_node: no context from parse — defaulting to deep_reasoning")
        return {"routing_decision": "deep_reasoning", "model_used": None}

    severity = _classify_severity(context.evento, context.codigo_erro)
    pi_detected = bool(context.pi_detected)

    # LGPD priority: PII in context → prefer local processing
    if pi_detected:
        decision = "sensitive_data"
    elif severity in ("CRITICAL", "HIGH"):
        decision = "deep_reasoning"
    else:
        decision = "validation"

    logger.info(
        "router_node: evento=%s, erro=%s, severity=%s, pii=%s => routing_decision=%s",
        context.evento, context.codigo_erro, severity, pi_detected, decision,
    )

    try:
        from observability import add_run_metadata
        add_run_metadata({
            "incident_id": state.get("incident_id"),
            "evento": context.evento,
            "codigo_erro": context.codigo_erro,
            "severity": severity,
            "pii_detected": pi_detected,
            "routing_decision": decision,
        })
    except Exception:
        pass

    return {"routing_decision": decision, "model_used": None}
