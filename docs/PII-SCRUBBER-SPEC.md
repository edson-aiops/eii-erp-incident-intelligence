# PII-SCRUBBER-SPEC.md

**Projeto:** EII — ERP Incident Intelligence
**Branch:** `feature/claude-mandatory-pii-scrubber`
**Autor da spec:** Claude · **Executor:** Kimi Code CLI · **Release owner:** Edson (única autoridade de push/merge)
**Gate de merge:** `EVIDENCE_PACK-scrubber.md` verde
**Regra:** Kimi implementa contra os testes black-box desta spec. Kimi **não** faz push.

---

## 1. Objetivo

Tornar a remoção de dados pessoais um **passo obrigatório e não-configurável** do pipeline do EII, executado antes de qualquer chamada a LLM remoto (GLM-5.3 via OpenRouter).

### O que isto NÃO é

Isto não é anonimização no sentido do art. 12 da LGPD. O mapa de reversão existe (o diagnóstico precisa ser remontado com os dados reais). O que a solução garante é que **o operador remoto não possui meios de reidentificar o titular**, porque o mapa nunca sai do servidor.

Qualquer texto público sobre o projeto (README, LinkedIn, TCC) deve usar essa formulação — não "os dados são anonimizados".

### Requisito não-funcional central

Não existe flag para desligar o scrubbing. Se for configurável, alguém desliga.

---

## 2. Contrato público

Módulo novo: `src/eii/privacy/scrubber.py`

```python
from dataclasses import dataclass, field

@dataclass
class ScrubResult:
    """Resultado de uma operação de scrubbing."""
    scrubbed_payload: str          # o que PODE sair pela rede
    token_map: dict[str, str]      # token -> valor real. NUNCA serializar.
    fields_scrubbed: list[str]     # caminhos de campo tratados (para auditoria)
    is_safe_for_remote: bool       # False => proibido chamar LLM remoto


class PIIScrubber:
    def scrub(self, xml_content: str, event_type: str) -> ScrubResult: ...
    def restore(self, text: str, token_map: dict[str, str]) -> str: ...
```

### Invariantes

1. `scrub()` é pura em relação a disco e rede — não escreve, não loga, não persiste.
2. `token_map` vive apenas em memória, no escopo do request.
3. `is_safe_for_remote=False` ⇒ o SmartRouter **não pode** rotear para provedor remoto.
4. `restore()` só é chamada depois que a resposta do LLM voltou, dentro do mesmo request.

---

## 3. Campos cobertos

Substituição **por caminho de campo**, usando o parser unificado já existente no EII. Não usar regex varrendo texto livre como estratégia primária — erra nas duas direções (deixa passar e destrói tag legítima).

| Campo eSocial | Token | Observação |
|---|---|---|
| `cpfTrab`, `cpfBenef`, `cpfResp` | `CPF_001` | numeração sequencial por request |
| `nmTrab`, `nmSoc` | `NOME_001` | |
| `nisTrab` / PIS/PASEP | `NIS_001` | |
| `dtNascto` | `DATA_NASC_001` | |
| `nmMae`, `nmPai` | `NOME_001` (mesmo pool) | |
| `endereco/*` (logradouro, num, cep) | `ENDERECO_001` | bloco inteiro |
| `matricula` | `MATR_001` | |
| `nrCtps`, `nrRic`, `nrRg`, `nrCnh` | `DOC_001` | |
| `nrInsc` (CNPJ empregador) | **mantido** | necessário ao diagnóstico, é pessoa jurídica |

### Quasi-identificadores

Valores de remuneração (`vrRubr`, `vrBcCp`) combinados com data e CNPJ podem reidentificar sem CPF. Para diagnóstico de rejeição, o valor exato é irrelevante — o que importa é **presença, tipo e formato**.

Regra: substituir por marcador de faixa preservando o formato.
`1543.27` → `VALOR_FAIXA_1000_2000` (mantém 2 casas decimais implícitas no metadado).

Se um caso de teste provar que o código de erro depende do valor exato, abrir exceção documentada em ADR — não silenciosamente.

### Rede de segurança (secundária, não primária)

