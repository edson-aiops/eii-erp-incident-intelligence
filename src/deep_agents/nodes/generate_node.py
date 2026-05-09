import logging
from typing import Dict, Any
from src.deep_agents.state import AgentState

logger = logging.getLogger(__name__)


async def generate_node(state: AgentState) -> Dict[str, Any]:
    """Generate diagnosis by delegating to crag_pipeline.generate().

    Uses routing_decision (set by router_node) to pick the right SmartRouter
    task_type. Falls back gracefully if the LLM call fails.
    """
    from crag_pipeline import generate
    from xml_parser import parse_esocial_xml

    context = state.get("context")
    retrieved = state.get("retrieved")
    incident_id = state.get("incident_id", "UNKNOWN")
    mentor_mode = state.get("use_mentor_mode", False)
    routing_decision = state.get("routing_decision", "deep_reasoning")
    # evaluation_feedback carries the corrective hint from reflexion_node
    corrective_hint = state.get("evaluation_feedback") or ""

    if context is None:
        return {
            "diagnosis": _error_diagnosis(incident_id, "DESCONHECIDO", "E000",
                                          "Contexto nao disponivel — parse falhou."),
            "model_used": routing_decision,
        }

    # Re-parse XML so we can pass the parsed object to generate()
    try:
        parsed_xml = parse_esocial_xml(context.xml_raw)
    except Exception as e:
        logger.error("generate_node: re-parse failed: %s", e)
        return {
            "diagnosis": _error_diagnosis(
                incident_id, context.evento, context.codigo_erro,
                f"Re-parse do XML falhou: {e}"
            ),
            "model_used": routing_decision,
        }

    # Build relevant list in crag_pipeline format
    relevant = []
    if retrieved and retrieved.documents:
        for doc in retrieved.documents:
            relevant.append({"item": doc, "distance": 0.3, "id": doc.get("id", "")})

    try:
        diagnosis = generate(
            parsed_xml=parsed_xml,
            relevant=relevant,
            incident_id=incident_id,
            corrective_hint=corrective_hint,
            mentor_mode=mentor_mode,
        )
    except Exception as e:
        logger.error("generate_node: generate() failed: %s", e)
        diagnosis = _error_diagnosis(
            incident_id, context.evento, context.codigo_erro,
            f"Geracao falhou: {e}"
        )

    logger.info(
        "generate_node: incident=%s, routing=%s, confianca=%s",
        incident_id, routing_decision, diagnosis.get("confianca", "?"),
    )

    try:
        from observability import add_run_metadata
        add_run_metadata({
            "incident_id": incident_id,
            "routing_decision": routing_decision,
            "confianca": diagnosis.get("confianca"),
            "severidade": diagnosis.get("severidade"),
            "fonte": diagnosis.get("fonte"),
            "has_corrective_hint": bool(corrective_hint),
            "kb_refs": diagnosis.get("referencias_kb", []),
        })
    except Exception:
        pass

    return {"diagnosis": diagnosis, "model_used": routing_decision}


def _error_diagnosis(incident_id: str, evento: str, codigo_erro: str, causa: str) -> dict:
    return {
        "incident_id": incident_id,
        "evento": evento,
        "codigo_erro": codigo_erro,
        "severidade": "MEDIO",
        "causa_raiz": causa,
        "confianca": "BAIXA",
        "fonte": "ERROR",
        "passos_resolucao": ["Analise manual necessaria."],
        "validacao": "N/A",
        "tempo_estimado": "Indefinido",
        "referencias_kb": [],
        "alerta_hitl": f"Geracao automatica falhou — revisao humana obrigatoria. {causa}",
    }
