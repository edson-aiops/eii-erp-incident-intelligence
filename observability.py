"""
EII Observability — LangSmith tracing (OBS-001).

Exports a ``traceable`` decorator shim:
  - Real langsmith.traceable when LANGSMITH_API_KEY is set and langsmith is installed.
  - No-op decorator otherwise — zero overhead in test / dev environments without a key.

Usage in crag_pipeline.py::

    from observability import traceable

    @traceable(name="EII.retrieve", metadata={"step": "retrieve"})
    def retrieve(...):
        ...
"""

import logging
import os

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

LANGSMITH_PROJECT = os.environ.get("LANGSMITH_PROJECT", "eii-esocial")

# ─────────────────────────────────────────────────────────────────────────────
# Optional import — fails silently when langsmith is not installed
# ─────────────────────────────────────────────────────────────────────────────

# Suporta tanto LANGSMITH_API_KEY (novo) quanto LANGCHAIN_API_KEY (legado)
_LANGSMITH_API_KEY = (
    os.environ.get("LANGSMITH_API_KEY")
    or os.environ.get("LANGCHAIN_API_KEY", "")
)

try:
    from langsmith import traceable as _real_traceable  # type: ignore
    _LANGSMITH_AVAILABLE = True
except ImportError:
    _real_traceable = None
    _LANGSMITH_AVAILABLE = False

_ENABLED = _LANGSMITH_AVAILABLE and bool(_LANGSMITH_API_KEY)

# Propaga project name e habilita tracing quando configurado
if _ENABLED:
    os.environ.setdefault("LANGSMITH_PROJECT", LANGSMITH_PROJECT)
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    logger.info("[observability] LangSmith tracing enabled — project=%s", LANGSMITH_PROJECT)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_tracer():
    """
    Return a LangSmith Client if LANGSMITH_API_KEY is configured, else None.

    The returned object is only needed for explicit run management.
    For decorator-based tracing, use the ``traceable`` shim below.
    """
    if not _ENABLED:
        return None
    try:
        from langsmith import Client  # type: ignore
        return Client(api_key=_LANGSMITH_API_KEY)
    except Exception:
        return None


def add_run_metadata(metadata: dict) -> None:
    """Enriquece o span LangSmith ativo com metadata adicional.

    Util para adicionar campos de negocio (incident_id, evento, confianca)
    ao span criado automaticamente pelo LangGraph ou por @traceable sem
    precisar criar um novo span filho.

    No-op quando LangSmith nao esta configurado.
    """
    if not _ENABLED:
        return
    try:
        from langsmith.run_helpers import get_current_run_tree  # type: ignore
        rt = get_current_run_tree()
        if rt is not None:
            current_extra = dict(rt.extra or {})
            current_extra.update(metadata)
            rt.extra = current_extra
    except Exception as e:
        logger.debug("[observability] add_run_metadata failed: %s", e)


def traceable(name: str = None, run_type: str = "chain",
              metadata: dict = None, **kwargs):
    """
    Decorator factory — wraps langsmith.traceable when tracing is enabled.

    Parameters
    ----------
    name      : Display name for the span in LangSmith UI.
    run_type  : LangSmith run type (chain / llm / tool / retriever / …).
    metadata  : Static key-value pairs attached to every run of this span.
    **kwargs  : Forwarded to langsmith.traceable when enabled.

    Returns a no-op decorator when LANGSMITH_API_KEY is absent or langsmith
    is not installed, so all call sites compile and run without changes.
    """
    def decorator(fn):
        if not _ENABLED or _real_traceable is None:
            return fn
        return _real_traceable(
            name=name,
            run_type=run_type,
            metadata=metadata or {},
            **kwargs,
        )(fn)
    return decorator
