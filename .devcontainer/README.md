# Dev Container — EII Incident Intelligence

Ambiente pré-configurado para GitHub Codespaces (ou Docker local via Dev Containers).

---

## Como abrir o Codespace

1. Acesse o repositório no GitHub.
2. Clique em **Code → Codespaces → Create codespace on main**.
3. Aguarde o build da imagem e a execução do `postCreateCommand` (instala todas as dependências automaticamente).

---

## Como configurar os Secrets

As variáveis abaixo **não têm valores no repositório** — configure-as como *Codespace Secrets* em:

**GitHub → Settings → Codespaces → Secrets**

| Secret | Descrição |
|---|---|
| `GROQ_API_KEY` | Chave de API do Groq (LLM inference) |
| `DB_PATH` | Caminho para o banco SQLite de incidentes (padrão: `eii_incidents.db`) |
| `LANGFUSE_PUBLIC_KEY` | Chave pública do Langfuse (observabilidade) |
| `LANGFUSE_SECRET_KEY` | Chave secreta do Langfuse |
| `LANGFUSE_BASE_URL` | URL base do Langfuse (ex.: `https://cloud.langfuse.com`) |

Os secrets são injetados automaticamente como variáveis de ambiente no Codespace.

---

## Como rodar o app

```bash
python app.py
```

O Gradio sobe na porta **7860**. O VS Code abre automaticamente o preview — ou acesse a aba **Ports** e clique no link gerado.

---

## Como rodar os testes

```bash
# Suite principal (fase 2)
python -m pytest tests/test_phase2.py -v

# Smoke test end-to-end contra o HF Space (requer rede)
python scripts/test_e2e_hf.py
```