Depois da substituição por campo, rodar uma varredura regex sobre o payload final procurando padrão de CPF (`\d{3}\.?\d{3}\.?\d{3}-?\d{2}`) e PIS (`\d{3}\.?\d{5}\.?\d{2}-?\d`). Se encontrar algo, `is_safe_for_remote = False`. Esta camada existe para pegar campo novo/desconhecido, não para fazer o trabalho.

---

## 4. Fail-closed

Se o scrubber não reconhecer a estrutura do evento (tipo não mapeado, XML malformado, campo esperado ausente):

```
is_safe_for_remote = False
```

O pipeline então **degrada para o Qwen 14B local** — não aborta, não manda pro remoto. Erro deve travar a saída de dado, nunca vazar.

Registrar em log **apenas** o tipo de evento e o motivo. Nunca o conteúdo.

---

## 5. Ponto de integração

O scrubbing entra **entre** a recepção do XML e a montagem do prompt:

```
XML recebido
   ↓
PIIScrubber.scrub()          ← NOVO, obrigatório
   ↓
CRAG / retrieval (Qdrant)     ← busca usa payload já limpo
   ↓
SmartRouter
   ├─ is_safe_for_remote=True  → GLM-5.3 (OpenRouter)
   └─ is_safe_for_remote=False → Qwen 14B local (obrigatório)
   ↓
PIIScrubber.restore()         ← remonta com dados reais
   ↓
Diagnóstico devolvido
```

> **Dependência:** o nome exato do entry point do pipeline e a assinatura do SmartRouter serão confirmados pelo diagnóstico do servidor (greps pendentes). Kimi: implemente o módulo `scrubber.py` e seus testes **primeiro** — eles não dependem disso. A fiação no SmartRouter é a segunda etapa.

---

## 6. Testes black-box

Escritos a partir do contrato, sem ler a implementação. Arquivo: `tests/test_pii_scrubber.py`

```python
import re
import pytest
from eii.privacy.scrubber import PIIScrubber, ScrubResult

CPF_PATTERN = re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")
PIS_PATTERN = re.compile(r"\d{3}\.?\d{5}\.?\d{2}-?\d")


def test_cpf_nao_sobrevive_ao_scrub(s1200_com_cpf):
    r = PIIScrubber().scrub(s1200_com_cpf, "S-1200")
    assert not CPF_PATTERN.search(r.scrubbed_payload)


def test_nome_nao_sobrevive_ao_scrub(s2200_com_nome):
    r = PIIScrubber().scrub(s2200_com_nome, "S-2200")
    assert "MARIA APARECIDA DA SILVA" not in r.scrubbed_payload.upper()


def test_pis_nao_sobrevive_ao_scrub(s1200_com_nis):
    r = PIIScrubber().scrub(s1200_com_nis, "S-1200")
    assert not PIS_PATTERN.search(r.scrubbed_payload)


def test_cnpj_empregador_e_preservado(s1200_padrao):
    r = PIIScrubber().scrub(s1200_padrao, "S-1200")
    assert "12345678000199" in r.scrubbed_payload.replace(".", "").replace("/", "")


def test_codigo_de_erro_sobrevive_ao_scrub(s1200_rejeitado):
    """O scrubbing não pode destruir o que é objeto do diagnóstico."""
    r = PIIScrubber().scrub(s1200_rejeitado, "S-1200")
    assert "MS0424" in r.scrubbed_payload


def test_restore_reverte_integralmente(s1200_com_cpf):
    sc = PIIScrubber()
    r = sc.scrub(s1200_com_cpf, "S-1200")
    token = next(iter(r.token_map))
    restored = sc.restore(f"Erro no trabalhador {token}.", r.token_map)
    assert r.token_map[token] in restored


def test_token_map_nunca_aparece_no_payload(s1200_com_cpf):
    r = PIIScrubber().scrub(s1200_com_cpf, "S-1200")
    for valor_real in r.token_map.values():
        assert valor_real not in r.scrubbed_payload


def test_evento_desconhecido_e_fail_closed():
    r = PIIScrubber().scrub("<eSocial><evtDesconhecido/></eSocial>", "S-9999")
    assert r.is_safe_for_remote is False


def test_xml_malformado_e_fail_closed():
    r = PIIScrubber().scrub("<eSocial><quebrado", "S-1200")
    assert r.is_safe_for_remote is False


def test_scrub_nao_escreve_em_disco(s1200_com_cpf, tmp_path, monkeypatch):
    """Nenhum artefato criado durante o scrub."""
    monkeypatch.chdir(tmp_path)
    antes = set(tmp_path.rglob("*"))
    PIIScrubber().scrub(s1200_com_cpf, "S-1200")
    assert set(tmp_path.rglob("*")) == antes


def test_scrub_nao_loga_conteudo_sensivel(s1200_com_cpf, caplog):
    PIIScrubber().scrub(s1200_com_cpf, "S-1200")
    assert not CPF_PATTERN.search(caplog.text)


def test_dois_requests_nao_compartilham_token_map(s1200_com_cpf, s2200_com_nome):
    sc = PIIScrubber()
    r1 = sc.scrub(s1200_com_cpf, "S-1200")
    r2 = sc.scrub(s2200_com_nome, "S-2200")
    assert r1.token_map is not r2.token_map


def test_valor_monetario_e_generalizado(s1200_com_rubrica):
    r = PIIScrubber().scrub(s1200_com_rubrica, "S-1200")
    assert "1543.27" not in r.scrubbed_payload
    assert "VALOR_FAIXA" in r.scrubbed_payload


def test_scrub_e_deterministico(s1200_com_cpf):
    """Mesmo input, mesmo payload — necessário para cache e reprodutibilidade."""
    sc = PIIScrubber()
    a = sc.scrub(s1200_com_cpf, "S-1200")
    b = sc.scrub(s1200_com_cpf, "S-1200")
    assert a.scrubbed_payload == b.scrubbed_payload
```

