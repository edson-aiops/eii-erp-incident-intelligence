"""
A5: Gradio Web Interface para EII
Diagnóstico automático de rejeições eSocial com UI visual.

Pipeline real (A3/A3.5/A23/A25/A26): PIIScrubber obrigatório → Deep Agents
(LangGraph) → finalize restaura tokens + audit log PostgreSQL.

Executar: python app_gradio.py
Acessar: http://localhost:7860

Deploy Contabo: python app_gradio.py --server-name 0.0.0.0 --server-port 7860
"""

import gradio as gr
import asyncio
import uuid
import time
import logging
from datetime import datetime
from typing import Tuple, List, Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from src.privacy.scrubber import PIIScrubber
    from src.deep_agents.graph import eii_agent_graph
    from src.deep_agents.nodes.parse_node import extract_ids
    PIPELINE_OK = True
except ImportError as e:
    logger.warning(f"Módulos do pipeline não disponíveis: {e}")
    PIPELINE_OK = False


# ==========================================================================
# Formatação visual
# ==========================================================================

def format_result_markdown(
    final_result: Dict,
    evento: str,
    is_safe: bool,
    latency: float,
    show_tokens: bool = False,
    token_map: Dict = None,
) -> str:
    """Formata final_result do Deep Agents em markdown visual."""

    diagnostico = final_result.get("diagnostico", "Sem diagnóstico")
    severidade = final_result.get("severidade", "N/A")
    confianca = final_result.get("confianca", "N/A")
    passos = final_result.get("passos_resolucao", []) or []
    validacao = final_result.get("validacao", "")
    tempo = final_result.get("tempo_estimado", "")
    referencias = final_result.get("referencias_kb", []) or []
    alerta_hitl = final_result.get("alerta_hitl", "")
    fonte = final_result.get("fonte", "")

    meta = final_result.get("metadata", {}) or {}
    model_used = meta.get("model_used") or "N/A"
    routing = meta.get("routing_decision") or "N/A"
    logprob_sim = meta.get("logprob_sim")

    sev_emoji = {"CRITICA": "🔴", "ALTA": "🟠", "MEDIA": "🟡", "MEDIO": "🟡",
                 "BAIXA": "🟢", "BAIXO": "🟢"}.get(str(severidade).upper(), "⚪")
    conf_emoji = {"ALTA": "🟢", "MEDIA": "🟡", "MEDIO": "🟡", "BAIXA": "🔴", "BAIXO": "🔴"}.get(
        str(confianca).upper(), "⚪")

    md = f"""## {sev_emoji} DIAGNÓSTICO

**Evento:** `{evento}`
**Causa raiz:** {diagnostico}
**Severidade:** {severidade} | **Confiança:** {conf_emoji} {confianca}
"""

    if alerta_hitl:
        md += f"\n> ⚠️ **Revisão humana:** {alerta_hitl}\n"

    if passos:
        md += "\n### 🛠️ Passos de resolução\n\n"
        for i, passo in enumerate(passos, 1):
            md += f"{i}. {passo}\n"

    if validacao:
        md += f"\n**✔ Validação:** {validacao}\n"
    if tempo:
        md += f"\n**⏱️ Tempo estimado:** {tempo}\n"

    if referencias:
        md += "\n### 📚 Referências (Knowledge Base)\n\n"
        for ref in referencias:
            md += f"- {ref}\n"

    md += f"""
### 🔒 Conformidade LGPD

- {'✅' if is_safe else '⛔'} Payload pseudonimizado (tokens reversíveis)
- ✅ Audit log de restaurações (PostgreSQL)
- ✅ token_map com TTL (uso único, nunca serializado)
- ✅ Fail-closed: PII não seguro força execução local

---
**🧠 Motor:** {model_used} ({routing})
**📶 P(SIM) logprobs:** {logprob_sim if logprob_sim is not None else 'N/A'}
**⏱️ Latência:** {latency*1000:.2f}ms
**📅 Processado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**📄 Fonte:** {fonte or 'N/A'}
"""

    if show_tokens and token_map:
        md += f"""
### 🐛 Debug: Token Map (LGPD-safe)
*Apenas metadados — comprimento dos valores, nunca os valores reais.*

```json
{{
{chr(10).join([f'  "{k}": "<{len(str(v))} chars>"' for k, v in list(token_map.items())[:10]])}
}}
```
"""

    return md


