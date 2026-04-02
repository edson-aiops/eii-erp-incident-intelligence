"""
Qdrant Cloud retrieval client — backend for eii-brasil.

Provides retrieve_qdrant() as a drop-in complement to the ChromaDB-based
retrieve() in crag_pipeline.py.  When EII_RETRIEVAL_BACKEND=qdrant, the
CRAG pipeline calls this module instead of querying the in-memory ChromaDB
collection.

Environment variables (configure as HuggingFace Secrets):
  QDRANT_API_KEY — API key from cloud.qdrant.io → Cluster → API Keys
  QDRANT_URL     — Cluster URL (optional; falls back to _DEFAULT_URL)

Embedding model: sentence-transformers/all-MiniLM-L6-v2  (384 dims)
Collection     : eii_esocial
Distance metric: Cosine  (score ∈ [0,1]; distance = 1 - score)

On any error (network, auth, missing env var, unexpected response shape),
retrieve_qdrant() returns [].  The CRAG pipeline then falls through to the
LLM_FALLBACK path — behaviour identical to having zero KB candidates.
"""

import os
import logging
import requests

_log = logging.getLogger(__name__)

_DEFAULT_URL    = "https://7475580f-5477-4ecf-952a-151442465cad.us-east4-0.gcp.cloud.qdrant.io"
_COLLECTION     = "eii_esocial"
_REQUEST_TIMEOUT = 15  # seconds

# Lazy-loaded SentenceTransformer model (initialised on first _embed() call).
_model = None


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _embed(text: str) -> list:
    """
    Returns a 384-dim float list for *text* using all-MiniLM-L6-v2.

    The model is loaded lazily on the first call and cached in _model so that
    importing this module is free — no GPU/CPU spin-up until retrieval is
    actually requested.
    """
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model.encode(text).tolist()


def _build_item_from_payload(payload: dict) -> dict:
    """
    Reconstructs the full KB item dict from a Qdrant point payload.

    All 11 KB fields are stored verbatim in the payload at ingest time
    (scripts/ingest_qdrant.py).  This function is the inverse of that
    serialisation — it simply reads them back, with safe defaults for any
    field that might be absent (e.g., chunks from external datasets).
    """
    return {
        "id":               payload.get("id",               ""),
        "evento":           payload.get("evento",           ""),
        "codigo_erro":      payload.get("codigo_erro",      ""),
        "titulo":           payload.get("titulo",           ""),
        "descricao":        payload.get("descricao",        ""),
        "causa_raiz":       payload.get("causa_raiz",       ""),
        "tags":             payload.get("tags",             []),
        "impacto":          payload.get("impacto",          ""),
        "passos_resolucao": payload.get("passos_resolucao", []),
        "validacao":        payload.get("validacao",        ""),
        "tempo_estimado":   payload.get("tempo_estimado",   ""),
    }


