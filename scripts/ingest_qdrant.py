"""
scripts/ingest_qdrant.py — Ingestão do KB eSocial no Qdrant Cloud

Lê todos os itens de KB (knowledge_base.py), embeds cada um com
all-MiniLM-L6-v2 (384 dims) e faz upsert na collection eii_esocial
do cluster Qdrant Cloud configurado via variáveis de ambiente.

A collection é criada automaticamente se não existir (Cosine, size=384).
O script suporta a base atual (20 itens) e a expansão futura (53 itens)
sem alterações — basta rodar novamente após adicionar itens ao KB.

Uso:
    cd eii-brasil/
    QDRANT_API_KEY=<key> python scripts/ingest_qdrant.py

    # URL personalizada (opcional — usa o cluster padrão se omitida):
    QDRANT_API_KEY=<key> QDRANT_URL=https://... python scripts/ingest_qdrant.py

Variáveis de ambiente:
    QDRANT_API_KEY  — API key do cluster (obrigatório)
    QDRANT_URL      — URL do cluster (opcional; usa o cluster eii-brasil por padrão)
"""

import os
import sys
import requests

# Garante que os módulos da raiz são encontrados ao rodar de scripts/
_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _ROOT)

from knowledge_base import KB
from qdrant_client import _embed, _kb_id_to_point_id, _DEFAULT_URL, _COLLECTION

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

REQUEST_TIMEOUT = 30  # segundos
UPSERT_BATCH    = 20  # pontos por requisição


