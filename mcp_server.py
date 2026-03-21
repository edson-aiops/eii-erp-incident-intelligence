"""
EII MCP Server — exposes eii_query and eii_escalate as MCP tools via fastmcp.

Usage:
    python mcp_server.py

Environment variables required:
    GROQ_API_KEY   — Groq API key for Llama 3.3 70B (LLM + model router)

Optional:
    DB_PATH        — Path to SQLite file (default: eii_incidents.db in CWD)
                     Must match the DB used by the Gradio app if running both.
"""

from fastmcp import FastMCP
from eii_handlers import query_incident, escalate_incident

mcp = FastMCP(
    name="EII — ERP Incident Intelligence",
    instructions=(
        "Diagnóstico de falhas de integração eSocial / Webservice RFB. "
        "Use eii_query para analisar um XML de retorno e obter diagnóstico CRAG. "
        "Use eii_escalate para registrar a decisão do analista (APROVADO/REJEITADO) "
        "após revisão humana — obrigatória antes de qualquer ação corretiva."
    ),
)


@mcp.tool()
def eii_query(xml_rejeicao: str) -> dict:
    """
    Analyze an eSocial XML return through the EII CRAG diagnostic pipeline.

    Parses the XML, retrieves relevant incidents from the knowledge base,
    generates a structured diagnosis with root cause and resolution steps,
    and persists the result as PENDING for human review.

    Args:
        xml_rejeicao: Raw eSocial XML string — supported formats:
                      retornoEnvioLoteEventos, retornoProcessamentoEvento,
                      retornoEvento.

    Returns:
        Diagnosis dict containing:
        - incident_id (str): Generated ID, e.g. "INC-20250307-143022"
        - evento (str): eSocial event code, e.g. "S-1200"
        - codigo_erro (str): Error codes from the XML response
        - severidade (str): "CRÍTICO" | "ALTO" | "MÉDIO" | "BAIXO"
        - confianca (str): AI confidence — "ALTA" | "MÉDIA" | "BAIXA"
        - fonte (str): "KB_MATCH" | "LLM_FALLBACK"
        - causa_raiz (str): Technical root cause explanation
        - passos_resolucao (list[str]): Ordered resolution steps
        - alerta_hitl (str): Human review alert / escalation reason
        - _meta (dict): Pipeline metadata (logprob_sim, eval_iterations, etc.)
    """
    return query_incident(xml_rejeicao)


@mcp.tool()
def eii_escalate(incident_id: str, status: str, notes: str = "") -> dict:
    """
    Record an analyst decision for a PENDING EII incident (Human-in-the-Loop).

    IMPORTANT: This step is mandatory before executing any corrective action.
    No incident resolution is considered approved without an explicit analyst
    decision. This enforces the HITL principle for eSocial compliance contexts.

    Args:
        incident_id: Incident ID returned by eii_query (e.g. "INC-20250307-143022").
        status:      Analyst decision — "APROVADO" or "REJEITADO".
        notes:       Analyst notes explaining the decision (recommended for
                     audit trail — e.g. whether the AI diagnosis was correct,
                     what adjustments were made, or why the diagnosis was rejected).

    Returns:
        Decision dict containing:
        - incident_id (str): The decided incident ID
        - status (str): "APROVADO" or "REJEITADO"
        - decided_at (str): ISO 8601 timestamp of the decision
        - message (str): Confirmation message
    """
    return escalate_incident(incident_id, status, notes)


if __name__ == "__main__":
    mcp.run()
