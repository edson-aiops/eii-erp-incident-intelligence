import asyncio
import logging
from src.deep_agents.graph import eii_agent_graph
from src.deep_agents.nodes.finalize_node import format_for_gradio

logger = logging.getLogger(__name__)

async def diagnose_incident_deep_agents(
    xml: str,
    incident_id: str,
    mentor_mode: bool = False,
    force_local: bool = False,
    retrieval_backend: str = "chromadb"
) -> dict:
    """
    Wrapper assíncrono para executar o Deep Agent a partir da UI Gradio.
    """
    # Estado inicial do agente
    initial_state = {
        "xml_input": xml,
        "incident_id": incident_id,
        "use_mentor_mode": mentor_mode,
        "context": None,
        "retrieved": None,
        "diagnosis": None,
        "evaluation_score": None,
        "evaluation_feedback": None,
        "iteration_count": 0,
        "max_iterations": 2,
        "routing_decision": "ollama-local" if force_local else None,
        "retrieval_backend": retrieval_backend,
        "model_used": None,
        "errors": [],
        "warnings": [],
        "final_result": None
    }
    
    try:
        # Executar grafo
        result = await eii_agent_graph.ainvoke(initial_state)
        
        # Formatar para Gradio
        if result.get('final_result'):
            return format_for_gradio(result)
        else:
            return {
                "diagnostico": "### ❌ Erro no Processamento\n\nNão foi possível gerar o diagnóstico.",
                "metadata": f"Erros: {result.get('errors', [])}"
            }
            
    except Exception as e:
        logger.error(f"Erro no wrapper Deep Agents: {e}")
        return {
            "diagnostico": f"### ❌ Erro Interno\n\n{str(e)}",
            "metadata": "Falha na execução do agente"
        }

# Versão síncrona para compatibilidade (caso Gradio precise)
def diagnose_incident_sync(*args, **kwargs):
    return asyncio.run(diagnose_incident_deep_agents(*args, **kwargs))
