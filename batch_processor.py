"""
EII — Batch Processor
Parallel analysis of multiple eSocial XMLs via ThreadPoolExecutor.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from xml_parser import parse_esocial_xml
from crag_pipeline import run_crag


# ─────────────────────────────────────────────────────────────────────────────
# Internal — single-XML worker
# ─────────────────────────────────────────────────────────────────────────────

def _process_one(xml: str, collection, inc_id: str) -> dict:
    """Analyze one XML through the CRAG pipeline. Always returns a dict."""
    t0 = time.time()
    _err = lambda msg: {          # noqa: E731
        "incident_id": inc_id,
        "evento":      "—",
        "codigo_erro": "—",
        "severidade":  "—",
        "confianca":   "—",
        "fonte":       "—",
        "status":      f"ERROR: {msg}",
        "elapsed_s":   round(time.time() - t0, 1),
    }

    try:
        if not xml or not xml.strip():
            return _err("XML vazio")

        parsed = parse_esocial_xml(xml.strip())

        if parsed.erro:
            return {
                "incident_id": inc_id,
                "evento":      "—",
                "codigo_erro": "PARSE_ERROR",
                "severidade":  "—",
                "confianca":   "—",
                "fonte":       "PARSE_ERROR",
                "status":      f"ERROR: {parsed.erro[:120]}",
                "elapsed_s":   round(time.time() - t0, 1),
            }

        diagnosis = run_crag(collection, parsed, inc_id)

        return {
            "incident_id": inc_id,
            "evento":      diagnosis.get("evento",      "—"),
            "codigo_erro": diagnosis.get("codigo_erro", "—"),
            "severidade":  diagnosis.get("severidade",  "—"),
            "confianca":   diagnosis.get("confianca",   "—"),
            "fonte":       diagnosis.get("fonte",       "—"),
            "status":      "OK",
            "elapsed_s":   round(time.time() - t0, 1),
        }

    except Exception as exc:  # noqa: BLE001
        return _err(str(exc)[:120])


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def _make_batch_ids(n: int) -> list[str]:
    """Generate unique incident IDs for a batch. Suffix B01…Bnn avoids collisions."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return [f"INC-{ts}-B{i + 1:02d}" for i in range(n)]


def batch_analyze(xml_list: list[str], max_workers: int = 3,
                  collection=None) -> list[dict]:
    """
    Analyze multiple eSocial XMLs in parallel.

    Args:
        xml_list:    List of raw XML strings.
        max_workers: Thread pool size (clamped to 1–5).
        collection:  ChromaDB collection. If None, a new one is built.

    Returns:
        List of result dicts (same order as xml_list), each with keys:
        incident_id, evento, codigo_erro, severidade, confianca, fonte,
        status (OK | ERROR: <msg>), elapsed_s.
    """
    if collection is None:
        from crag_pipeline import build_vector_store  # deferred — avoids circular import
        collection = build_vector_store()

    workers = max(1, min(5, max_workers))
    inc_ids = _make_batch_ids(len(xml_list))
    results: list[dict | None] = [None] * len(xml_list)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_process_one, xml_list[i], collection, inc_ids[i]): i
            for i in range(len(xml_list))
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as exc:  # noqa: BLE001
                results[idx] = {
                    "incident_id": inc_ids[idx],
                    "evento":      "—",
                    "codigo_erro": "—",
                    "severidade":  "—",
                    "confianca":   "—",
                    "fonte":       "—",
                    "status":      f"ERROR: {exc}",
                    "elapsed_s":   0.0,
                }

    return results  # type: ignore[return-value]


def batch_analyze_streaming(xml_list: list[str], max_workers: int = 3,
                            collection=None):
    """
    Generator version of batch_analyze.
    Yields (completed_count, partial_results) after each XML finishes.
    partial_results preserves original order (None for not-yet-done items).
    """
    if collection is None:
        from crag_pipeline import build_vector_store  # deferred
        collection = build_vector_store()

    workers = max(1, min(5, max_workers))
    n = len(xml_list)
    inc_ids = _make_batch_ids(n)
    results: list[dict | None] = [None] * n

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_process_one, xml_list[i], collection, inc_ids[i]): i
            for i in range(n)
        }
        completed = 0
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as exc:  # noqa: BLE001
                results[idx] = {
                    "incident_id": inc_ids[idx],
                    "evento":      "—",
                    "codigo_erro": "—",
                    "severidade":  "—",
                    "confianca":   "—",
                    "fonte":       "—",
                    "status":      f"ERROR: {exc}",
                    "elapsed_s":   0.0,
                }
            completed += 1
            yield completed, list(results)   # snapshot — caller may mutate freely