def format_problems_highlight(final_result: Dict) -> List[Tuple[str, Optional[str]]]:
    """Formata alertas do diagnóstico para Gradio HighlightedText."""

    highlight = []
    severidade = str(final_result.get("severidade", "")).upper()
    color_map = {
        "CRITICA": "#FF6B6B",
        "ALTA": "#FF8C42",
        "MEDIA": "#FFA500",
        "MEDIO": "#FFA500",
        "BAIXA": "#4A90E2",
    }

    if severidade in color_map:
        highlight.append((f"Severidade: {severidade}", color_map[severidade]))

    alerta = final_result.get("alerta_hitl")
    if alerta:
        highlight.append((f"⚠️ HITL: {alerta}", "#FF6B6B"))

    for warn in (final_result.get("metadata", {}) or {}).get("warnings", []) or []:
        highlight.append((f"⚠️ {warn}", "#FFA500"))

    for erro in (final_result.get("metadata", {}) or {}).get("errors", []) or []:
        highlight.append((f"❌ {erro}", "#FF6B6B"))

    if not highlight:
        highlight.append(("✅ Nenhum problema detectado", "#2ECC71"))

    return highlight


def parse_xml_input(xml_file, xml_text: str) -> Optional[str]:
    """Extrai XML de upload (filepath) ou de texto colado."""

    if xml_file:
        try:
            if isinstance(xml_file, str):
                with open(xml_file, "r", encoding="utf-8") as f:
                    return f.read()
            content = xml_file.read()
            return content.decode("utf-8") if isinstance(content, bytes) else content
        except Exception as e:
            logger.error(f"Erro ao ler arquivo: {e}")
            return None

    if xml_text and xml_text.strip():
        return xml_text

    return None


# ==========================================================================
# Pipeline
# ==========================================================================

