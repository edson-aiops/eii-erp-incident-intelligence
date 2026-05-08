from typing import Dict, Any
from src.deep_agents.state import AgentState

async def reflexion_node(state: AgentState) -> Dict[str, Any]:
    """Reflexão sobre a resposta para melhorar iterações futuras."""
    return {"reflections": [], "improvements": []}

async def finalize_node(state: AgentState) -> Dict[str, Any]:
    """Finaliza o processo e retorna resultado consolidado."""
    return {"final_output": state.get("diagnosis", "No diagnosis generated")}
