from langgraph.graph import StateGraph, END
from src.deep_agents.state import AgentState
from src.deep_agents.nodes.parse_node import parse_xml_node
from src.deep_agents.nodes.router_node import smart_router_node
from src.deep_agents.nodes.retrieve_node import retrieve_node
from src.deep_agents.nodes.generate_node import generate_node
from src.deep_agents.nodes.evaluate_node import evaluate_node, should_reflexion
from src.deep_agents.nodes.reflexion_node import reflexion_node
from src.deep_agents.nodes.finalize_node import finalize_node

def create_deep_agent_graph() -> StateGraph:
    workflow = StateGraph(AgentState)
    workflow.add_node("parse", parse_xml_node)
    workflow.add_node("router", smart_router_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("evaluate", evaluate_node)
    workflow.add_node("reflexion", reflexion_node)
    workflow.add_node("finalize", finalize_node)

    workflow.set_entry_point("parse")
    workflow.add_edge("parse", "router")
    workflow.add_edge("router", "retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", "evaluate")
    workflow.add_conditional_edges("evaluate", should_reflexion, {
        "reflexion": "reflexion",
        "finalize": "finalize"
    })
    workflow.add_edge("reflexion", "generate")
    workflow.add_edge("finalize", END)

    return workflow.compile()

eii_agent_graph = create_deep_agent_graph()