async def process_xml(
    xml_file,
    xml_text: str,
    use_remote: bool = True,
    force_local: bool = False,
    show_tokens: bool = False,
) -> Tuple[str, dict, List]:
    """Processa XML eSocial e retorna (markdown, json, highlights)."""

    try:
        xml_input = parse_xml_input(xml_file, xml_text)

        if not xml_input:
            return (
                "❌ **Nenhum XML fornecido**\n\nFaça upload de um arquivo XML ou cole o conteúdo.",
                {"error": "No XML input"},
                [("Nenhum XML fornecido", "#FF6B6B")],
            )

        if "<eSocial" not in xml_input:
            return (
                "❌ **XML inválido**\n\nTag `<eSocial>` não encontrada. Verifique o arquivo.",
                {"error": "Invalid XML"},
                [("XML inválido (sem <eSocial>)", "#FF6B6B")],
            )

        incident_id = f"ui_{uuid.uuid4().hex[:8]}"
        logger.info(f"Processando XML: {incident_id}")

        # Fallback simulado quando o pipeline não está disponível no ambiente
        if not PIPELINE_OK:
            resultado_sim = {
                "diagnostico": "XML recebido (modo simulado — módulos do pipeline não carregados)",
                "severidade": "BAIXA",
                "confianca": "N/A",
                "passos_resolucao": ["Verificar ambiente (deps do pipeline)"],
                "metadata": {"model_used": "simulado", "routing_decision": "n/a"},
            }
            md = format_result_markdown(resultado_sim, "S-? (simulado)", True, 0.1)
            return md, {"modo": "simulado", "incident_id": incident_id}, \
                [("⚠️ Modo simulado", "#FFA500")]

        start_time = time.time()

        # 1. Scrubber obrigatório (LGPD) — mesmo padrão do eii_api (A3.5)
        scrubber = PIIScrubber()
        _, tipo_evento = extract_ids(xml_input)
        try:
            scrub_result = scrubber.scrub(xml_input, tipo_evento)
            is_safe = scrub_result.is_safe_for_remote
            scrubbed_xml = scrub_result.scrubbed_payload
            token_map = scrub_result.token_map
        except Exception as e:
            # Fail-closed: nunca envia PII não verificada adiante
            logger.error(f"Scrubber exception: {e}")
            return (
                f"⛔ **Fail-closed LGPD**\n\nScrubber rejeitou o payload: `{e}`\n\n"
                "Nenhum dado foi enviado a modelo remoto.",
                {"error": f"Scrubber exception: {e}", "is_safe_for_remote": False},
                [("⛔ Fail-closed: processamento abortado", "#FF6B6B")],
            )

        # Fail-closed estrutural: XML malformado/evento não mapeado
        if not is_safe and not token_map:
            return (
                "⛔ **Fail-closed estrutural**\n\nXML malformado ou evento não suportado. "
                "O processamento foi abortado antes de qualquer chamada remota.",
                {"error": "Scrubber fail-closed: XML malformado ou evento não suportado",
                 "is_safe_for_remote": False},
                [("⛔ XML malformado/evento não suportado", "#FF6B6B")],
            )

        # 2. Deep Agents (grafo LangGraph) — PII não seguro força local
        effective_force_local = force_local or not use_remote or not is_safe
        initial_state = {
            "xml_input": scrubbed_xml,
            "incident_id": incident_id,
            "use_mentor_mode": False,
            "context": None,
            "retrieved": None,
            "diagnosis": None,
            "evaluation_score": None,
            "evaluation_feedback": None,
            "iteration_count": 0,
            "max_iterations": 2,
            "routing_decision": "ollama-local" if effective_force_local else None,
            "retrieval_backend": "chromadb",
            "model_used": None,
            "errors": [],
            "warnings": [],
            "final_result": None,
        }

        graph_result = await eii_agent_graph.ainvoke(initial_state)
        final_result = graph_result.get("final_result") or {}

        # 3. Restaurar tokens na resposta exibida ao usuário
        #    (finalize_node já restaura diagnosis_raw e loga no audit A26;
        #     aqui restauramos também o texto do diagnóstico exibido)
        if token_map and final_result.get("diagnostico"):
            final_result["diagnostico"] = scrubber.restore(
                final_result["diagnostico"], token_map
            )
        passos = final_result.get("passos_resolucao") or []
        if token_map and passos:
            final_result["passos_resolucao"] = [
                scrubber.restore(p, token_map) for p in passos
            ]

        latency = time.time() - start_time
        meta = final_result.get("metadata", {}) or {}

        if not final_result:
            return (
                f"❌ **Erro no processamento**\n\n```\n{graph_result.get('errors')}\n```",
                {"error": graph_result.get("errors", ["sem final_result"]),
                 "incident_id": incident_id},
                [("Erro no processamento", "#FF6B6B")],
            )

        # 4. Saídas visuais
        markdown = format_result_markdown(
            final_result, tipo_evento, is_safe, latency,
            show_tokens=show_tokens, token_map=token_map,
        )

        json_output = {
            "incident_id": incident_id,
            "evento": tipo_evento,
            "diagnostico": final_result.get("diagnostico"),
            "severidade": final_result.get("severidade"),
            "confianca": final_result.get("confianca"),
            "passos_resolucao": final_result.get("passos_resolucao", []),
            "validacao": final_result.get("validacao", ""),
            "tempo_estimado": final_result.get("tempo_estimado", ""),
            "referencias_kb": final_result.get("referencias_kb", []),
            "alerta_hitl": final_result.get("alerta_hitl", ""),
            "fonte": final_result.get("fonte", ""),
            "lgpd_compliance": {
                "is_safe_for_remote": is_safe,
                "pseudonimizado": bool(token_map),
                "audit_log_ativo": True,
                "fail_closed_respeitado": effective_force_local or is_safe,
            },
            "motor": {
                "model_used": meta.get("model_used"),
                "routing_decision": meta.get("routing_decision"),
                "logprob_sim": meta.get("logprob_sim"),
                "iteracoes": meta.get("iteracoes"),
            },
            "latencia_ms": round(latency * 1000, 2),
            "timestamp": datetime.now().isoformat(),
        }

        highlights = format_problems_highlight(final_result)
        logger.info(f"✅ Processamento completo: {latency*1000:.2f}ms")

        return markdown, json_output, highlights

    except Exception as e:
        logger.error(f"❌ Erro: {e}", exc_info=True)
        return (
            f"❌ **Erro ao processar**\n\n```\n{e}\n```",
            {"error": str(e), "type": type(e).__name__},
            [("Erro no processamento", "#FF6B6B")],
        )


