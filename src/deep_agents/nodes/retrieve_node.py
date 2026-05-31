import logging
import re
from typing import Dict, Any
from src.deep_agents.state import AgentState, RetrievedKnowledge

logger = logging.getLogger(__name__)


async def retrieve_node(state: AgentState) -> Dict[str, Any]:
    """Retrieve + Grade: reuses build_vector_store/retrieve/grade from crag_pipeline.py."""
    from crag_pipeline import build_vector_store, retrieve, grade, _KB_HASH

    context = state.get("context")
    if context is None:
        logger.warning("retrieve_node: no context — returning empty retrieval")
        return {
            "retrieved": RetrievedKnowledge(
                documents=[], relevance_scores=[], kb_version=_KB_HASH
            )
        }

    # Build query from eSocial context fields
    ocorrencias = context.metadata.get("ocorrencias", [])
    ocorrencias_txt = " ".join(
        f"{o.get('codigo', '')} {o.get('descricao', '')[:80]}"
        for o in ocorrencias[:3]
    )
    query = " ".join(filter(None, [context.evento, context.codigo_erro, ocorrencias_txt]))

    # Fallback: se evento desconhecido, enriquecer query com tags do XML bruto
    if context.evento in ("DESCONHECIDO", "PARSE_ERROR"):
        xml_raw = getattr(context, "xml_raw", "") or ""
        # Extrai tags relevantes do XML (ex: evtAdmissao, codCateg, tpRegTrab)
        tags = re.findall(r"<([a-zA-Z][a-zA-Z0-9]+)>", xml_raw[:800])
        stopwords = {"xml", "eSocial", "ideEvento", "ideEmpregador", "idePeriodo",
                     "ideVinculo", "infoEmpregador", "infoEmpregado"}
        tag_terms = " ".join(dict.fromkeys(t for t in tags if t not in stopwords))
        query = " ".join(filter(None, [tag_terms, context.codigo_erro]))
        logger.info("retrieve_node: enriched query (event unknown) = %r", query[:120])

    backend = state.get("retrieval_backend", "chromadb")

    try:
        col = build_vector_store()
        candidates = retrieve(col, query, n=5, backend=backend)
        relevant = grade(query, candidates)
    except Exception as e:
        logger.error("retrieve_node error: %s", e)
        return {
            "retrieved": RetrievedKnowledge(
                documents=[], relevance_scores=[], kb_version=_KB_HASH
            ),
            "errors": state.get("errors", []) + [f"Retrieval error: {e}"],
        }

    logger.info(
        "retrieve_node: query=%r, candidates=%d, relevant=%d",
        query[:80], len(candidates), len(relevant),
    )

    return {
        "retrieved": RetrievedKnowledge(
            documents=[c["item"] for c in relevant],
            relevance_scores=[1.0 - c.get("distance", 0.5) for c in relevant],
            kb_version=_KB_HASH,
        )
    }
