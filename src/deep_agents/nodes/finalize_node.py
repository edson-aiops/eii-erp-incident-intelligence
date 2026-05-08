import logging
from typing import Dict, Any
from src.deep_agents.state import AgentState

logger = logging.getLogger(__name__)


async def finalize_node(state: AgentState) -> Dict[str, Any]:
    """Applies logprobs confidence gate (ADR-001) and builds the final result dict."""
    from crag_pipeline import confidence_score, _KB_HASH
    from xml_parser import parse_esocial_xml

    context = state.get("context")
    diagnosis = dict(state.get("diagnosis") or {})
    incident_id = state.get("incident_id", "UNKNOWN")
    iteration_count = state.get("iteration_count", 0)

    # ADR-001: override confianca with logprobs measurement
    logprob_sim = None
    if context and diagnosis and context.xml_raw:
        try:
            parsed_xml = parse_esocial_xml(context.xml_raw)
            confianca_label, prob_sim = confidence_score(parsed_xml, diagnosis)
            diagnosis["confianca"] = confianca_label
            logprob_sim = round(prob_sim, 3)
        except Exception as e:
            logger.warning("finalize_node: confidence_score failed: %s", e)

    final_result = {
        "incident_id": incident_id,
        "diagnostico": diagnosis.get("causa_raiz", "Sem diagnostico"),
        "severidade": diagnosis.get("severidade", "MEDIO"),
        "confianca": diagnosis.get("confianca", "BAIXA"),
        "passos_resolucao": diagnosis.get("passos_resolucao", []),
        "validacao": diagnosis.get("validacao", ""),
        "tempo_estimado": diagnosis.get("tempo_estimado", ""),
        "referencias_kb": diagnosis.get("referencias_kb", []),
        "alerta_hitl": diagnosis.get("alerta_hitl", ""),
        "fonte": diagnosis.get("fonte", ""),
        "metadata": {
            "iteracoes": iteration_count,
            "evaluation_score": state.get("evaluation_score"),
            "logprob_sim": logprob_sim,
            "kb_version": _KB_HASH,
            "retrieval_backend": state.get("retrieval_backend", "chromadb"),
            "routing_decision": state.get("routing_decision"),
            "model_used": state.get("model_used"),
            "warnings": state.get("warnings", []),
            "errors": state.get("errors", []),
        },
        "diagnosis_raw": diagnosis,
    }

    logger.info(
        "finalize_node: incident=%s, confianca=%s, severidade=%s, passos=%d",
        incident_id,
        final_result["confianca"],
        final_result["severidade"],
        len(final_result["passos_resolucao"]),
    )

    return {"final_result": final_result}


def format_for_gradio(result: Dict[str, Any]) -> Dict[str, Any]:
    """Formats agent final_result for Gradio display."""
    fr = result.get("final_result", {})
    meta = fr.get("metadata", {})

    metadata_str = (
        f"Confianca: {fr.get('confianca', 'N/A')} | "
        f"Severidade: {fr.get('severidade', 'N/A')} | "
        f"Iteracoes: {meta.get('iteracoes', 1)} | "
        f"Fonte: {fr.get('fonte', 'N/A')}"
    )

    return {
        "diagnostico": fr.get("diagnostico", "Diagnostico nao gerado."),
        "metadata": metadata_str,
    }
