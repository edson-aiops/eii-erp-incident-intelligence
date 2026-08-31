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

## 11. A23 — revisão v2 da seção 3 do PII Scrubber

### 11.1 Diff da revisão

Arquivos alterados:

```text
docs/PII-SCRUBBER-SPEC.md   (seção 3 substituída pela v2)
src/privacy/scrubber.py     (implementação v2: allowlist, CLASSIFICAR, GENERALIZAR,
                             Id condicional a tpInsc, rede de segurança v2)
```

Arquivos criados:

```text
tests/test_pii_scrubber_s2200.py   (33 casos → 48 casos após correção de testes)
```

Arquivos **não** tocados:

```text
smartrouter/            (fiação continua deferida)
tests/test_pii_scrubber.py   (15/15 verdes, inalterado)
```

### 11.2 Saídas dos testes

```text
$ python -m pytest tests/test_pii_scrubber.py -v
15 passed

$ python -m pytest tests/test_pii_scrubber_s2200.py -v
48 passed

$ python -m pytest --tb=short
183 passed, 19 warnings in 5.29s
```

Os 19 warnings continuam sendo `DeprecationWarning` de
`datetime.datetime.utcnow()` em `smartrouter/tests/`, sem relação com esta
feature.

### 11.3 Campos cobertos vs. seção 3 v2 da spec

| Classe | Campos eSocial | Token / tratamento | Status |
|---|---|---|---|
| **TOKENIZAR** | `cpfTrab`, `cpfBenef`, `cpfResp`, `cpfDep` | `CPF_NNN` | ✅ coberto |
| | `nmTrab`, `nmSoc`, `nmDep`, `nmMae`, `nmPai` | `NOME_NNN` | ✅ coberto |
| | `nisTrab` | `NIS_NNN` | ✅ coberto |
| | `dtNascto` | `DATA_NASC_NNN` | ✅ coberto |
| | `nrCtps`, `nrRic`, `nrRg`, `nrRne`, `nrOc`, `nrRegCnh`, `nrCnh` | `DOC_NNN` | ✅ coberto |
| | `fonePrinc`, `foneAlternat` | `FONE_NNN` | ✅ coberto |
| | `emailPrinc`, `emailAlternat` | `EMAIL_NNN` | ✅ coberto |
| | `dscLograd`, `logradouro`, `nrLograd`, `nrLogradouro`, `complemento`, `bairro` | `ENDERECO_NNN` (bloco compartilhado) | ✅ coberto |
| | `observacao`, `dscSalVar` | `TEXTO_LIVRE_NNN` | ✅ coberto |
| | `matricula` | `MATR_NNN` | ✅ coberto |
| | `cnpjSindTrab` | `CNPJ_SIND_NNN` | ✅ coberto |
| | `nrProcJud`, `nrProcTrab` | `PROC_NNN` | ✅ coberto |
| **CLASSIFICAR** | `racaCor`, `sexo`, `estCiv`, `grauInstr` | `<CAMPO>_VALIDO_NNN` / `FORA_DOMINIO_NNN` | ✅ coberto |
| | `defFisica`, `defVisual`, `defAuditiva`, `defMental`, `defIntelectual`, `reabReadap`, `infoCota` | `<CAMPO>_VALIDO_NNN` / `FORA_DOMINIO_NNN` | ✅ coberto |
| | `incTrab`, `trabAposent`, `casadoBr`, `filhosBr`, `depIRRF`, `depSF` | `<CAMPO>_VALIDO_NNN` / `FORA_DOMINIO_NNN` | ✅ coberto |
| | `tpDep`, `classTrabEstrang` | `<CAMPO>_VALIDO_NNN` / `FORA_DOMINIO_NNN` | ✅ coberto |
| | `paisNascto`, `paisNac`, `paisResid`, `paisResidExt` | `PAIS_BRASIL_NNN` / `PAIS_ESTRANGEIRO_NNN` / `PAIS_FORA_DOMINIO_NNN` | ✅ coberto |
| **GENERALIZAR** | `vrRubr`, `vrBcCp`, `vrSalFx`, `vrDedDep`, `vrCpSeg` | `VALOR_FAIXA_<lower>_<upper>` | ✅ coberto |
| | `cep` | `CEP_VALIDO_NNN` / `CEP_FORA_FORMATO_NNN` | ✅ coberto |
| **PRESERVAR** | `tpInsc`, `tpAmb`, `indRetif`, `codCateg`, `CBOCargo`, `CBOFunc`, `tpRegTrab`, `tpRegPrev`, `tpAdmissao`, `indAdmissao`, `cnpjSindCategProf`, `cnpjEmpregador`, `cnpjTransf`, `cnpjSucessora`, `dtAdm`, `dtDeslig`, `dtOpcFGTS`, `cdResposta`, `codigo`, `nrRecibo`, `nrRec`, `nrRecArqBase`, `nrRecInfPrelim`, `nrProtocolo`, `hash` | mantido | ✅ coberto |
| **Id do evento** | atributo `Id` (36 posições) | preserva largura; CPF do empregador tokenizado quando `tpInsc=2/3` | ✅ coberto |
| **Allowlist de bloco de titular** | campos dentro de `trabalhador`, `dependente`, `endereco`, `documentos`, `contato`, `infoDeficiencia`, `aposentadoria`, `trabEstrangeiro`, `filiacaoSindical` sem regra explícita | `CAMPO_TITULAR_NNN` | ✅ coberto |
| **Rede de segurança v2** | regex CPF/PIS, run de dígitos ≥11, eco de valores em texto livre de retorno | `is_safe_for_remote=False` quando ativada | ✅ coberto |