### Teste de integração — o gate de verdade

```python
def test_payload_que_sai_pela_rede_nao_tem_pii(s1200_com_cpf, capture_outbound):
    """
    Intercepta o payload no ponto exato da chamada HTTP ao OpenRouter
    e falha se houver padrão de PII. Este é o teste que impede regressão.
    """
    run_diagnosis(s1200_com_cpf)
    for req in capture_outbound.requests:
        assert not CPF_PATTERN.search(req.body)
        assert not PIS_PATTERN.search(req.body)


def test_fail_closed_nao_chama_remoto(capture_outbound):
    run_diagnosis("<eSocial><evtDesconhecido/></eSocial>")
    assert capture_outbound.remote_calls == 0
```

### Fixtures

Kimi deve criar `tests/fixtures/pii/` com XMLs **sintéticos** — CPFs de teste inválidos por dígito verificador, nomes fictícios. Nunca dado real de cliente.

---

## 7. Ordem de execução (Kimi)

1. Criar `src/eii/privacy/scrubber.py` com o contrato da seção 2
2. Criar fixtures sintéticas
3. Implementar até os 14 testes unitários passarem
4. **Parar.** Reportar a Edson antes de tocar no SmartRouter — a fiação depende dos greps do servidor
5. Rodar suíte completa (120+ testes existentes) e confirmar zero regressão
6. Preencher `EVIDENCE_PACK-scrubber.md`
7. **Não fazer push.** Edson revisa e mergeia.

Requisito ambíguo ⇒ escalar para Edson, não adivinhar.

---

## 8. EVIDENCE_PACK — campos obrigatórios

- [ ] Diff completo
- [ ] Saída do pytest: 14 testes novos + suíte existente verde
- [ ] Confirmação explícita de que nenhum teste existente foi alterado para passar
- [ ] Lista dos campos cobertos vs. lista da seção 3 (justificar cada divergência)
- [ ] **Blast radius:** que parte do pipeline quebra se o scrubber falhar
- [ ] **Rollback path:** como reverter sem perder o retrieval
- [ ] Declaração: "sem métrica de performance nova" ou benchmark real de overhead do scrub
- [ ] Veredito assinado — Edson

---

## 9. Pendências (não bloqueiam a etapa 1)

- Entry point do pipeline — depende dos greps no Contabo
- Assinatura do SmartRouter para receber `is_safe_for_remote`
- Decisão sobre overhead aceitável do scrub na latência total
- ADR documentando a escolha "pseudonimização + mapa local" vs anonimização plena
