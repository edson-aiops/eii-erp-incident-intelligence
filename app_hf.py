"""
EII — ERP Incident Intelligence (PUBLIC DEMO v3.0)
Versão para HuggingFace Spaces: busca por palavra-chave + LLM (Groq) + KB lookup + PII Scrubbing
"""
import os
import re
import sys
import warnings
from datetime import datetime
from pathlib import Path

import gradio as gr
import requests

warnings.filterwarnings("ignore", message=".*logfire-plugin.*")

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ─────────────────────────────────────────────────────────────────────────────
# Knowledge Base
# ─────────────────────────────────────────────────────────────────────────────
_KB: list[dict] = []
try:
    from knowledge_base import KB as KNOWLEDGE_BASE
    _KB = KNOWLEDGE_BASE
    print(f"[EII] Knowledge Base: {len(_KB)} incidentes")
except Exception as _e:
    print(f"[EII] KB indisponivel: {_e}")

_KB_TOTAL   = len(_KB)
_KB_ESOCIAL = sum(1 for i in _KB if not i.get("evento", "").startswith("R-"))
_KB_REINF   = _KB_TOTAL - _KB_ESOCIAL


def _kb_lookup(xml: str, top_n: int = 2) -> list[dict]:
    if not _KB:
        return []
    tokens = set(re.findall(r"[A-Z0-9]{3,}", xml.upper()))
    scored = []
    for inc in _KB:
        inc_tokens = set()
        for field in ("evento", "codigo_erro", "titulo", "descricao"):
            inc_tokens.update(re.findall(r"[A-Z0-9]{3,}", str(inc.get(field, "")).upper()))
        score = len(tokens & inc_tokens)
        if score > 0:
            scored.append((score, inc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [inc for _, inc in scored[:top_n]]


def _kb_context(xml: str) -> str:
    hits = _kb_lookup(xml)
    if not hits:
        return ""
    lines = ["Incidentes similares na base de conhecimento:"]
    for h in hits:
        lines.append(
            f"- [{h['id']}] {h.get('evento','')} / {h.get('codigo_erro','')}: "
            f"{h.get('titulo','')}\n"
            f"  Causa: {h.get('causa_raiz','')[:250]}"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# PII Scrubbing
# ─────────────────────────────────────────────────────────────────────────────

def _scrub_pii(text: str) -> tuple[str, int]:
    total = [0]

    def _mask(m, label):
        total[0] += 1
        return f"[{label}/SCRUBBED]"

    text = re.sub(r'\b\d{3}[\.\s]?\d{3}[\.\s]?\d{3}[-\.\s]?\d{2}\b',
                  lambda m: _mask(m, "CPF"), text)
    text = re.sub(r'\b\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\/\.\s]?\d{4}[-\.\s]?\d{2}\b',
                  lambda m: _mask(m, "CNPJ"), text)
    text = re.sub(r'\b\d{11}\b',
                  lambda m: _mask(m, "NIS"), text)
    return text, total[0]


# ─────────────────────────────────────────────────────────────────────────────
# Groq — geração de diagnóstico (busca por palavra-chave na KB + LLM)
# ─────────────────────────────────────────────────────────────────────────────

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.3-70b-versatile"


def _call_groq(xml_clean: str, inc_id: str, mentor_mode: bool) -> tuple[str, str]:
    if not GROQ_API_KEY:
        return (
            "### Configuracao pendente\n"
            "`GROQ_API_KEY` nao configurada nos Secrets do Space.\n\n"
            "Para rodar localmente: `python app.py`",
            "sem API key"
        )

    kb_ctx = _kb_context(xml_clean)
    kb_refs = len(_kb_lookup(xml_clean))

    system = (
        "Voce e o EII (ERP Incident Intelligence), especialista em eSocial, "
        "EFD-Reinf e legislacao trabalhista/tributaria brasileira. "
        "Diagnostique incidentes de integracao fiscal com precisao tecnica. "
        "Responda SEMPRE em portugues brasileiro. Use Markdown com as secoes solicitadas."
    )

    mentor_section = (
        "\n### Nota para Analista Junior\n"
        "[Explicacao didatica: o que e esse evento, por que foi rejeitado, como evitar no futuro]"
        if mentor_mode else ""
    )

    user = f"""Analise o XML de retorno eSocial/EFD-Reinf abaixo e gere um diagnostico tecnico completo.

{f"CONTEXTO DA BASE DE CONHECIMENTO:{chr(10)}{kb_ctx}{chr(10)}" if kb_ctx else ""}
XML do incidente ({inc_id}):
```xml
{xml_clean[:4000]}
```

Retorne EXATAMENTE neste formato Markdown:

### Diagnostico: {inc_id}
**Evento:** [evento eSocial ou EFD-Reinf]
**Codigo de Erro:** [codigo]
**Severidade:** [critico / alto / medio / baixo]
**Confianca:** [alta / media / baixa]

### Causa Raiz
[Explicacao tecnica detalhada do motivo da rejeicao]

### Passos de Resolucao
1. [passo 1]
2. [passo 2]
3. [mais passos conforme necessario]

### Validacao
[Como confirmar que o problema foi resolvido]{mentor_section}
"""

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                "temperature": 0.1,
                "max_tokens": 2000,
            },
            timeout=45,
        )
        if resp.status_code == 200:
            text = resp.json()["choices"][0]["message"]["content"]
            kb_tag = f" | KB: {kb_refs} ref(s)" if _KB else ""
            return text, f"Groq {GROQ_MODEL}{kb_tag}"
        return (
            f"### Erro Groq ({resp.status_code})\n```\n{resp.text[:300]}\n```",
            "erro HTTP"
        )
    except Exception as exc:
        return f"### Erro de conexao\n`{exc}`", "timeout"


# ─────────────────────────────────────────────────────────────────────────────
# Handler principal
# ─────────────────────────────────────────────────────────────────────────────

def diagnose_public(xml_raw: str, mentor_mode: bool) -> str:
    if not xml_raw or not xml_raw.strip():
        return "Cole um XML eSocial ou EFD-Reinf no campo acima e clique em **Diagnosticar**."
    if not xml_raw.strip().startswith("<"):
        return "### XML invalido\nO texto nao parece ser um XML valido. Cole o retorno completo da plataforma eSocial/EFD-Reinf."

    inc_id = f"INC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    xml_clean, pii_count = _scrub_pii(xml_raw)
    scrub_info = f"PII removido: {pii_count} ocorrencia(s)" if pii_count else "Nenhum dado pessoal detectado"

    diag, engine = _call_groq(xml_clean, inc_id, mentor_mode)
    return f"{diag}\n\n---\n`{inc_id}` | {scrub_info} | {engine}"


# ─────────────────────────────────────────────────────────────────────────────
# XMLs de exemplo
# ─────────────────────────────────────────────────────────────────────────────

EXAMPLES = {
    "S-1000 / E001 — CNPJ nao cadastrado": """\
<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtInfoEmpregador/v02_05_00">
  <evtInfoEmpregador Id="ID1000999912340001202505090001">
    <ideEvento><tpAmb>1</tpAmb><procEmi>1</procEmi></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>99991234000199</nrInsc></ideEmpregador>
  </evtInfoEmpregador>
  <retornoEnvio>
    <cdResposta>401</cdResposta>
    <descResposta>CNPJ do empregador nao consta na base da RFB ou esta inapto</descResposta>
    <ocorrencias>
      <ocorrencia>
        <tipo>E</tipo><codigo>E001</codigo>
        <descricao>CNPJ 99.991.234/0001-99 nao encontrado ou inapto na base da Receita Federal</descricao>
        <localizacao>ideEmpregador/nrInsc</localizacao>
      </ocorrencia>
    </ocorrencias>
  </retornoEnvio>
</eSocial>""",

    "S-2200 / E220 — CPF invalido na admissao": """\
<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtAdmissao/v02_09_00">
  <evtAdmissao Id="ID220099912340001202505090001">
    <ideEvento><indRetif>1</indRetif><tpAmb>1</tpAmb></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000195</nrInsc></ideEmpregador>
    <trabalhador>
      <cpfTrab>12345678901</cpfTrab>
      <nmTrab>Joao Silva</nmTrab>
      <dtNascto>1990-03-15</dtNascto>
    </trabalhador>
    <vinculo><tpRegTrab>1</tpRegTrab><dtAdm>2025-05-01</dtAdm></vinculo>
  </evtAdmissao>
  <retornoEnvio>
    <cdResposta>401</cdResposta>
    <descResposta>Erro de validacao nos dados do trabalhador</descResposta>
    <ocorrencias>
      <ocorrencia>
        <tipo>E</tipo><codigo>E220</codigo>
        <descricao>CPF do trabalhador nao consta na base da RFB ou esta cancelado/suspenso</descricao>
        <localizacao>trabalhador/cpfTrab</localizacao>
      </ocorrencia>
    </ocorrencias>
  </retornoEnvio>
</eSocial>""",

    "S-1200 / E302 — rubrica sem incidencia FGTS": """\
<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtRemun/v02_09_00">
  <evtRemun Id="ID1200123456780001202505090001">
    <ideEvento><indRetif>1</indRetif><perApur>2025-04</perApur><tpAmb>1</tpAmb></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000195</nrInsc></ideEmpregador>
    <dmDev>
      <ideDmDev>FOLHA2025-04</ideDmDev><codCateg>101</codCateg>
      <infoPerApur>
        <ideEstabLot>
          <tpInsc>1</tpInsc><nrInsc>12345678000195</nrInsc><codLotacao>001</codLotacao>
          <detVerbas>
            <codRubr>0500</codRubr><ideTabRubr>EMP001</ideTabRubr>
            <qtdRubr>1</qtdRubr><vrUnit>3500.00</vrUnit><vrRubr>3500.00</vrRubr>
          </detVerbas>
        </ideEstabLot>
      </infoPerApur>
    </dmDev>
  </evtRemun>
  <retornoEnvio>
    <cdResposta>401</cdResposta>
    <ocorrencias>
      <ocorrencia>
        <tipo>E</tipo><codigo>E302</codigo>
        <descricao>Rubrica 0500 nao possui incidencia de FGTS configurada na tabela S-1010. Envie o S-1010 antes do S-1200.</descricao>
        <localizacao>dmDev/infoPerApur/ideEstabLot/detVerbas/codRubr</localizacao>
      </ocorrencia>
    </ocorrencias>
  </retornoEnvio>
</eSocial>""",

    "R-2010 / ERF010 — retencao CSLL/COFINS/PIS incorreta": """\
<?xml version="1.0" encoding="UTF-8"?>
<EFD-Reinf xmlns="http://www.reinf.esocial.gov.br/schema/evtServTom/v02_01_00">
  <evtServTom Id="ID2010123456780001202505090001">
    <ideEvento><indRetif>1</indRetif><perApur>2025-04</perApur><tpAmb>1</tpAmb></ideEvento>
    <ideContri><tpInsc>1</tpInsc><nrInsc>12345678000195</nrInsc></ideContri>
    <ideEstab>
      <tpInsc>1</tpInsc><nrInsc>12345678000195</nrInsc>
      <infoServTom>
        <cnpjPrestador>98765432000188</cnpjPrestador>
        <vlrBruto>10000.00</vlrBruto>
        <vlrCsll>80.00</vlrCsll>
        <vlrCofins>240.00</vlrCofins>
        <vlrPis>55.00</vlrPis>
        <natRend>10308</natRend>
        <nrNF>2025001234</nrNF>
      </infoServTom>
    </ideEstab>
  </evtServTom>
  <retornoEnvio>
    <cdResposta>401</cdResposta>
    <ocorrencias>
      <ocorrencia>
        <tipo>E</tipo><codigo>ERF010</codigo>
        <descricao>Soma retencoes (CSLL+COFINS+PIS = R$ 375,00) diverge do esperado 4,65% s/ R$ 10.000,00 = R$ 465,00. CSLL esperado R$ 100,00 | COFINS R$ 300,00 | PIS R$ 65,00.</descricao>
      </ocorrencia>
    </ocorrencias>
  </retornoEnvio>
</EFD-Reinf>""",

    "R-4010 / ERF040 — IRRF tabela progressiva desatualizada": """\
<?xml version="1.0" encoding="UTF-8"?>
<EFD-Reinf xmlns="http://www.reinf.esocial.gov.br/schema/evtPgtoRendPF/v02_01_00">
  <evtPgtoRendPF Id="ID4010123456780001202505090001">
    <ideEvento><indRetif>1</indRetif><perApur>2025-04</perApur><tpAmb>1</tpAmb></ideEvento>
    <ideContri><tpInsc>1</tpInsc><nrInsc>12345678000195</nrInsc></ideContri>
    <ideBenef>
      <cpfBenef>98765432100</cpfBenef>
      <nmBenef>Maria Oliveira</nmBenef>
      <infoRend>
        <natRend>12001</natRend>
        <vlrBruto>8500.00</vlrBruto>
        <vlrRendTrib>8500.00</vlrRendTrib>
        <vlrIRRF>1275.00</vlrIRRF>
      </infoRend>
    </ideBenef>
  </evtPgtoRendPF>
  <retornoEnvio>
    <cdResposta>401</cdResposta>
    <ocorrencias>
      <ocorrencia>
        <tipo>E</tipo><codigo>ERF040</codigo>
        <descricao>IRRF informado R$ 1.275,00 diverge do esperado pela tabela progressiva 2025. Base R$ 8.500,00 | aliquota 22,5% | deducao R$ 869,36 | IRRF esperado R$ 1.043,14.</descricao>
      </ocorrencia>
    </ocorrencias>
  </retornoEnvio>
</EFD-Reinf>""",
}


# ─────────────────────────────────────────────────────────────────────────────
# Tabela KB
# ─────────────────────────────────────────────────────────────────────────────

def _build_kb_table() -> list[list[str]]:
    return [
        [
            inc.get("id", ""),
            inc.get("evento", ""),
            inc.get("codigo_erro", ""),
            inc.get("impacto", "").capitalize(),
            inc.get("titulo", "")[:90],
        ]
        for inc in _KB
    ]


# ─────────────────────────────────────────────────────────────────────────────
# UI Gradio
# ─────────────────────────────────────────────────────────────────────────────

with gr.Blocks(title="EII — ERP Incident Intelligence") as demo:

    gr.Markdown("""
# EII — ERP Incident Intelligence
**Diagnostico inteligente de incidentes eSocial e EFD-Reinf com IA**

Pipeline CRAG com Knowledge Base de 93 incidentes documentados e PII Scrubbing automatico (LGPD).
Cole o XML rejeitado pela plataforma e receba a causa raiz e os passos de resolucao.

---
""")

    with gr.Tabs():

        # ── Tab 1: Diagnostico ─────────────────────────────────────────────
        with gr.Tab("Diagnostico"):

            # Exemplos — botoes nomeados no topo
            gr.Markdown("**Carregar exemplo:**")
            with gr.Row():
                ex_btns = [gr.Button(label, size="sm") for label in EXAMPLES]

            with gr.Row():

                # Coluna esquerda — input (menor)
                with gr.Column(scale=2):
                    xml_input = gr.Textbox(
                        label="XML eSocial / EFD-Reinf",
                        lines=18,
                        placeholder="Cole aqui o XML de retorno rejeitado pela plataforma...\n\nOu clique em um dos exemplos acima para carregar um caso real.",
                    )
                    with gr.Row():
                        mentor_mode = gr.Checkbox(
                            label="Modo Mentor",
                            value=False,
                            scale=1,
                        )
                        diagnose_btn = gr.Button("Diagnosticar", variant="primary", scale=2)
                    gr.Markdown(
                        "_CPF, CNPJ e NIS sao removidos automaticamente antes do envio ao LLM (LGPD)._"
                    )

                # Coluna direita — output (maior)
                with gr.Column(scale=3):
                    output = gr.Markdown(
                        value=(
                            "### Como usar\n\n"
                            "1. **Escolha um exemplo** acima ou cole seu proprio XML\n"
                            "2. Clique em **Diagnosticar**\n"
                            "3. Receba a causa raiz e os passos de resolucao\n\n"
                            "---\n"
                            "_O pipeline busca incidentes similares na base de "
                            f"{_KB_TOTAL} casos documentados antes de gerar o diagnostico._"
                        ),
                    )

            # Conectar botoes de exemplo ao xml_input
            for btn, (label, xml_val) in zip(ex_btns, EXAMPLES.items()):
                btn.click(fn=lambda v=xml_val: v, inputs=[], outputs=[xml_input])

        # ── Tab 2: Base de Conhecimento ────────────────────────────────────
        with gr.Tab(f"Base de Conhecimento ({_KB_TOTAL})"):

            gr.Markdown(f"""
### Knowledge Base — {_KB_TOTAL} incidentes documentados

| Cobertura | Quantidade |
|---|---|
| eSocial (S-series) | **{_KB_ESOCIAL}** incidentes — S-1000 a S-2240, erros E001-E529 |
| EFD-Reinf (R-series) | **{_KB_REINF}** incidentes — R-1000 a R-9001, erros ERF001-ERF050 |

Cada incidente documenta: evento, codigo de erro, causa raiz detalhada, passos de resolucao step-by-step,
validacao e impacto. O pipeline CRAG usa essa base para recuperar contexto relevante antes de gerar o diagnostico.
""")

            if _KB:
                gr.Dataframe(
                    value=_build_kb_table(),
                    headers=["ID", "Evento", "Erro", "Impacto", "Titulo"],
                    datatype=["str", "str", "str", "str", "str"],
                    interactive=False,
                    wrap=True,
                )

        # ── Tab 3: Sobre ───────────────────────────────────────────────────
        with gr.Tab("Sobre"):
            gr.Markdown(f"""
### O que e o EII

O **EII (ERP Incident Intelligence)** e um sistema de diagnostico automatico de falhas de integracao
com o **eSocial** e a **EFD-Reinf**, desenvolvido para acelerar a resolucao de incidentes em ambientes
ERP/HCM corporativos.

---

### Pipeline desta demo

```
XML rejeitado pela plataforma
        |
[PII Scrubbing]     CPF / CNPJ / NIS removidos (LGPD)
        |
[KB Lookup]         Busca os {_KB_TOTAL} incidentes por sobreposicao de tokens
        |
[Groq LLM]          Llama 3.3 70b gera diagnostico com contexto KB
        |
[Resultado]         Causa raiz + passos de resolucao + validacao
```

---

### Versao local completa (v3.0)

A versao interna adiciona sobre esta demo:

| Recurso | Descricao |
|---|---|
| Deep Agents LangGraph | Pipeline de 8 nos com reflexao iterativa e confidence gate |
| SmartRouter | 9 LLMs roteados por tarefa (Groq, Qwen, Mistral, Cerebras, Ollama...) |
| HITL | Human-in-the-Loop — analista aprova ou rejeita cada diagnostico |
| IntelAgent | Analise proativa de padroes historicos via SQLite |
| REST API FastAPI | Integracao com sistemas ERP via X-API-Key |
| Alertas por e-mail | Notificacao quando incidente aguarda decisao HITL |
| Painel admin | Metricas, MTTR, taxa de aprovacao, gestao de sessoes |

---

### Tecnologias

`Python 3.12` · `Gradio 5` · `LangGraph` · `ChromaDB` · `sentence-transformers`
· `Groq (Llama 3.3 70b)` · `FastAPI` · `SQLite` · `smtplib`

---

### Links

- Repositorio: [github.com/edson-aiops/eii-erp-incident-intelligence](https://github.com/edson-aiops/eii-erp-incident-intelligence)
- Autor: Edson Oliveira
""")

    # ── Conectar handler ───────────────────────────────────────────────────
    diagnose_btn.click(
        fn=diagnose_public,
        inputs=[xml_input, mentor_mode],
        outputs=[output],
    )

if __name__ == "__main__":
    print(f"[EII] Demo Publica v3.0 | KB: {_KB_TOTAL} incidentes")
    print("[EII] http://127.0.0.1:7860")
    demo.launch(server_name="0.0.0.0", server_port=7860)
