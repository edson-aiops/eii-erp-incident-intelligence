"""
RAGFlow Cloud retrieval client — dual-backend POC for eii-brasil.

Provides retrieve_ragflow() as a drop-in complement to the ChromaDB-based
retrieve() in crag_pipeline.py.  When EII_RETRIEVAL_BACKEND=ragflow, the
CRAG pipeline calls this module instead of querying the in-memory ChromaDB
collection.

Environment variables (configure as HuggingFace Secrets):
  RAGFLOW_API_KEY    — Bearer token from cloud.ragflow.io → Profile → API Key
  RAGFLOW_DATASET_ID — ID of the dataset to query (Datasets page → copy ID)

On any API error (network, auth, malformed response), retrieve_ragflow()
returns an empty list.  The CRAG pipeline then falls through to the
LLM_FALLBACK path — behaviour is identical to having zero KB candidates.
"""

import os
import requests

_BASE_URL          = "https://cloud.ragflow.io"
_RETRIEVAL_PATH    = "/api/v1/retrieval"
_REQUEST_TIMEOUT   = 15  # seconds


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_synthetic_item(chunk: dict) -> dict:
    """
    Maps a RAGFlow chunk to the KB item dict expected by grade() and generate().

    RAGFlow chunk fields consumed:
      id            → item["id"]
      document_name → item["titulo"]
      content       → item["descricao"] (truncated) + item["causa_raiz"] (full)

    Fields not available from a chunk (evento, codigo_erro, passos_resolucao,
    etc.) are set to empty strings / empty lists so downstream code that
    accesses them does not raise KeyError.
    """
    content = chunk.get("content", "")
    return {
        "id":               chunk.get("id", ""),
        "evento":           "",
        "codigo_erro":      "",
        "titulo":           chunk.get("document_name", chunk.get("id", "RAGFlow chunk")),
        "descricao":        content[:500],
        "causa_raiz":       content,
        "tags":             [],
        "impacto":          "",
        "passos_resolucao": [],
        "validacao":        "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def retrieve_ragflow(query: str, n: int = 5, dataset_id: str = "") -> list:
    """
    Retrieves the top-n chunks from RAGFlow Cloud for *query*.

    Calls POST https://cloud.ragflow.io/api/v1/retrieval with:
      {"question": query, "dataset_ids": [dataset_id], "top_k": n}

    Returns list[dict] in the same format as crag_pipeline.retrieve():
      [{"id": str, "distance": float, "item": dict}, ...]

    RAGFlow returns a relevance *score* in [0, 1]; this is converted to a
    *distance* via  distance = 1 - score  so the shape matches ChromaDB output
    (lower distance = more similar).

    Falls back to [] on:
      - Missing RAGFLOW_API_KEY or RAGFLOW_DATASET_ID
      - HTTP error (4xx / 5xx)
      - Network timeout or connection error
      - Unexpected response shape

    Args:
        query:      Free-text query built from the parsed eSocial XML.
        n:          Maximum number of results to return.
        dataset_id: RAGFlow dataset ID to search.  When empty, reads
                    RAGFLOW_DATASET_ID from the environment.
    """
    api_key = os.environ.get("RAGFLOW_API_KEY", "")
    if not api_key:
        return []

    effective_dataset_id = dataset_id or os.environ.get("RAGFLOW_DATASET_ID", "")
    if not effective_dataset_id:
        return []

    payload = {
        "question":    query,
        "dataset_ids": [effective_dataset_id],
        "top_k":       n,
    }

    try:
        response = requests.post(
            f"{_BASE_URL}{_RETRIEVAL_PATH}",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            json=payload,
            timeout=_REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            return []

        data   = response.json()
        chunks = data.get("data", {}).get("chunks", [])

        results = []
        for chunk in chunks[:n]:
            score = float(chunk.get("score", 0.0))
            results.append({
                "id":       chunk.get("id", ""),
                "distance": round(1.0 - score, 4),  # similarity → distance
                "item":     _build_synthetic_item(chunk),
            })
        return results

    except Exception:
        return []