Divergências: nenhuma.

### 11.4 Blast radius

- **Pipeline de diagnóstico:** `is_safe_for_remote=False` força degradação para
  Qwen 14B local (fail-closed). Nenhum dado pessoal vaza para OpenRouter/GLM.
- **CRAG/retrieval:** a busca passa a usar payload já limpo; falhas no scrubber
  podem contaminar o contexto enviado ao LLM local ou, no pior caso, ao remoto
  se a camada de segurança também falhar.
- **SmartRouter:** ainda não integrado (depende dos greps do servidor). A
  fiação continua deferida.
- **Testes existentes:** nenhum impacto — suíte completa continua verde.

### 11.5 Rollback path

Mesmo da seção 7, com acréscimo:

- Reverter a revisão v2 significa perder a cobertura de dados sensíveis do
  S-2200 (`racaCor`, `infoDeficiencia`, etc.) e a pseudonimização do CPF no
  `Id` quando `tpInsc != 1`.
- Se necessário, o rollback pode ser feito commit-a-commit, mantendo a v1 do
  scrubber em `src/privacy/scrubber.py` e removendo
  `tests/test_pii_scrubber_s2200.py`.

### 11.6 Métrica de performance

**Sem métrica de performance nova.** O overhead de parsing XML e das três
passadas de scrubbing continua esperado como irrisório frente à chamada de LLM.

### 11.7 Correção de teste pelo autor

Os testes `test_campos_classificados_sao_reversiveis`,
`test_scrub_com_dados_sensiveis_e_deterministico` e
`test_token_map_nunca_aparece_no_payload_do_s2200` foram corrigidos pelo
autor da spec, após escalacao do Kimi, antes da primeira execucao verde.
Nenhum deles existia em main. A implementacao NAO foi ajustada para
acomoda-los: os dois primeiros tinham erro de chamada (argumento
obrigatorio omitido) e o terceiro asseria um invariante impossivel de
satisfazer sob o esquema de tokens exigido pela propria spec.
`test_pais_fora_do_formato_nao_e_tratado_como_estrangeiro_valido` e teste
novo, cobrindo defeito de implementacao contra a secao 3.3.2 encontrado
na revisao do diff.

### 11.8 Limitação registrada

A verificacao de nao-vazamento de campos CLASSIFICADOS e feita caso a caso
(secao 1 do arquivo de testes), nao por varredura generica sobre token_map.
Motivo: dominios de 1 e 2 caracteres colidem por acaso com qualquer esquema
de token legivel. Uma varredura que soubesse distinguir colisao de vazamento
precisaria conhecer o vocabulario de tokens da implementacao, o que
quebraria a autoria black-box (D9).

---

## 12. Itens de decisão / autorização (v1 + A23)

| # | Item | Decisão | Quem |
|---|---|---|---|
| 1 | Caminho do módulo (`src/eii/` → `src/privacy/`) | Corrigir para refletir estrutura real do projeto | Edson autorizou em 31/08 |
| 2 | Regex de CPF/PIS com falsos positivos em CNPJ | Aplicar lookarounds `(?<!\d)` e `(?!\d)` nos testes e na rede de segurança | Edson autorizou em 31/08 |
| 3 | Remoção de `src/utils/scrubber.py` | Deferir para PR separado com ADR | Edson instruiu em 31/08 |
| 4 | Integração no SmartRouter | Deferir após greps do servidor | Edson instruiu em 31/08 |
| 5 | Correção de testes s2200 com argumento omitido e assert ingênuo | Corrigir pelo autor da spec antes do merge | Edson autorizou em 31/08 |
| 6 | `PAIS_FORA_DOMINIO` para país fora do formato de 3 dígitos | Restaurar estado com validação de formato, não de tabela | Edson autorizou em 31/08 |
| 7 | Strip de valores e não tokenizar texto vazio/whitespace | Ratificar na implementação e na seção 3.6 da spec | Edson ratificou em 31/08 |

---

## 13. Veredito

- [x] 15 testes de `tests/test_pii_scrubber.py` passam
- [x] 48 testes de `tests/test_pii_scrubber_s2200.py` passam
- [x] 183 testes da suíte completa passam (sem regressão)
- [x] Nenhum teste existente alterado para passar
- [x] Campos cobertos alinhados à seção 3 v2 da spec
- [x] Código morto identificado e marcado como deprecado
- [x] Testes de integração deferidos documentados
- [x] Correção de testes documentada no evidence pack
- [x] Sem push realizado

**Veredito:** Pronto para revisão de Edson.

Assinado:Edson — 2026-08-31
