# EVIDENCE_PACK — PII Scrubber Obrigatório

| Item | Valor |
|---|---|
| **Feature** | `feature/claude-mandatory-pii-scrubber` |
| **Spec** | `docs/PII-SCRUBBER-SPEC.md` |
| **Executor** | Kimi Code CLI |
| **Release owner** | Edson (única autoridade de push/merge) |
| **Data** | 2026-08-31 |

---

## 1. Diff completo

Arquivos criados:

```text
src/privacy/__init__.py
src/privacy/scrubber.py
tests/fixtures/pii/s1200_com_cpf.xml
tests/fixtures/pii/s1200_com_nis.xml
tests/fixtures/pii/s1200_com_rubrica.xml
tests/fixtures/pii/s1200_padrao.xml
tests/fixtures/pii/s1200_rejeitado.xml
tests/fixtures/pii/s2200_com_nome.xml
tests/test_pii_scrubber.py
EVIDENCE_PACK-scrubber.md
```

Arquivos alterados:

```text
src/utils/scrubber.py  (docstring de depreciação)
```

Arquivos removidos:

```text
src/eii/__init__.py
src/eii/privacy/__init__.py
src/eii/privacy/scrubber.py
```

> Nota: a spec original indicava `src/eii/privacy/scrubber.py`, mas a estrutura
> real do projeto usa `src` como raiz de pacotes (`src.deep_agents`,
> `src.intel_agent`, `src.utils`). O caminho foi corrigido para
> `src/privacy/scrubber.py`. **Defeito da spec, não adaptação para passar.**

---

## 2. Saída dos testes

### Testes novos (15/15 verdes)

```text
platform win32 -- Python 3.13.7, pytest-9.0.2, pluggy-9.1.1
rootdir: C:\Projetos\eii-erp-incident-intelligence
configfile: pyproject.toml

tests\test_pii_scrubber.py ................
15 passed in 0.11s
```

### Suíte completa

```text
135 passed, 19 warnings in 26.90s
```

Os 19 warnings são `DeprecationWarning` de `datetime.datetime.utcnow()` em
`smartrouter/tests/test_adapter.py` e `smartrouter/tests/test_smartrouter.py`,
sem relação com esta feature.

---

## 3. Confirmação: nenhum teste existente foi alterado para passar

- Nenhum arquivo em `tests/` existente antes desta feature foi modificado.
- `tests/test_pii_scrubber.py` é novo.
- Os 14 testes unitários vieram da `PII-SCRUBBER-SPEC.md`; eles nunca estiveram
  no repositório, portanto não houve alteração de teste existente.
- A correção da regex de CPF/PIS (lookarounds `(?<!\d)` e `(?!\d)`) foi
  aplicada na **própria spec antes da primeira execução**, para evitar falsos
  positivos em CNPJ de 14 dígitos. A versão corrigida da spec foi a base para
  a implementação e para os testes.

---

## 4. Campos cobertos vs. seção 3 da spec

| Campo eSocial | Token | Status |
|---|---|---|
| `cpfTrab`, `cpfBenef`, `cpfResp` | `CPF_001` | ✅ coberto |
| `nmTrab`, `nmSoc` | `NOME_001` | ✅ coberto |
| `nisTrab` / PIS/PASEP | `NIS_001` | ✅ coberto |
| `dtNascto` | `DATA_NASC_001` | ✅ coberto |
| `nmMae`, `nmPai` | `NOME_001` (mesmo pool) | ✅ coberto |
| `endereco/*` (logradouro, num, cep) | `ENDERECO_001` | ✅ coberto (bloco compartilha token) |
| `matricula` | `MATR_001` | ✅ coberto |
| `nrCtps`, `nrRic`, `nrRg`, `nrCnh` | `DOC_001` | ✅ coberto |
| `nrInsc` (CNPJ empregador) | **mantido** | ✅ preservado |
| `vrRubr`, `vrBcCp` | `VALOR_FAIXA_*_*` | ✅ coberto (quasi-identificadores) |

Divergências: nenhuma.

---

## 5. Código morto encontrado

`src/utils/scrubber.py` já existia, sem importadores, e era incompatível com a
spec atual:

- Redige CNPJ do empregador (destrói contexto necessário ao diagnóstico).
- Não possui mapa de reversão (`token_map`).
- Interface (`scrub_pii`) diferente do contrato `PIIScrubber`/`ScrubResult`.

Foi marcado como **deprecado** via docstring no topo, apontando para
`src/privacy/scrubber.py`. A remoção física foi deferida para PR separado com
ADR, conforme instrução.

---

## 6. Blast radius

Se `PIIScrubber` falhar:

- **Pipeline de diagnóstico:** `is_safe_for_remote=False` força degradação para
  Qwen 14B local (fail-closed). Nenhum dado pessoal vaza para OpenRouter/GLM.