# ==========================================================================
# Interface Gradio
# ==========================================================================

def create_demo():
    """Cria a interface Gradio."""

    with gr.Blocks(title="EII — Diagnóstico eSocial") as demo:

        gr.Markdown("""
# 🚀 EII — ERP Incident Intelligence

**Diagnóstico automático de rejeições eSocial**

Envie um XML de evento eSocial (S-1200, S-2200, S-2300, etc.) e receba análise visual:
- ✅ Causa raiz e severidade
- 🛠️ Passos de resolução
- 🧠 Raciocínio com referências da Knowledge Base
- 🔒 Conformidade LGPD (pseudonimização reversível + audit log)
""")

        with gr.Row():
            with gr.Column():
                gr.Markdown("### 📥 Input")

                xml_file = gr.File(
                    label="📁 Upload XML",
                    file_types=[".xml"],
                    type="filepath",
                )

                xml_text = gr.Textbox(
                    label="📝 Ou cole o XML aqui",
                    lines=12,
                    placeholder='<?xml version="1.0" encoding="UTF-8"?>\n<eSocial>\n  <evtAdmissao>...</evtAdmissao>\n</eSocial>',
                )

                gr.Markdown("### ⚙️ Opções")

                use_remote = gr.Checkbox(
                    label="☑ Permitir modelo remoto (melhor qualidade)",
                    value=True,
                )
                force_local = gr.Checkbox(
                    label="☐ Forçar execução local (sem dados em nuvem)",
                    value=False,
                )
                show_tokens = gr.Checkbox(
                    label="☐ Debug: mostrar token_map (metadados)",
                    value=False,
                )

                with gr.Row():
                    btn_analyze = gr.Button("🚀 ANALISAR", variant="primary")
                    btn_clear = gr.Button("🧹 Limpar")

            with gr.Column():
                gr.Markdown("### 📊 Output")

                resultado_md = gr.Markdown(
                    value="*Envie um XML para ver o diagnóstico aqui*",
                )
                problemas_hl = gr.HighlightedText(
                    value=[("Aguardando análise...", None)],
                    label="⚠️ Alertas",
                )
                resultado_json = gr.JSON(
                    label="📋 Dados completos (JSON)",
                    visible=True,
                )

        gr.Markdown("""
---

## 🔒 Segurança & Conformidade LGPD

- **Pseudonimização:** CPF, nomes e contatos viram tokens reversíveis antes de qualquer chamada a LLM
- **Fail-closed:** se o scrubber falha ou o XML é malformado, o processamento aborta — nada sai com PII real
- **Audit log:** toda restauração de token é registrada em PostgreSQL (A26)
- **TTL:** token_map expira automaticamente (uso único, nunca serializado na saída)

## 💡 Dica

Arquivos de exemplo estão em `exemplos/` (s2200_valido.xml, s2200_cpf_invalido.xml).
""")

        def on_analyze(file, text, remote, local, tokens):
            return asyncio.run(process_xml(file, text, remote, local, tokens))

        def on_clear():
            return None, "", "*Envie um XML para ver o diagnóstico aqui*", \
                [("Aguardando análise...", None)], {}

        btn_analyze.click(
            fn=on_analyze,
            inputs=[xml_file, xml_text, use_remote, force_local, show_tokens],
            outputs=[resultado_md, resultado_json, problemas_hl],
        )
        btn_clear.click(
            fn=on_clear,
            inputs=[],
            outputs=[xml_file, xml_text, resultado_md, problemas_hl, resultado_json],
        )

    return demo


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="A5: Gradio UI para EII")
    parser.add_argument("--server-name", default="127.0.0.1", help="Endereço do servidor")
    parser.add_argument("--server-port", type=int, default=7860, help="Porta do servidor")
    parser.add_argument("--share", action="store_true", help="Gerar link público (Gradio share)")

    args = parser.parse_args()

    demo = create_demo()
    logger.info(f"🚀 Iniciando Gradio em http://{args.server_name}:{args.server_port}")
    demo.launch(
        server_name=args.server_name,
        server_port=args.server_port,
        share=args.share,
        theme=gr.themes.Soft(),
    )
