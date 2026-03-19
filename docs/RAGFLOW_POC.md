# RAGFlow Cloud — POC Dual-Backend

Este documento descreve como configurar o backend RAGFlow Cloud como alternativa
ao ChromaDB in-memory para o passo de retrieval do pipeline CRAG.

## Arquitetura do dual-backend

```
EII_RETRIEVAL_BACKEND=chromadb (padrão)
  └─ retrieve() → ChromaDB in-memory → 20 itens do KB hardcoded

EII_RETRIEVAL_BACKEND=ragflow
  └─ retrieve() → ragflow_client.retrieve_ragflow()
                → POST cloud.ragflow.io/api/v1/retrieval
                → Dataset configurado via RAGFLOW_DATASET_ID
```

O fallback é automático: se a API RAGFlow retornar erro ou as variáveis de
ambiente não estiverem configuradas, `retrieve_ragflow()` retorna `[]` e o
pipeline segue pelo caminho `LLM_FALLBACK` — sem quebrar nada.

---

## 1. Criar conta no RAGFlow Cloud

1. Acesse **https://cloud.ragflow.io**
2. Clique em **Sign Up** e crie uma conta (Google OAuth ou e-mail)
3. Confirme o e-mail e faça login

---

## 2. Obter a API Key

1. No canto superior direito, clique no seu avatar → **Profile**
2. Role até a seção **API Key**
3. Clique em **Create new key**
4. Copie a chave gerada — ela começa com `ragflow-`
5. Guarde-a com segurança: ela não fica visível novamente após fechar o modal

---

## 3. Criar um Dataset e obter o dataset_id

### 3a. Criar o dataset

1. No menu lateral, clique em **Datasets**
2. Clique em **+ New dataset**
3. Preencha:
   - **Name:** `eii-esocial`
   - **Embedding model:** deixe o padrão (`BAAI/bge-large-zh-v1.5`) ou escolha
     outro modelo de embedding disponível
   - **Chunk method:** `General` para texto plain; `Paper` ou `Manual` se for
     ingerir PDFs estruturados (ex.: manual eSocial)
4. Clique em **Save**

### 3b. Fazer upload dos documentos

Opção A — Upload manual via UI:
1. Abra o dataset criado
2. Clique em **+ Add file**
3. Faça upload de arquivos `.txt`, `.pdf` ou `.docx` com o conteúdo do KB

Opção B — Upload via API REST (automatizável):
```bash
curl -X POST https://cloud.ragflow.io/api/v1/document/upload \
  -H "Authorization: Bearer ragflow-XXXXX" \
  -F "file=@knowledge_base_esocial.txt" \
  -F "dataset_id=<DATASET_ID>"
```

### 3c. Obter o dataset_id

1. Na página do dataset, olhe a URL do browser:
   `https://cloud.ragflow.io/dataset/<DATASET_ID>`
2. Copie o `<DATASET_ID>` — é um UUID hexadecimal

Alternativa via API:
```bash
curl https://cloud.ragflow.io/api/v1/dataset?name=eii-esocial \
  -H "Authorization: Bearer ragflow-XXXXX"
```
O campo `id` na resposta é o `dataset_id`.

### 3d. Aguardar o parsing

Após o upload, o RAGFlow processa (chunking + embedding) os documentos
automaticamente. O status muda para **Ready** quando estiver completo.
Tempo típico: 30 segundos a 5 minutos dependendo do tamanho dos arquivos.

---

## 4. Configurar secrets no HuggingFace Spaces

1. Acesse o seu Space em **https://huggingface.co/spaces/\<user\>/\<space\>**
2. Clique em **Settings** (aba no topo)
3. Seção **Repository secrets** → **New secret**
4. Adicione os dois secrets:

| Nome | Valor |
|---|---|
| `RAGFLOW_API_KEY` | `ragflow-XXXXX...` (copiado no passo 2) |
| `RAGFLOW_DATASET_ID` | UUID do dataset (copiado no passo 3c) |

5. Clique em **Add secret** para cada um
6. Reinicie o Space (Settings → Factory reset, ou faça um novo push)

---

## 5. Alternar entre backends

### Usar RAGFlow Cloud

```bash
# Localmente (arquivo .env ou export)
export EII_RETRIEVAL_BACKEND=ragflow
export RAGFLOW_API_KEY=ragflow-XXXXX
export RAGFLOW_DATASET_ID=<UUID>
python app.py
```

No HuggingFace Spaces, adicione também `EII_RETRIEVAL_BACKEND=ragflow` como
secret (ou variável de ambiente do Space).

### Voltar para ChromaDB (padrão)

```bash
# Remover a variável ou setar para chromadb
unset EII_RETRIEVAL_BACKEND
# ou
export EII_RETRIEVAL_BACKEND=chromadb
```

Sem a variável configurada, o pipeline usa ChromaDB automaticamente.

---

## 6. Verificar se o backend RAGFlow está ativo

Após processar um XML, o campo `_meta.retrieval_backend` no diagnóstico indica
qual backend foi usado:

```json
{
  "_meta": {
    "retrieval_backend": "ragflow",
    "candidates_retrieved": 3,
    "candidates_relevant": 2,
    ...
  }
}
```

---

## 7. Estrutura dos arquivos adicionados

```
eii-brasil/
├── ragflow_client.py          ← cliente REST para RAGFlow Cloud
├── crag_pipeline.py           ← retrieve() com feature flag (backend=)
├── docker-compose.ragflow.yml ← POC self-hosted (requer Docker + 6 GB RAM)
└── docs/
    └── RAGFLOW_POC.md         ← este documento
```

---

## 8. Limitações do POC

- **Mapeamento de chunks:** `retrieve_ragflow()` constrói um `item` sintético a
  partir do chunk retornado. Os campos `evento`, `codigo_erro` e
  `passos_resolucao` ficam vazios — o LLM depende do campo `causa_raiz` (conteúdo
  completo do chunk) para gerar o diagnóstico. Para máxima qualidade, estruture
  os documentos no dataset com os mesmos campos do KB atual.

- **Sem filtro por evento:** a busca atual usa `top_k` global. Em produção, use
  múltiplos datasets (um por tipo de evento) e roteie via `RAGFLOW_DATASET_ID`
  conforme `parsed_xml.tipo_evento`.

- **Latência:** a API RAGFlow Cloud adiciona ~200–800 ms de latência de rede
  comparado ao ChromaDB in-memory local. Aceitável para o fluxo HITL do EII.
