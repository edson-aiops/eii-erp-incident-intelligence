"""
scripts/ingest_ragflow.py — Ingestão do KB eSocial no RAGFlow Cloud

Lê os 20 itens de KB (knowledge_base.py), serializa cada um como
um arquivo .txt em formato Q&A e faz upload para o dataset RAGFlow
configurado via variáveis de ambiente.

Uso:
    cd eii-brasil/
    RAGFLOW_API_KEY=ragflow-XXX RAGFLOW_DATASET_ID=<UUID> python scripts/ingest_ragflow.py

Variáveis de ambiente:
    RAGFLOW_API_KEY     — Bearer token (obrigatório)
    RAGFLOW_DATASET_ID  — UUID do dataset de destino (obrigatório)
"""

import os
import sys
import io
import requests

# Garante que o módulo knowledge_base é encontrado ao rodar de scripts/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from knowledge_base import KB

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

BASE_URL       = "https://cloud.ragflow.io"
UPLOAD_PATH    = "/api/v1/datasets/{dataset_id}/documents"
REQUEST_TIMEOUT = 30  # segundos


def _require_env(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        print(f"[ERRO] Variavel de ambiente ausente: {name}")
        print(f"       Defina via: set {name}=...")
        sys.exit(1)
    return val


# ─────────────────────────────────────────────────────────────────────────────
# Formatador Q&A
# ─────────────────────────────────────────────────────────────────────────────

def _format_qa(item: dict) -> str:
    """
    Serializa um item do KB como documento texto Q&A.

    O formato expõe explicitamente cada campo relevante para que o
    chunking e o embedding do RAGFlow capturem o contexto completo,
    incluindo códigos de erro, passos de resolução e tags.
    """
    passos = "\n".join(
        f"  {i + 1}. {passo}"
        for i, passo in enumerate(item.get("passos_resolucao", []))
    )
    tags = ", ".join(item.get("tags", []))

    return (
        f"ID: {item['id']}\n"
        f"Evento eSocial: {item['evento']}\n"
        f"Código de Erro: {item['codigo_erro']}\n"
        f"Título: {item['titulo']}\n"
        f"Impacto: {item.get('impacto', '—')}\n"
        f"Tags: {tags}\n"
        "\n"
        "DESCRIÇÃO DO PROBLEMA:\n"
        f"{item['descricao']}\n"
        "\n"
        "CAUSA RAIZ:\n"
        f"{item['causa_raiz']}\n"
        "\n"
        "PASSOS DE RESOLUÇÃO:\n"
        f"{passos}\n"
        "\n"
        "VALIDAÇÃO:\n"
        f"{item['validacao']}\n"
        "\n"
        f"TEMPO ESTIMADO: {item.get('tempo_estimado', '—')}\n"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Upload
# ─────────────────────────────────────────────────────────────────────────────

def _upload_document(api_key: str, dataset_id: str, filename: str, content: str) -> bool:
    """
    Faz upload de um documento texto para o dataset RAGFlow.

    Usa multipart/form-data com campo 'file' conforme a API v0.19.0.
    Retorna True em sucesso, False em falha.
    """
    url = BASE_URL + UPLOAD_PATH.format(dataset_id=dataset_id)
    file_bytes = content.encode("utf-8")

    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (filename, io.BytesIO(file_bytes), "text/plain")},
            timeout=REQUEST_TIMEOUT,
        )
    except Exception as exc:
        print(f"    ✗ Erro de conexão: {exc}")
        return False

    if response.status_code == 200:
        body = response.json()
        # A API retorna code=0 em sucesso
        if body.get("code", -1) == 0:
            return True
        # Alguns erros chegam com HTTP 200 mas code != 0
        print(f"    ✗ API retornou code={body.get('code')}: {body.get('message', '')}")
        return False

    print(f"    ✗ HTTP {response.status_code}: {response.text[:200]}")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Smoke test
# ─────────────────────────────────────────────────────────────────────────────

def _smoke_test() -> None:
    """Chama retrieve_ragflow() e imprime os resultados."""
    # Importação local para garantir que o sys.path está correto
    from ragflow_client import retrieve_ragflow

    query  = "erro E312 vínculo não encontrado"
    print(f"\n{'-'*60}")
    print(f"Smoke test — query: \"{query}\"  n=3")
    print(f"{'-'*60}")

    results = retrieve_ragflow(query=query, n=3)

    if not results:
        print("  [AVISO] Nenhum resultado retornado.")
        print("  Possiveis causas:")
        print("  - Documentos ainda sendo processados pelo RAGFlow (aguarde ~1 min)")
        print("  - RAGFLOW_API_KEY ou RAGFLOW_DATASET_ID incorretos")
        print("  - Dataset vazio ou parsing ainda em andamento")
        return

    for i, r in enumerate(results, 1):
        item  = r["item"]
        score = round(1.0 - r["distance"], 4)
        print(f"\n  [{i}] id={r['id'][:16]}…")
        print(f"      score={score:.4f}  distance={r['distance']:.4f}")
        print(f"      documento: {item['titulo'][:80]}")
        content_preview = item['descricao'][:120].replace('\n', ' ')
        print(f"      trecho: {content_preview}…")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    api_key    = _require_env("RAGFLOW_API_KEY")
    dataset_id = _require_env("RAGFLOW_DATASET_ID")

    print(f"Dataset: {dataset_id}")
    print(f"Total de itens KB: {len(KB)}\n")

    success = 0
    failed  = []

    for item in KB:
        doc_id    = item["id"]
        titulo    = item["titulo"]
        filename  = f"{doc_id}_{item['evento'].replace('/', '_').replace(' ', '_')}.txt"
        content   = _format_qa(item)

        ok = _upload_document(api_key, dataset_id, filename, content)
        if ok:
            print(f"  [OK] {doc_id} - {titulo}")
            success += 1
        else:
            print(f"  [FALHOU] {doc_id} - {titulo}")
            failed.append(doc_id)

    print(f"\n{'-'*60}")
    print(f"Upload concluído: {success}/{len(KB)} documentos enviados")
    if failed:
        print(f"Falhas: {', '.join(failed)}")
    print(f"{'-'*60}")

    _smoke_test()


if __name__ == "__main__":
    main()
