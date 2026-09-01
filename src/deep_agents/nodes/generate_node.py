import logging
from typing import Dict, Any
from src.deep_agents.state import AgentState

logger = logging.getLogger(__name__)


def _build_prompt(payload: str, state: AgentState) -> str:
    """Monta prompt para o SmartRouter a partir do payload e contexto."""
    context = state.get("context")
    evento = context.evento if context else "DESCONHECIDO"
    codigo_erro = context.codigo_erro if context else "E000"
    corrective_hint = state.get("evaluation_feedback") or ""

    prompt_parts = [
        "Você é um analista especialista em eSocial.",
        f"Evento: {evento}",
        f"Código de erro: {codigo_erro}",
        "XML do evento (pseudonimizado):",
        payload[:4000],
    ]
    if corrective_hint:
        prompt_parts.append(f"Feedback de revisão anterior: {corrective_hint}")
    prompt_parts.append(
        "Forneça: causa_raiz, severidade (BAIXA/MEDIA/ALTA/CRITICA), "
        "passos_resolucao (lista), validacao, tempo_estimado, referencias_kb (lista), "
        "alerta_hitl e fonte. Responda em português do Brasil."
    )
    return "\n\n".join(prompt_parts)


async def generate_node(state: AgentState) -> Dict[str, Any]:
    """Generate diagnosis by delegating to SmartRouter.call().

    Uses routing_decision (set by router_node) to pick the right task_type.
    Falls back gracefully if the LLM call fails.
    """
    from smartrouter.smart_router import SmartRouter

    incident_id = state.get("incident_id", "UNKNOWN")
    routing_decision = state.get("routing_decision", "deep_reasoning")
    is_safe_for_remote = state.get("is_safe_for_remote", False)

    payload = state.get("scrubbed_payload", state.get("payload", state.get("xml_input", "")))

    if not payload:
        logger.error("generate_node: no payload available")
        return {
            "diagnosis": _error_diagnosis(incident_id, "DESCONHECIDO", "E000",
                                          "Payload não disponível — parse falhou."),
            "model_used": routing_decision,
        }

    prompt = _build_prompt(payload, state)

    try:
        router = SmartRouter()
        result = await router.call(
            prompt=prompt,
            routing_decision=routing_decision,
            is_safe_for_remote=is_safe_for_remote,
        )
        diagnosis = _normalize_smart_router_result(result, incident_id)
    except Exception as e:
        logger.error("generate_node: SmartRouter.call failed: %s", e)
        diagnosis = _error_diagnosis(
            incident_id,
            state.get("context", {}).evento if state.get("context") else "DESCONHECIDO",
            state.get("context", {}).codigo_erro if state.get("context") else "E000",
            f"Geração falhou: {e}",
        )

    logger.info(
        "generate_node: incident=%s, routing=%s, is_safe=%s, confianca=%s",
        incident_id, routing_decision, is_safe_for_remote, diagnosis.get("confianca", "?"),
    )

    try:
        from observability import add_run_metadata
        add_run_metadata({
            "incident_id": incident_id,
            "routing_decision": routing_decision,
            "is_safe_for_remote": is_safe_for_remote,
            "confianca": diagnosis.get("confianca"),
            "severidade": diagnosis.get("severidade"),
            "fonte": diagnosis.get("fonte"),
            "has_corrective_hint": bool(state.get("evaluation_feedback")),
            "kb_refs": diagnosis.get("referencias_kb", []),
        })
    except Exception:
        pass

    return {"diagnosis": diagnosis, "model_used": routing_decision}


def _normalize_smart_router_result(result: Dict[str, Any], incident_id: str) -> Dict[str, Any]:
    """Converte resultado do SmartRouter no formato de diagnosis esperado."""
    if not isinstance(result, dict):
        return _error_diagnosis(incident_id, "DESCONHECIDO", "E000",
                                "Resposta inválida do SmartRouter.")

    # Se o SmartRouter já retornou um dict no formato de diagnosis, usa direto.
    if "causa_raiz" in result or "root_cause" in result:
        return {
            "incident_id": incident_id,
            "evento": result.get("evento", "DESCONHECIDO"),
            "codigo_erro": result.get("codigo_erro", "E000"),
            "severidade": result.get("severidade", result.get("severity", "MEDIO")).upper(),
            "causa_raiz": result.get("causa_raiz", result.get("root_cause", "Sem causa identificada.")),
            "confianca": result.get("confianca", result.get("confidence", "BAIXA")).upper(),
            "fonte": result.get("fonte", result.get("source", "SMARTROUTER")),
            "passos_resolucao": result.get("passos_resolucao", result.get("resolution_steps", ["Análise manual necessária."])),
            "validacao": result.get("validacao", result.get("validation", "N/A")),
            "tempo_estimado": result.get("tempo_estimado", result.get("estimated_time", "Indefinido")),
            "referencias_kb": result.get("referencias_kb", result.get("kb_refs", [])),
            "alerta_hitl": result.get("alerta_hitl", result.get("hitl_alert", "")),
            "resposta": result.get("resposta", result.get("response", "")),
        }

    # Caso o resultado seja um texto livre
    resposta = str(result.get("text", result.get("content", result)))
    return {
        "incident_id": incident_id,
        "evento": "DESCONHECIDO",
        "codigo_erro": "E000",
        "severidade": "MEDIO",
        "causa_raiz": resposta[:500],
        "confianca": "BAIXA",
        "fonte": "SMARTROUTER",
        "passos_resolucao": ["Análise manual necessária."],
        "validacao": "N/A",
        "tempo_estimado": "Indefinido",
        "referencias_kb": [],
        "alerta_hitl": "",
        "resposta": resposta,
    }


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
        "resposta": causa,
    }
