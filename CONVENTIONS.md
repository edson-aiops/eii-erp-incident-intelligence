# CONVENTIONS.md — EII (ERP Incident Intelligence)

> Convenções obrigatórias para qualquer contribuidor (humano ou IA) neste repositório.
> Ler junto com CONTEXT.md e ROADMAP.md antes de qualquer tarefa.
> Última atualização: 2026-09

## Ambiente de desenvolvimento

- **SO de referência:** Windows + **CMD como terminal padrão**
  - Use `findstr` / `dir` / `type` — NÃO `grep` / `ls` / `cat`
  - `Select-Object -First N` em vez de `head` (quando em PowerShell)
- **PowerShell:** escrever arquivos com here-string `@'...'@` + `Out-File -Encoding UTF8`
- **Git commit no CMD:** `-m` repetido em linha única (mensagem multilinha quebra no CMD):
  ```cmd
  git commit -m "feat: add parse_xml_auto" -m "Detecta eSocial vs EFD-Reinf automaticamente"
  ```
- **Python:** 3.11–3.13 (CI roda matriz 3.11/3.13); desenvolvimento em 3.13
- **Cloud dev:** GitHub Codespaces via `.devcontainer/` (ambiente Linux — nesse caso
  bash vale, mas scripts entregues devem considerar o Windows do autor)

## Comandos essenciais

```cmd
REM Rodar suíte completa (obrigatório antes de entregar qualquer coisa)
python -m pytest -v

REM Verificação rápida de sintaxe antes de entregar
python -m py_compile <arquivo.py>

REM App local interno (auth + HITL + dados reais — NUNCA vai pra HF)
python app.py

REM Demo pública (vai pro HF Space via Docker)
python app_hf.py

REM API REST
uvicorn eii_api:app --port 8000
```

## Git

- **Branches:** `feature/claude-<descricao>` (histórico) ou `feature/<descricao>`
- **Commits:** Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`)
- **Push:** somente Edson. IAs executoras NUNCA fazem push
- **Entrega de código:** diff por arquivo + `py_compile` passando + suíte verde

## Workflow de 3 atores (obrigatório)

1. **Especificador (IA):** escreve spec + testes black-box a partir da spec,
   SEM ler a implementação
2. **Executor (IA local):** implementa. Regras:
   - NUNCA altera testes existentes — se um teste parecer errado, **PARE e escale**
   - NUNCA faz push
   - Escala requisitos ambíguos em vez de adivinhar
   - Roda a suíte completa: zero regressão
3. **Edson:** única autoridade de revisão, merge e push

## Merge gate: EVIDENCE_PACK.md

Todo PR/entrega inclui EVIDENCE_PACK.md com:
- Diff completo por arquivo
- Saída REAL da suíte de testes (não resumida)
- Confirmação explícita: "nenhum teste existente foi alterado para passar"
- Blast radius (o que pode quebrar)
- Rollback path
- Métrica real OU declaração explícita "sem métrica nova"
- Nota: "testes verdes" sozinhos não contam a história — o que importa é o que
  a revisão do diff revela

## Testes

- **Fixtures de PII:** XMLs como **constantes no próprio módulo de teste** (não em
  arquivos separados editáveis) quando a asserção depende de valores exatos —
  arquivo editável + teste verde = falso verde silencioso
- **Suíte determinística offline:** `conftest.py` autouse injeta dummy API keys —
  testes nunca dependem de rede ou chaves reais
- **Datetime:** converter via `astimezone(UTC)` antes de subtrair (subtração de
  datetimes aware com mesmo tzinfo retorna wall-clock, não tempo decorrido)
- **Testes de vazamento PII:** asserir valores sensíveis explicitamente — teste
  genérico de substring mede coincidência de alfabeto, não vazamento

## Segredos e credenciais

- **Windows:** Credential Manager via `keyring.set_password()` — NUNCA `cmdkey`
- **Linux/Contabo/Codespaces:** variáveis de ambiente / secrets do GitHub
- **NUNCA** hardcoded, NUNCA commitado, NUNCA em logs
- Chaves atuais: `OPENROUTER_API_KEY`, `QDRANT_API_KEY` (read-only), `QDRANT_URL`

## Dependências

- **`groq==0.31.0` pinado** em todos os projetos (quebras de API em versões novas)
- **Gradio 4.44.0 pinado** (bug `unhashable type: 'dict'` com Jinja2 recente)
- Ao adicionar dependência: justificar no PR e atualizar requirements.txt

## LGPD / Segurança (inegociável)

- Scrubbing PII é **passo incondicional** antes de qualquer chamada remota
- Terminologia: **pseudonimização** (mapa reversível no servidor), nunca "anonimização"
- OpenRouter: apenas perfil `mode=test` com dado sintético; NUNCA no fluxo LGPD
- Em produção: integrações diretas (sem hop extra nem taxa de gateway)
- `scrub_pii()` cobre: CPF (formatado e bare), CNPJ, NIS, nmTrab

## Métricas e comunicação pública

- Só número de **benchmark real** sobre dataset sintético versionado vai a público
- MTTR −70%, auto-resolve ≥70%, HITL ≤30% = **design targets**, sempre rotulados
- Nunca nomear empregador atual nem vendors ERP/HCM em artefatos públicos
  (regra retroativa) — usar "ERP"/"HCM" genérico

## Estilo de código

- Type hints; `Diagnosis` tipada com `ConfidenceLevel Literal` (Fase 5.2 NOAA)
- Evitar `Dict[str, Any]` em estruturas de domínio — usar dataclasses
- Scripts ad-hoc vivem em `scripts/dev/`, nunca na raiz
- Nenhum script com `exit()` solto (quebra coleta do pytest)

## UI (quando aplicável)

- Padrão AcademyTracker: dark `#0A0E1A`, teal `#00D4AA`, monospace
- ECG visual do SmartRouter: reservado para carrossel LinkedIn, NÃO para o app
