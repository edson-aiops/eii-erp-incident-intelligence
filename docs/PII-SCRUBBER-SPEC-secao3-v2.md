## 3. Campos cobertos

> **Revisão v2 (A23) — 2026-08-31.** Substitui integralmente a seção 3 anterior.
> Motivo: a versão v1 usava denylist por caminho e não cobria dados sensíveis do
> S-2200 (art. 5º, II da LGPD), nem o CPF embutido no atributo `Id` quando
> `tpInsc != 1`. Ver seção 3.9 para o registro das mudanças.

Substituição **por caminho de campo**, usando o parser unificado já existente no
EII. Não usar regex varrendo texto livre como estratégia primária — erra nas duas
direções (deixa passar e destrói tag legítima). Regex é rede de segurança
(seção 3.7), não estratégia.

---

### 3.1 Princípio: allowlist dentro dos blocos de titular

Denylist por caminho não fecha. O layout eSocial tem centenas de tags e muda a
cada versão (S-1.1 → S-1.2 → S-1.3). Cada campo novo dentro de `trabalhador`
seria um vazamento silencioso — foi exatamente o que aconteceu com `racaCor`,
`infoDeficiencia` e `filiacaoSindical` na v1 desta spec.

**Regra:** dentro dos *blocos de titular*, **todo nó folha é tratado por
padrão**. Preservar exige entrada explícita na allowlist da seção 3.5. Fora dos
blocos de titular, vale a denylist por caminho da seção 3.3.

Blocos de titular (por *local-name*, ignorando namespace e profundidade):

```
trabalhador        dependente         endereco (brasil | exterior)
documentos         contato            infoDeficiencia
aposentadoria      trabEstrangeiro    filiacaoSindical
```

Custo aceito: a allowlist erra destruindo contexto de diagnóstico. É erro
recuperável — aparece como diagnóstico ruim e se corrige adicionando o campo à
allowlist. O erro na direção oposta não é recuperável.

Nó folha dentro de bloco de titular sem tratamento definido ⇒ **TOKENIZAR**
com o token genérico `CAMPO_TITULAR_NNN`. Não é fail-closed: é o default seguro
que permite o evento seguir para o remoto. Fail-closed continua reservado aos
casos da seção 4.

---

### 3.2 Classes de tratamento

| Classe | Quando aplicar | Efeito no payload | Reversível |
|---|---|---|---|
| **PRESERVAR** | valor é de pessoa jurídica ou puramente estrutural | inalterado | n/a |
| **TOKENIZAR** | identificador direto ou texto livre | `CPF_001`, `NOME_001` | sim |
| **CLASSIFICAR** | domínio fechado **e** valor sensível ou quasi-identificador | `RACA_COR_VALIDO_001` \| `RACA_COR_FORA_DOMINIO_001` | sim |
| **GENERALIZAR** | valor contínuo (monetário, CEP) | `VALOR_FAIXA_1000_2000` | não |

#### Nota sobre CLASSIFICAR

