"""
EII — intel_node
No LangGraph que executa o IntelAgent sobre o final_result e
adiciona proactive_insights ao AgentState.
"""

import logging
from typing import Dict, Any

from src.deep_agents.state import AgentState

logger = logging.getLogger(__name__)


async def intel_node(state: AgentState) -> Dict[str, Any]:
    """Executa IntelAgent.run() sobre final_result e persiste insights no state."""
    from src.intel_agent.intel_agent import IntelAgent

    final_result = state.get("final_result")
    if not final_result:
        logger.warning("intel_node: final_result ausente, pulando analise proativa")
        return {"proactive_insights": {}}

    try:
        agent = IntelAgent()
        insights = agent.run(final_result)
    except Exception as e:
        logger.error("intel_node: IntelAgent.run() falhou: %s", e)
        insights = {"erro": str(e), "alertas": [], "risco_recorrencia": "DESCONHECIDO"}

    logger.info(
        "intel_node: risco=%s, alertas=%d, relacionados=%d",
        insights.get("risco_recorrencia", "?"),
        len(insights.get("alertas", [])),
        len(insights.get("incidentes_relacionados", [])),
    )

    try:
        from observability import add_run_metadata
        padrao = insights.get("padrao_historico", {})
        add_run_metadata({
            "incident_id": state.get("incident_id"),
            "intel_risco_recorrencia": insights.get("risco_recorrencia"),
            "intel_total_90d": padrao.get("total_90d", 0),
            "intel_tendencia": padrao.get("tendencia"),
            "intel_alertas_count": len(insights.get("alertas", [])),
            "intel_relacionados_count": len(insights.get("incidentes_relacionados", [])),
        })
    except Exception:
        pass

    return {"proactive_insights": insights}
