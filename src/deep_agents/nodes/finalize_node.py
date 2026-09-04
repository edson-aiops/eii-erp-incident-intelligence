import logging
from typing import Dict, Any
from src.deep_agents.state import AgentState
from src.privacy.scrubber import PIIScrubber
from src.utils.tokenmap_store import get_token_map_store

logger = logging.getLogger(__name__)


async def finalize_node(state: AgentState) -> Dict[str, Any]:
    """Applies logprobs confidence gate (ADR-001), restores PII tokens and builds the final result dict."""
    from crag_pipeline import confidence_score, _KB_HASH
    from xml_parser import parse_esocial_xml

    context = state.get("context")
    diagnosis = dict(state.get("diagnosis") or {})
    incident_id = state.get("incident_id", "UNKNOWN")
    iteration_count = state.get("iteration_count", 0)

    # A25: token_map vem da store (Redis/TTL), não do estado do grafo.
    # Lê e apaga imediatamente (uso único — restore só acontece no finalize).
    token_map = {}
    if incident_id and incident_id != "UNKNOWN":
        try:
            store = get_token_map_store()
            token_map = store.get(incident_id)
            if token_map:
                store.delete(incident_id)
        except Exception as e:
            logger.warning("finalize_node: falha ao ler token_map da store: %s", e)

    # Restaurar tokens na resposta antes de expor ao usuário
    if token_map:
        try:
            scrubber = PIIScrubber()
            resposta = diagnosis.get("resposta", "")
            diagnosis["resposta"] = scrubber.restore(resposta, token_map)
        except Exception as e:
            logger.warning("finalize_node: restore failed: %s", e)

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
        "is_safe_for_remote": state.get("is_safe_for_remote"),
        "token_map": None,  # garante que o mapa não serializa na saída
    }

    logger.info(
        "finalize_node: incident=%s, confianca=%s, severidade=%s, passos=%d",
        incident_id,
        final_result["confianca"],
        final_result["severidade"],
        len(final_result["passos_resolucao"]),
    )

    try:
        from observability import add_run_metadata
        add_run_metadata({
            "incident_id": incident_id,
            "confianca": final_result["confianca"],
            "severidade": final_result["severidade"],
            "logprob_sim": logprob_sim,
            "iteracoes": iteration_count,
            "evaluation_score": state.get("evaluation_score"),
            "routing_decision": state.get("routing_decision"),
            "model_used": state.get("model_used"),
            "referencias_kb": final_result.get("referencias_kb", []),
            "has_hitl_alert": bool(final_result.get("alerta_hitl")),
        })
    except Exception:
        pass

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