CLASSIFICAR existe porque os campos de domínio fechado do S-2200 são
**objeto frequente de rejeição** ("racaCor inválido", "grauInstr fora do
domínio"). Tokenizar destruiria o objeto do diagnóstico; preservar vazaria dado
sensível.

O token expõe **1 bit**: o valor pertence ou não ao domínio da versão de layout
configurada. Isso é o que o diagnóstico precisa e é insuficiente para
reidentificar o titular.

Regras de formação do token classificado:

- Prefixo = *local-name* da tag em `SNAKE_UPPER`: `racaCor` → `RACA_COR`,
  `defFisica` → `DEF_FISICA`, `estCiv` → `EST_CIV`, `grauInstr` → `GRAU_INSTR`.
- Sufixo `_VALIDO_NNN` quando o código está no domínio;
  `_FORA_DOMINIO_NNN` quando não está.
- `NNN` é sequencial por request, em ordem de documento (seção 3.6).

`_FORA_DOMINIO` significa **"não pertence ao domínio da versão de layout
carregada"** — não "o valor é inválido". O scrubber não emite juízo de validade;
quem faz isso é o diagnóstico. As tabelas de domínio ficam versionadas no módulo
sob a constante `LAYOUT_VERSION` (inicialmente `"S-1.3"`), e código desconhecido
cai em `_FORA_DOMINIO` — nunca em `_VALIDO`.

---

### 3.3 Tabela de campos

#### 3.3.1 Identificadores diretos — TOKENIZAR

| Campo eSocial | Token | Observação |
|---|---|---|
| `cpfTrab`, `cpfBenef`, `cpfResp`, `cpfDep` | `CPF_NNN` | pool único; mesmo valor real ⇒ mesmo token |
| `nmTrab`, `nmSoc`, `nmDep` | `NOME_NNN` | pool único |
| `nmMae`, `nmPai` | `NOME_NNN` | mesmo pool |
| `nisTrab` / PIS/PASEP | `NIS_NNN` | |
| `dtNascto` (titular e dependente) | `DATA_NASC_NNN` | data pessoal; datas contratuais preservadas (3.5) |
| `matricula` | `MATR_NNN` | |
| `nrCtps` + `serieCtps` | `DOC_NNN` | número e série juntos identificam |
| `nrRic`, `nrRg`, `nrRne`, `nrOc`, `nrRegCnh` | `DOC_NNN` | pool único de documentos |
| `nrProcJud`, `nrProcTrab` | `PROC_NNN` | processo identifica as partes |
| `cnpjSindTrab` (`filiacaoSindical`) | `CNPJ_SIND_NNN` | **filiação sindical — art. 5º, II** |
| `fonePrinc`, `foneAlternat` | `FONE_NNN` | |
| `emailPrinc`, `emailAlternat` | `EMAIL_NNN` | |
| `dscLograd`, `nrLograd`, `complemento`, `bairro` | `ENDERECO_NNN` | bloco compartilha o token |
| `observacao`, `observacoes/observacao`, `dscSalVar` | `TEXTO_LIVRE_NNN` | texto livre: pode conter qualquer coisa |
| nó folha não previsto dentro de bloco de titular | `CAMPO_TITULAR_NNN` | default da allowlist (3.1) |

#### 3.3.2 Domínio fechado sensível ou quasi-identificador — CLASSIFICAR

| Campo eSocial | Domínio (S-1.3) | Justificativa |
|---|---|---|
| `racaCor` | `1..6` | **dado sensível, art. 5º, II** (origem racial/étnica) |
| `sexo` | `M`, `F` | quasi-identificador |
| `estCiv` | `1..5` | quasi-identificador |
| `grauInstr` | `01..12` | quasi-identificador |
| `defFisica`, `defVisual`, `defAuditiva`, `defMental`, `defIntelectual`, `reabReadap`, `infoCota` | `S`, `N` | **dado de saúde, art. 5º, II** |
| `incTrab` (dependente) | `S`, `N` | **saúde de terceiro** |
| `trabAposent` | `S`, `N` | quasi-identificador |
| `tpDep` | `01..99` | revela vínculo familiar |
| `classTrabEstrang`, `casadoBr`, `filhosBr` | domínio do layout | quasi-identificadores |
| `depIRRF`, `depSF` | `S`, `N` | quasi-identificadores |

Os quatro primeiros combinados (`racaCor` + `sexo` + `estCiv` + `grauInstr`),
somados a município e faixa salarial, formam quasi-identificador forte mesmo sem
CPF. É por isso que `sexo`, `estCiv` e `grauInstr` entram aqui apesar de não
serem sensíveis no sentido do art. 5º, II.

**Exceção de país — 1 bit adicional.** `paisNascto`, `paisNac`, `paisResid` e
`paisResidExt` recebem `PAIS_BRASIL_NNN` quando o código é `105`,
`PAIS_ESTRANGEIRO_NNN` para qualquer outro código do domínio, e
`PAIS_FORA_DOMINIO_NNN` fora dele. Sem esse bit, a regra "se `paisNascto` ≠ 105
o grupo `trabEstrangeiro` é obrigatório" fica indiagnosticável.

#### 3.3.3 Valores contínuos — GENERALIZAR

| Campo eSocial | Token | Observação |
|---|---|---|
| `vrRubr`, `vrBcCp`, `vrSalFx`, `vrDedDep`, `vrCpSeg` | `VALOR_FAIXA_<piso>_<teto>` | ver 3.4 |
| `cep` | `CEP_VALIDO_NNN` \| `CEP_FORA_FORMATO_NNN` | classificação por formato (8 dígitos), não por valor |

#### 3.3.4 Preservados

| Campo eSocial | Condição |
|---|---|
| `nrInsc` do empregador | **somente quando `tpInsc=1`** (CNPJ) — ver 3.4 |
| `codMunic`, `uf`, `tpLograd` | quasi-identificadores fracos e objeto frequente de erro |
| `cnpjSindCategProf` | sindicato **da categoria**, definido pelo CBO — não revela escolha do titular |
| `dtAdm`, `dtDeslig`, `dtOpcFGTS`, demais datas contratuais | objeto direto do diagnóstico |
| `codCateg`, `CBOCargo`, `CBOFunc`, `tpRegTrab`, `tpRegPrev`, `tpAdmissao`, `indAdmissao` | domínio fechado, não identificam |
| códigos de erro, `cdResposta`, `ocorrencias/codigo` | objeto do diagnóstico |

---

### 3.4 `Id` e `nrInsc` do empregador — regra condicional a `tpInsc`

A regra v1 ("`nrInsc` do empregador é mantido, é pessoa jurídica") é falsa
quando `tpInsc != 1`.

Domínio de `tpInsc`: `1=CNPJ`, `2=CPF`, `3=CAEPF`, `4=CNO`. Em `ideEmpregador`
só valem 1 e 2; 3 e 4 aparecem em lotação, local de trabalho e obra.

- `tpInsc=2` ⇒ `nrInsc` **é um CPF** (empregador doméstico, produtor rural,
  pessoa física).
- `tpInsc=3` ⇒ `nrInsc` é CAEPF = **CPF (11 dígitos) + 3 dígitos de
  estabelecimento**.
- `tpInsc=4` ⇒ CNO, vinculado a obra. Preservado, com ressalva registrada em
  3.8.

#### Estrutura do atributo `Id` (36 posições)

```
ID | tpInsc | nrInsc              | AAAAMMDDHHMMSS | sequencial
2  | 1      | 14                  | 14             | 5
```

`nrInsc` ocupa 14 posições, completado com zeros à direita quando o valor real
tem menos dígitos. Com `tpInsc=2`, as posições 4..14 são o CPF do empregador e
15..17 são zeros de preenchimento.

#### Regra única

**Substituir apenas os 11 primeiros dígitos do `nrInsc` (o CPF) pelo token
`CPF_EMPR_NN`, que tem exatamente 11 caracteres, mantendo o restante do campo
intacto.**

| Contexto | Valor real | Após scrub | Largura |
|---|---|---|---|
| `ideEmpregador/nrInsc`, `tpInsc=2` | `22222222222` | `CPF_EMPR_01` | 11 → 11 |
| `nrInsc` CAEPF, `tpInsc=3` | `33333333333001` | `CPF_EMPR_01001` | 14 → 14 |
| segmento do `Id`, `tpInsc=2` | `22222222222000` | `CPF_EMPR_01000` | 14 → 14 |
| `Id` completo, `tpInsc=2` | `ID22222222222200020260801120000 00001` | `ID2CPF_EMPR_0100020260801120000000001` | 36 → 36 |

Consequências desejadas:

1. **Largura preservada** — erro de formato de `Id` continua diagnosticável.
2. **Coerência referencial** — o mesmo CPF real recebe o mesmo token em
   `Id` e em `ideEmpregador/nrInsc`; as regras de validação cruzada sobrevivem.
3. **Reversível** — `token_map["CPF_EMPR_01"] = "22222222222"`; `restore()` por
   substituição de string reverte as três ocorrências.
4. `CPF_EMPR_NN` usa sequencial de 2 dígitos (máximo 99 empregadores distintos
   por request). Estourar o limite ⇒ fail-closed.

#### Fail-closed do `Id`

Se o atributo `Id` não parsear exatamente — prefixo diferente de `ID`, largura
diferente de 36, `tpInsc` fora de `1..4`, ou segmentos que deveriam ser
numéricos e não são — então `is_safe_for_remote = False`. Não tentar adivinhar
a estrutura.

---

### 3.5 Allowlist dentro de blocos de titular

Preservados apesar de estarem dentro de bloco de titular:

```
codMunic   uf   tpLograd   undSalFixo   orgaoEmissor   ufCtps   ufCnh
categoriaCnh   dtExped   dtValid   dtPriHab
```

Critério: código de domínio fechado que não identifica o titular e cuja
ausência quebra diagnóstico de erro de preenchimento. Toda entrada nova nesta
lista exige justificativa no diff — não é lista de conveniência.

---

### 3.6 Numeração e determinismo

- Sequencial por request, atribuído em **ordem de documento** (a mesma que
  `ElementTree.iter()` produz).
- Mesmo valor real ⇒ mesmo token, dentro do request. Isso preserva coerência
  referencial (por exemplo, `cpfTrab` que reaparece em `mudancaCPF`).
- Pools independentes por prefixo: `CPF_001` e `NOME_001` coexistem.
- Nenhum estado atravessa requests. O `token_map` nasce e morre no escopo do
  `scrub()`.

---

### 3.7 Rede de segurança v2 (secundária, não primária)

A rede v1 não detectava CPF contido em sequência maior que 11 dígitos — achado
do A2. Três camadas, nesta ordem, depois da substituição por campo:

**Camada 1 — passe de substituição em texto livre de retorno.**
Percorrer `descResposta`, `ocorrencias/descricao` e demais nós de texto livre do
retorno, substituindo qualquer valor presente no `token_map` pelo respectivo
token, nas formas crua e formatada (`12345678909`, `123.456.789-09`).
Justificativa: o webservice ecoa o valor rejeitado. Se o CPF entrou no evento e o
erro é sobre ele, ele volta na descrição — vazamento fora de qualquer bloco de
titular.

**Camada 2 — regex CPF/PIS.**
Sobre o payload final inteiro, com os lookarounds já corrigidos no A2:

```
CPF: (?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)
PIS: (?<!\d)\d{3}\.?\d{5}\.?\d{2}-?\d(?!\d)
```

Match ⇒ `is_safe_for_remote = False`.

**Camada 3 — run de dígitos.**
Para cada nó de texto e cada valor de atributo **fora da lista de isenção**,
normalizar removendo `.`, `-`, `/` e espaço. Run de dígitos com comprimento
≥ 11 ⇒ `is_safe_for_remote = False`.

Critério de isenção: **nó cujo tratamento é PRESERVAR e cujo valor é, por
definição de layout, inscrição de pessoa jurídica ou identificador de
protocolo.** Lista nominal:

```
Id                        (validação estrutural própria, seção 3.4)
nrInsc                    (apenas quando o tpInsc do mesmo grupo é 1)
cnpjSindCategProf   cnpjEmpregador   cnpjTransf   cnpjSucessora
nrRecibo   nrRec   nrRecArqBase   nrRecInfPrelim   nrProtocolo   hash
```

A isenção existe porque um `Id` legítimo com `tpInsc=1` é um run de 33 dígitos
contíguos e um CNPJ é um run de 14 — sem a lista, a camada 3 derrubaria todo
evento válido. Qualquer entrada nova exige justificativa no diff: cada isenção
é um ponto cego deliberado.

Estas três camadas existem para pegar **campo novo ou desconhecido**. Não são o
mecanismo de proteção.

---

### 3.8 Limitações conhecidas e exceções documentadas

1. **`tpInsc=4` (CNO).** Preservado. O CNO identifica obra, não pessoa, mas pode
   estar vinculado a um titular pessoa física em obra de construção civil de PF.
   Não tratado nesta revisão; registrar em backlog.

2. **CLASSIFICAR expõe 1 bit por campo.** Um adversário com o payload sabe se
   `racaCor` está dentro do domínio, não qual é. Aceito explicitamente.

3. **Tabelas de domínio versionadas.** Mudança de layout do eSocial que
   introduza códigos novos fará campos válidos caírem em `_FORA_DOMINIO` até a
   tabela ser atualizada. Degradação de qualidade de diagnóstico, não de
   privacidade.

4. **Se um caso de teste provar que o código de erro depende do valor exato de
   um campo CLASSIFICADO**, abrir exceção documentada em ADR — não
   silenciosamente. Vale a mesma regra que já valia para valores monetários.

---

### 3.9 Registro de mudanças da v1 para a v2

| # | Mudança | Motivo |
|---|---|---|
| 1 | Allowlist dentro de blocos de titular substitui a denylist pura | denylist não fecha contra evolução de layout |
| 2 | Classe CLASSIFICAR introduzida | permite tratar domínio fechado sem destruir a diagnosticabilidade |
| 3 | `racaCor`, `sexo`, `estCiv`, `grauInstr` cobertos | `racaCor` é sensível (art. 5º, II); os quatro são quasi-id combinados |
| 4 | `infoDeficiencia/*` coberto | **dado de saúde**, art. 5º, II — ausente da v1 |
| 5 | `cnpjSindTrab` coberto | **filiação sindical**, art. 5º, II — ausente da v1 |
| 6 | `dependente/*` coberto | PII de terceiro, incluindo `incTrab` (saúde) |
| 7 | `contato/*` coberto | ausente da v1 |
| 8 | `vrSalFx` coberto | mesmo quasi-identificador de `vrRubr`, escapou da v1 |
| 9 | Texto livre (`observacao`, `dscSalVar`, `nrProcJud`) coberto | ausente da v1 |
| 10 | `nrInsc` preservado **apenas** com `tpInsc=1` | v1 assumia PJ sempre; falso para 2 e 3 |
| 11 | `Id` tratado com preservação de largura | CPF do empregador saía no payload (limitação registrada no A2) |
| 12 | Rede de segurança ganha passe em texto livre e varredura por run de dígitos | v1 não pegava CPF dentro de sequência maior |