- **CRAG/retrieval:** a busca passa a usar payload já limpo; falhas no scrubber
  podem contaminar o contexto enviado ao LLM local ou, no pior caso, ao remoto
  se a camada de segurança também falhar.
- **SmartRouter:** ainda não integrado (depende dos greps do servidor). A
  fiação é a próxima etapa.
- **Testes existentes:** nenhum impacto — suíte completa continua verde.

---

## 7. Rollback path

**Enquanto o scrubber não estiver fiado no SmartRouter:**
1. Reverter o commit/branch `feature/claude-mandatory-pii-scrubber`.
2. Remover `src/privacy/` e `tests/test_pii_scrubber.py`.
3. Restaurar `src/utils/scrubber.py` ao estado anterior (sem docstring de
   depreciação), se necessário.
4. O retrieval e o SmartRouter continuam funcionando com payload cru até nova
   implementação de scrubbing ser acoplada.

**Pós-integração no SmartRouter:**
- Reverter o scrubber significa enviar PII ao OpenRouter.
- Portanto, após a fiação, o rollback correto é **desabilitar o provedor remoto
  e forçar o uso do Qwen 14B local**.
- Nunca remover o scrubber mantendo o LLM remoto ativo.

---

## 8. Métrica de performance

**Sem métrica de performance nova.** Não foi realizado benchmark de overhead do
scrubber. A latência do parsing XML com `xml.etree.ElementTree` é esperada como
irrisória frente à chamada de LLM.

---

## 9. Limitações conhecidas

### Id do evento quando `tpInsc=2` (CAEPF / pessoa física empregadora)

O atributo `Id` do evento eSocial embute o `nrInsc` do empregador. Quando
`tpInsc=2` (CAEPF — empregador doméstico, produtor rural, pessoa física), esse
`nrInsc` **é um CPF**, preenchido com zeros até 14 dígitos. Nesse caso o CPF do
empregador sai no payload dentro do `Id`, e a rede de segurança atual não
detecta porque o CPF está contido em uma sequência maior que 11 dígitos.

**Impacto:** bloqueia o uso seguro do scrubber em folha doméstica / produtor
rural com roteamento remoto.

**Backlog:** tratar o atributo `Id` quando `tpInsc=2` (pseudonimizar ou
validar separadamente).

**Não bloqueia esta entrega:** os fixtures e casos de teste atuais usam
`tpInsc=1` (CNPJ pessoa jurídica).

### Dados sensíveis do S-2200 não cobertos pela spec

A seção 3 da `PII-SCRUBBER-SPEC.md` não contempla `racaCor`, `sexo`,
`estCiv` e `grauInstr`. `racaCor` é dado pessoal **sensível** sob a LGPD
(art. 5º, II), com regime mais restrito que PII comum. Os quatro campos
combinados também funcionam como quasi-identificadores.

**Origem do achado:** constavam em `_PRESERVED_TAGS`, código morto removido
nesta entrega.

**Backlog:** revisar a seção 3 da spec contra o layout do S-2200 e definir
trata­mento (pseudonimizar, generalizar ou suprimir) para dados sensíveis.

**Impacto:** não bloqueia — o scrubber não está fiado. **Bloqueia a fiação no
SmartRouter** até a decisão ser tomada.

---

## 10. Testes de integração deferidos

Os dois testes de integração da seção 6 da spec foram **deliberadamente não
implementados** nesta etapa:

- `test_payload_que_sai_pela_rede_nao_tem_pii`
- `test_fail_closed_nao_chama_remoto`

**Motivo:** dependem da fiação no SmartRouter e do entry point do pipeline,
que serão confirmados pelos greps pendentes no servidor Contabo, conforme
seção 7 da spec.

---

## 11. Itens de decisão / autorização

| # | Item | Decisão | Quem |
|---|---|---|---|
| 1 | Caminho do módulo (`src/eii/` → `src/privacy/`) | Corrigir para refletir estrutura real do projeto | Edson autorizou em 31/08 |
| 2 | Regex de CPF/PIS com falsos positivos em CNPJ | Aplicar lookarounds `(?<!\d)` e `(?!\d)` nos testes e na rede de segurança | Edson autorizou em 31/08 |
| 3 | Remoção de `src/utils/scrubber.py` | Deferir para PR separado com ADR | Edson instruiu em 31/08 |
| 4 | Integração no SmartRouter | Deferir após greps do servidor | Edson instruiu em 31/08 |

---

## 12. Veredito

- [x] 15 testes novos passam
- [x] 135 testes da suíte completa passam (sem regressão)
- [x] Nenhum teste existente alterado para passar
- [x] Campos cobertos alinhados à seção 3 da spec
- [x] Código morto identificado e marcado como deprecado
- [x] Testes de integração deferidos documentados
- [x] Sem push realizado

**Veredito:** Pronto para revisão de Edson.

Assinado: ___________________________  Edson  —  2026-08-31
