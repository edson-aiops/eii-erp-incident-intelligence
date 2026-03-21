"""
scripts/ingest_ragflow.py — Ingestão do KB eSocial no RAGFlow Cloud

Lê os 20 itens de KB (knowledge_base.py), serializa cada um como texto
corrido em parágrafos contínuos (_format_general) e faz upload para o
dataset RAGFlow configurado via variáveis de ambiente.

O formato de texto é compatível com o chunker General do RAGFlow
(chunk_method="general", max_token_per_chunk=1024). Cada item do KB
ocupa ~400–600 tokens — dentro do limite do chunk único por documento.

Uso:
    cd eii-brasil/
    # Com dataset já existente:
    RAGFLOW_API_KEY=ragflow-XXX RAGFLOW_DATASET_ID=<UUID> python scripts/ingest_ragflow.py

    # Criar dataset automaticamente (omita RAGFLOW_DATASET_ID):
    RAGFLOW_API_KEY=ragflow-XXX python scripts/ingest_ragflow.py

Variáveis de ambiente:
    RAGFLOW_API_KEY     — Bearer token (obrigatório)
    RAGFLOW_DATASET_ID  — UUID do dataset de destino (opcional; cria um novo se ausente)
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

BASE_URL        = "https://cloud.ragflow.io"
DATASET_PATH    = "/api/v1/datasets"
UPLOAD_PATH     = "/api/v1/datasets/{dataset_id}/documents"
REQUEST_TIMEOUT = 30  # segundos

DATASET_NAME          = "eii-esocial"
CHUNK_METHOD          = "general"
MAX_TOKEN_PER_CHUNK   = 1024


def _require_env(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        print(f"[ERRO] Variavel de ambiente ausente: {name}")
        print(f"       Defina via: set {name}=...")
        sys.exit(1)
    return val


# ─────────────────────────────────────────────────────────────────────────────
# Formatador General — texto corrido, sem cabeçalhos em maiúsculas
# ─────────────────────────────────────────────────────────────────────────────

def _format_general(item: dict) -> str:
    """
    Serializa um item do KB como texto corrido em parágrafos contínuos.

    Compatível com o chunker General do RAGFlow. Sem cabeçalhos de seção
    em maiúsculas separados por linhas em branco — o General chunker
    trata toda a estrutura como texto plain e divide por limite de tokens.

    Os rótulos 'Evento eSocial:' e 'Código de Erro:' ficam na primeira
    linha para que _build_synthetic_item() os extraia via regex mesmo
    quando o chunk retornado for parcial.

    Com max_token_per_chunk=1024 e itens de ~400–600 tokens, cada
    documento gera exatamente 1 chunk — preservando todo o contexto.
    """
    steps_lines = "\n".join(
        f"{i + 1}. {passo}"
        for i, passo in enumerate(item.get("passos_resolucao", []))
    )
    tags = ", ".join(item.get("tags", []))

    return (
        f"{item['id']} — Evento eSocial: {item['evento']} — "
        f"Código de Erro: {item['codigo_erro']} — {item['titulo']}. "
        f"Impacto: {item.get('impacto', '—')}. Tags: {tags}.\n\n"
        f"{item['descricao']}\n\n"
        f"{item['causa_raiz']}\n\n"
        f"{steps_lines}\n\n"
        f"{item['validacao']} "
        f"Tempo estimado: {item.get('tempo_estimado', '—')}.\n"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Dataset creation
# ─────────────────────────────────────────────────────────────────────────────

def _create_dataset(api_key: str, name: str = DATASET_NAME) -> str:
    """
    Cria um dataset RAGFlow com chunker General e 1024 tokens por chunk.

    POST /api/v1/datasets
    {
      "name": "eii-esocial",
      "chunk_method": "general",
      "parser_config": {"chunk_token_count": 1024}
    }

    Retorna o dataset_id (UUID) em sucesso, string vazia em falha.
    """
    url     = BASE_URL + DATASET_PATH
    payload = {
        "name":         name,
        "chunk_method": CHUNK_METHOD,
        "parser_config": {"chunk_token_count": MAX_TOKEN_PER_CHUNK},
    }
    try:
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code in (200, 201):
            body = resp.json()
            if body.get("code", -1) == 0:
                dataset_id = body["data"]["id"]
                print(f"  Dataset criado: {dataset_id}")
                print(f"  Salve como: RAGFLOW_DATASET_ID={dataset_id}")
                return dataset_id
            print(f"  API retornou code={body.get('code')}: {body.get('message', '')}")
        else:
            print(f"  HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as exc:
        print(f"  Erro de conexão: {exc}")
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Upload
# ─────────────────────────────────────────────────────────────────────────────

def _upload_document(api_key: str, dataset_id: str, filename: str, content: str) -> bool:
    """
    Faz upload de um documento texto para o dataset RAGFlow.

    Usa multipart/form-data com campo 'file' conforme a API v0.19.0.
    Retorna True em sucesso, False em falha.
    """
    url        = BASE_URL + UPLOAD_PATH.format(dataset_id=dataset_id)
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
        if body.get("code", -1) == 0:
            return True
        print(f"    ✗ API retornou code={body.get('code')}: {body.get('message', '')}")
        return False

    print(f"    ✗ HTTP {response.status_code}: {response.text[:200]}")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Smoke test — 3 queries representativas
# ─────────────────────────────────────────────────────────────────────────────

def _smoke_test() -> None:
    """
    Valida o retrieval com 3 queries representativas do KB eSocial.

    Para cada query, verifica se o documento esperado aparece no top-3.
    Exibe document_name e score de cada resultado.

    Nota: os documentos podem levar 30 s – 5 min para serem indexados
    após o upload. Execute novamente se o resultado for vazio.
    """
    from ragflow_client import retrieve_ragflow

    queries = [
        ("E428 indRetif retificação S-1200",    "KB001"),
        ("E312 vínculo não encontrado",          "KB006"),
        ("certificado digital expirado E214",    "KB003"),
    ]

    all_passed = True
    print(f"\n{'='*62}")
    print("  Smoke test — RAGFlow retrieval (3 queries)")
    print(f"{'='*62}")

    for query, expected_id in queries:
        print(f'\nQuery : "{query}"')
        print(f"Esperado no top-3: {expected_id}")
        print(f"{'-'*50}")

        results = retrieve_ragflow(query=query, n=3)

        if not results:
            print("  [AVISO] Nenhum resultado — documentos ainda sendo indexados?")
            print("  Aguarde ~1 min e rode novamente.")
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

            print(f"  [{i}] document_name : {doc_name}")
            print(f"       score         : {score:.4f}")
            print(f"       evento        : {evento}   codigo_erro: {codigo}")
            print(f"       passos extraídos: {passos_n}")

            if expected_id in doc_name or expected_id in r.get("id", ""):
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
    api_key    = _require_env("RAGFLOW_API_KEY")
    dataset_id = os.environ.get("RAGFLOW_DATASET_ID", "")

    if not dataset_id:
        print(f"RAGFLOW_DATASET_ID ausente — criando dataset '{DATASET_NAME}'...")
        dataset_id = _create_dataset(api_key)
        if not dataset_id:
            print("[ERRO] Falha ao criar dataset. Defina RAGFLOW_DATASET_ID manualmente.")
            sys.exit(1)

    print(f"\nDataset : {dataset_id}")
    print(f"Chunker : {CHUNK_METHOD}  |  max_token_per_chunk: {MAX_TOKEN_PER_CHUNK}")
    print(f"KB items: {len(KB)}\n")

    success = 0
    failed  = []

    for item in KB:
        doc_id   = item["id"]
        titulo   = item["titulo"]
        filename = f"{doc_id}_{item['evento'].replace('/', '_').replace(' ', '_')}.txt"
        content  = _format_general(item)

        ok = _upload_document(api_key, dataset_id, filename, content)
        if ok:
            print(f"  [OK]     {doc_id} — {titulo}")
            success += 1
        else:
            print(f"  [FALHOU] {doc_id} — {titulo}")
            failed.append(doc_id)

    print(f"\n{'-'*62}")
    print(f"Upload concluído: {success}/{len(KB)} documentos enviados")
    if failed:
        print(f"Falhas: {', '.join(failed)}")
    print(f"{'-'*62}")

    _smoke_test()


if __name__ == "__main__":
    main()