def _require_env(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        print(f"[ERRO] Variável de ambiente ausente: {name}")
        print(f"       Defina via: export {name}=...")
        sys.exit(1)
    return val


def _base_url() -> str:
    return os.environ.get("QDRANT_URL", _DEFAULT_URL).rstrip("/")


# ─────────────────────────────────────────────────────────────────────────────
# Texto para embedding — mesmo formato do ChromaDB (build_vector_store)
# ─────────────────────────────────────────────────────────────────────────────

def _doc_text(item: dict) -> str:
    """
    Serializa um item KB como texto para embedding.

    Reproduz exatamente o formato usado em crag_pipeline.build_vector_store()
    para garantir que o espaço vetorial do Qdrant seja idêntico ao ChromaDB
    e que os experimentos A/B comparar backends sejam válidos.
    """
    return (
        f"Evento: {item['evento']} | Erro: {item['codigo_erro']}\n"
        f"Título: {item['titulo']}\n"
        f"Descrição: {item['descricao']}\n"
        f"Causa Raiz: {item['causa_raiz']}\n"
        f"Tags: {', '.join(item.get('tags', []))}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Collection management
# ─────────────────────────────────────────────────────────────────────────────

def _collection_exists(api_key: str) -> bool:
    """Retorna True se eii_esocial já existe no cluster."""
    url = f"{_base_url()}/collections/{_COLLECTION}"
    try:
        resp = requests.get(
            url,
            headers={"api-key": api_key},
            timeout=REQUEST_TIMEOUT,
        )
        return resp.status_code == 200
    except Exception as exc:
        print(f"  [AVISO] Não foi possível verificar collection: {exc}")
        return False


def _create_collection(api_key: str) -> bool:
    """
    Cria a collection eii_esocial com:
      vectors.size     = 384  (all-MiniLM-L6-v2)
      vectors.distance = Cosine

    Retorna True em sucesso, False em falha.
    """
    url     = f"{_base_url()}/collections/{_COLLECTION}"
    payload = {
        "vectors": {
            "size":     384,
            "distance": "Cosine",
        }
    }
    try:
        resp = requests.put(
            url,
            headers={
                "api-key":      api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code in (200, 201):
            body = resp.json()
            if body.get("result") is True:
                print(f"  Collection '{_COLLECTION}' criada.")
                return True
            print(f"  API retornou: {body}")
            return False
        print(f"  HTTP {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as exc:
        print(f"  Erro de conexão: {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Upsert
# ─────────────────────────────────────────────────────────────────────────────

def _upsert_batch(api_key: str, points: list) -> bool:
    """
    Faz upsert de uma lista de pontos na collection eii_esocial.

    Cada ponto: {"id": int, "vector": list[float], "payload": dict}

    Retorna True se o Qdrant confirmou a operação.
    """
    url     = f"{_base_url()}/collections/{_COLLECTION}/points"
    payload = {"points": points}
    try:
        resp = requests.put(
            url,
            headers={
                "api-key":      api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            body = resp.json()
            return body.get("result", {}).get("status") == "acknowledged"
        print(f"    ✗ HTTP {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as exc:
        print(f"    ✗ Erro de conexão: {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Smoke test — 3 queries representativas
# ─────────────────────────────────────────────────────────────────────────────

def _smoke_test() -> None:
    """
    Valida o retrieval com 3 queries representativas do KB eSocial.

    Para cada query, verifica se o documento esperado aparece no top-3.
    Exibe document_name, score e veredicto PASS/FAIL.

    Nota: o índice pode levar alguns segundos para ficar disponível após o
    upsert. Execute novamente se o resultado for vazio.
    """
    from qdrant_client import retrieve_qdrant

    queries = [
        ("E428 indRetif retificação S-1200",  "KB001"),
        ("E312 vínculo não encontrado S-2299", "KB006"),
        ("certificado digital expirado E214",  "KB003"),
    ]

    all_passed = True
    print(f"\n{'='*62}")
    print("  Smoke test — Qdrant retrieval (3 queries)")
    print(f"{'='*62}")

    for query, expected_id in queries:
        print(f'\nQuery : "{query}"')
        print(f"Esperado no top-3: {expected_id}")
        print(f"{'-'*50}")

        results = retrieve_qdrant(query=query, n=3)

        if not results:
            print("  [AVISO] Nenhum resultado — índice ainda sendo construído?")
            print("  Aguarde alguns segundos e rode novamente.")
            all_passed = False
            continue

        found = False
        for i, r in enumerate(results, 1):
            item      = r["item"]
            score     = round(1.0 - r["distance"], 4)
            doc_name  = r.get("document_name") or item.get("titulo", "—")
            evento    = item.get("evento")    or "—"
            codigo    = item.get("codigo_erro") or "—"
            passos_n  = len(item.get("passos_resolucao", []))

            print(f"  [{i}] document_name   : {doc_name}")
            print(f"       score (cosine)  : {score:.4f}")
            print(f"       evento          : {evento}   codigo_erro: {codigo}")
            print(f"       passos extraídos: {passos_n}")

            if expected_id in item.get("id", "") or expected_id in doc_name:
                found = True

        verdict = "[PASS]" if found else "[FAIL] — esperado não encontrado no top-3"
        print(f"  → {verdict}")
        if not found:
            all_passed = False

    print(f"\n{'='*62}")
    print(f"  Resultado: {'PASSOU' if all_passed else 'FALHOU'}")
    print(f"{'='*62}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    api_key = _require_env("QDRANT_API_KEY")

    print(f"\nCluster : {_base_url()}")
    print(f"Collection: {_COLLECTION}  |  size=384  |  distance=Cosine")
    print(f"KB items  : {len(KB)}\n")

    # Garante que a collection existe
    if _collection_exists(api_key):
        print(f"  Collection '{_COLLECTION}' já existe — pulando criação.")
    else:
        print(f"  Collection '{_COLLECTION}' não encontrada — criando...")
        if not _create_collection(api_key):
            print("[ERRO] Falha ao criar collection. Verifique QDRANT_API_KEY e QDRANT_URL.")
            sys.exit(1)

    print(f"\nGerando embeddings e fazendo upsert ({len(KB)} itens)...\n")

    success = 0
    failed  = []
    batch   = []

    for item in KB:
        doc_id  = item["id"]
        titulo  = item["titulo"]
        text    = _doc_text(item)

        try:
            vector = _embed(text)
        except Exception as exc:
            print(f"  [FALHOU] {doc_id} — embedding error: {exc}")
            failed.append(doc_id)
            continue

        # Payload armazena todos os 11 campos KB para reconstrução sem KB lookup,
        # mais contadores de confidence_tier para o sistema de gold-boost.
        payload = {
            "id":               item["id"],
            "evento":           item["evento"],
            "codigo_erro":      item["codigo_erro"],
            "titulo":           item["titulo"],
            "descricao":        item["descricao"],
            "causa_raiz":       item["causa_raiz"],
            "tags":             item.get("tags", []),
            "impacto":          item.get("impacto", ""),
            "passos_resolucao": item.get("passos_resolucao", []),
            "validacao":        item.get("validacao", ""),
            "tempo_estimado":   item.get("tempo_estimado", ""),
            "validacoes":       0,
            "confidence_tier":  "standard",
        }

        batch.append({
            "id":      _kb_id_to_point_id(doc_id),
            "vector":  vector,
            "payload": payload,
        })

        # Flush batch
        if len(batch) >= UPSERT_BATCH:
            ok = _upsert_batch(api_key, batch)
            for pt in batch:
                pid = pt["payload"]["id"]
                if ok:
                    print(f"  [OK]     {pid} — {pt['payload']['titulo']}")
                    success += 1
                else:
                    print(f"  [FALHOU] {pid}")
                    failed.append(pid)
            batch = []

    # Flush remainder
    if batch:
        ok = _upsert_batch(api_key, batch)
        for pt in batch:
            pid = pt["payload"]["id"]
            if ok:
                print(f"  [OK]     {pid} — {pt['payload']['titulo']}")
                success += 1
            else:
                print(f"  [FALHOU] {pid}")
                failed.append(pid)

    print(f"\n{'-'*62}")
    print(f"Upsert concluído: {success}/{len(KB)} pontos enviados")
    if failed:
        print(f"Falhas: {', '.join(failed)}")
    print(f"{'-'*62}")

    _smoke_test()


if __name__ == "__main__":
    main()