def _kb_id_to_point_id(kb_id: str) -> int:
    """
    Maps a KB string ID to a Qdrant numeric point ID.

    Qdrant requires point IDs to be uint64 or UUID.  The KB uses IDs of the
    form "KB001" … "KB053", so we strip the prefix and parse the integer:
      "KB001" → 1
      "KB020" → 20
      "KB053" → 53

    If the string does not match the expected pattern, falls back to abs(hash).
    """
    if kb_id.startswith("KB") and kb_id[2:].isdigit():
        return int(kb_id[2:])
    return abs(hash(kb_id)) % (2 ** 63)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def increment_validacao(kb_id: str) -> bool:
    """
    Increments the ``validacoes`` counter for a KB point in Qdrant and updates
    its ``confidence_tier`` (standard → gold at 3 approvals).

    Steps:
      1. GET  /collections/eii_esocial/points/{point_id}  — read current payload
      2. Increment ``validacoes`` (default 0 if absent)
      3. Compute ``confidence_tier``: "gold" if validacoes >= 3, else "standard"
      4. POST /collections/eii_esocial/points/payload     — overwrite the two fields

    Returns True on success, False on any error (fails silently via log).
    """
    api_key = os.environ.get("QDRANT_API_KEY", "")
    if not api_key:
        return False

    url      = os.environ.get("QDRANT_URL", _DEFAULT_URL).rstrip("/")
    point_id = _kb_id_to_point_id(kb_id)

    try:
        # ── 1. Read current payload ───────────────────────────────────────────
        r = requests.get(
            f"{url}/collections/{_COLLECTION}/points/{point_id}",
            headers={"api-key": api_key, "Content-Type": "application/json"},
            timeout=_REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            _log.warning("increment_validacao: GET point %s → HTTP %s", point_id, r.status_code)
            return False

        current_payload = r.json().get("result", {}).get("payload", {})

        # ── 2–3. Compute new values ───────────────────────────────────────────
        validacoes      = current_payload.get("validacoes", 0) + 1
        confidence_tier = "gold" if validacoes >= 3 else "standard"

        # ── 4. Patch only the two counter fields ──────────────────────────────
        patch = requests.post(
            f"{url}/collections/{_COLLECTION}/points/payload",
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json={
                "payload": {
                    "validacoes":      validacoes,
                    "confidence_tier": confidence_tier,
                },
                "points": [point_id],
            },
            timeout=_REQUEST_TIMEOUT,
        )
        if patch.status_code != 200:
            _log.warning("increment_validacao: PATCH %s → HTTP %s", point_id, patch.status_code)
            return False

        _log.info(
            "increment_validacao: %s validacoes=%d tier=%s", kb_id, validacoes, confidence_tier
        )
        return True

    except Exception as exc:
        _log.warning("increment_validacao(%s) failed: %s", kb_id, exc)
        return False


def retrieve_qdrant(query: str, n: int = 5) -> list:
    """
    Retrieves the top-n closest points from eii_esocial for *query*.

    Embeds *query* with all-MiniLM-L6-v2, then calls:
      POST {QDRANT_URL}/collections/eii_esocial/points/search
      {"vector": [...], "limit": n, "with_payload": true}

    Returns list[dict] in the same format as crag_pipeline.retrieve():
      [{"id": str, "distance": float, "document_name": str, "item": dict}, ...]

    Qdrant returns a cosine similarity *score* ∈ [0, 1]; converted to
    *distance* via  distance = 1 - score  (lower = more similar).

    Falls back to [] on:
      - Missing QDRANT_API_KEY
      - Embedding failure
      - HTTP error (4xx / 5xx)
      - Network timeout or connection error
      - Unexpected response shape
    """
    api_key = os.environ.get("QDRANT_API_KEY", "")
    if not api_key:
        return []

    url = os.environ.get("QDRANT_URL", _DEFAULT_URL).rstrip("/")

    try:
        vector = _embed(query)
    except Exception:
        return []

    payload = {
        "vector":       vector,
        "limit":        n,
        "with_payload": True,
    }

    try:
        response = requests.post(
            f"{url}/collections/{_COLLECTION}/points/search",
            headers={
                "api-key":      api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=_REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            return []

        hits = response.json().get("result", [])

        results = []
        for hit in hits[:n]:
            score           = float(hit.get("score", 0.0))
            hit_payload     = hit.get("payload", {})
            item            = _build_item_from_payload(hit_payload)
            confidence_tier = hit_payload.get("confidence_tier", "standard")
            results.append({
                "id":              item["id"],
                "distance":        round(1.0 - score, 4),  # similarity → distance
                "document_name":   item["titulo"],
                "confidence_tier": confidence_tier,
                "item":            item,
            })

        # Gold-boost: stable sort keeps original score order; gold items float
        # above standard items when distances are equal.
        results.sort(key=lambda r: (r["distance"], 0 if r["confidence_tier"] == "gold" else 1))

        return results

    except Exception:
        return []
