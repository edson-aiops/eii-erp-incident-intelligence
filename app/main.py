"""
EII — ERP Incident Intelligence
Fase 1: Aplicação base rodando no HuggingFace Spaces

Próximas fases adicionam:
  Fase 2 → Groq LLM + ChromaDB + Knowledge Base
  Fase 3 → LangGraph Agents (LogAnalysis, RootCause, CRAG)
  Fase 4 → Langfuse observabilidade
  Fase 5 → RAGAS avaliação
"""

import os
import gradio as gr
from dotenv import load_dotenv

load_dotenv()

# ── Verificação de Ambiente ──────────────────────────────────
def check_env() -> dict:
    """Verifica quais APIs estão configuradas."""
    return {
        "groq":     bool(os.getenv("GROQ_API_KEY")),
        "langfuse_secret": bool(os.getenv("LANGFUSE_SECRET_KEY")),
        "langfuse_public": bool(os.getenv("LANGFUSE_PUBLIC_KEY")),
    }

# ── Status do Sistema ────────────────────────────────────────
def get_system_status() -> str:
    env = check_env()

    status_lines = ["## 🔍 Status do Sistema EII\n"]

    checks = {
        "🤖 Groq API (LLM)":        env["groq"],
        "📊 Langfuse Secret Key":    env["langfuse_secret"],
        "📊 Langfuse Public Key":    env["langfuse_public"],
    }

    all_ok = True
    for label, configured in checks.items():
        icon = "✅" if configured else "❌"
        status = "Configurado" if configured else "Não configurado"
        status_lines.append(f"{icon} **{label}**: {status}")
        if not configured:
            all_ok = False

    status_lines.append("\n---")

    # Status das fases
    status_lines.append("## 📋 Fases de Implementação\n")
    fases = [
        ("✅", "Fase 1", "Fundação — App rodando no HuggingFace Spaces"),
        ("⏳", "Fase 2", "LLM + RAG — Groq + ChromaDB + Knowledge Base Workday"),
        ("⏳", "Fase 3", "LangGraph — Agentes LogAnalysis + RootCause + CRAG"),
        ("⏳", "Fase 4", "Langfuse — Observabilidade e traces por agente"),
        ("⏳", "Fase 5", "RAGAS — Avaliação de qualidade do pipeline RAG"),
    ]
    for icon, fase, descricao in fases:
        status_lines.append(f"{icon} **{fase}**: {descricao}")

    if all_ok:
        status_lines.append("\n\n✅ **Ambiente pronto para Fase 2!**")
    else:
        status_lines.append("\n\n⚠️ **Configure as variáveis de ambiente para avançar.**")
        status_lines.append("\n**Como configurar no HuggingFace Spaces:**")
        status_lines.append("Settings → Variables and secrets → New secret")

    return "\n".join(status_lines)

# ── Simulação de Incidente (placeholder Fase 2) ──────────────
HCM_SYSTEMS = ["Workday", "Senior HCM", "UKG Pro", "UKG Ready", "UKG Dimensions"]

MODULES = {
    "Workday":        ["Payroll", "Benefits", "Recruiting", "Time & Attendance"],
    "Senior HCM":     ["Folha de Pagamento", "Benefícios", "Recrutamento & Seleção", "Ponto & Jornada", "eSocial"],
    "UKG Pro":        ["Payroll", "Benefits", "HR Core"],
    "UKG Ready":      ["Payroll", "Time & Attendance"],
    "UKG Dimensions": ["Workforce Management", "Time & Attendance"],
}

SAMPLE_INCIDENTS = {
    # Workday
    "Workday|Payroll":              "[ERROR] Workday: ITIN field missing for non-resident employee EMP-1234. Payroll calculation aborted for pay period 2024-11.",
    "Workday|Benefits":             "[ERROR] Workday: Benefits enrollment failed for NEW_HIRE EMP-5678. Eligibility rule 'FT_90_DAYS' not satisfied.",
    "Workday|Recruiting":           "[WARN] Workday: Job requisition REQ-9012 stuck in approval. Approver USER-456 inactive 15 days. SLA breach imminent.",
    "Workday|Time & Attendance":    "[ERROR] Workday: Time entry rejected EMP-3456: Overtime exceeds policy limit (12h). Manager approval workflow not triggered.",
    # Senior HCM
    "Senior HCM|Folha de Pagamento":        "[ERRO] Senior HCM: Cálculo de rescisão bloqueado para FUNC-7890. FGTS proporcional não calculado. Competência 2024-11.",
    "Senior HCM|eSocial":                   "[ERRO] Senior HCM: Evento S-1200 rejeitado pelo eSocial. Código MA105 - CNPJ do estabelecimento inválido.",
    "Senior HCM|Ponto & Jornada":           "[WARN] Senior HCM: Banco de horas negativo para FUNC-4521. Saldo: -32h. Política de compensação não aplicada.",
    "Senior HCM|Benefícios":                "[ERRO] Senior HCM: Integração com operadora de plano de saúde falhou. 143 vidas pendentes de inclusão. Prazo: 3 dias.",
    "Senior HCM|Recrutamento & Seleção":    "[WARN] Senior HCM: Vaga VAG-2234 sem movimentação há 45 dias. SLA de contratação em risco.",
    # UKG Pro
    "UKG Pro|Payroll":              "[ERROR] UKG Pro: Tax withholding calculation failed EMP-2341. Federal filing status mismatch. W-4 not updated since 2022.",
    "UKG Pro|HR Core":              "[ERROR] UKG Pro: Employee record sync failed. HRIS integration timeout 30s. 847 records pending.",
    "UKG Pro|Benefits":             "[ERROR] UKG Pro: Open enrollment auto-assignment failed. 234 employees missing elections. Deadline in 48h.",
    # UKG Ready
    "UKG Ready|Payroll":            "[ERROR] UKG Ready: Direct deposit rejected for 12 employees. Routing number validation failed. Next payroll in 2 days.",
    "UKG Ready|Time & Attendance":  "[WARN] UKG Ready: Punch exception threshold exceeded. 23 employees missing clock-out for shift 2024-11-15.",
    # UKG Dimensions
    "UKG Dimensions|Workforce Management":  "[ERROR] UKG Dimensions: Schedule optimization failed. Minimum rest period (11h) violation for 12 employees.",
    "UKG Dimensions|Time & Attendance":     "[ERROR] UKG Dimensions: Timecard approval workflow stuck. 89 timecards pending manager sign-off. Payroll processing in 4h.",
}

def get_modules_for_system(system: str) -> list:
    return MODULES.get(system, [])

def load_sample_incident(system: str, module: str) -> str:
    key = f"{system}|{module}"
    return SAMPLE_INCIDENTS.get(key, f"[ERROR] {system} — {module}: Incident log example not available for this combination.")

def process_incident_stub(log: str, system: str, module: str, language: str) -> tuple[str, str]:
    if not log.strip():
        return "⚠️ Nenhum log fornecido.", ""

    analysis = f"""## 📋 Análise do Incidente (Fase 1 — Estrutura Multi-HCM)

**Sistema HCM:** {system}
**Módulo:** {module}
**Idioma:** {"Português" if language == "pt" else "English"}

---

### Pipeline que será ativado nas próximas fases:

**Fase 2 — KB Multi-HCM:**
Groq/Llama 3.1 consultará a knowledge base específica de `{system} → {module}`

**Fase 3 — LangGraph:**
→ `HCMRouter` detecta automaticamente: *{system}*
→ `LogAnalysisAgent` classifica o tipo de erro
→ `RootCauseDiagnosisAgent` identifica a causa raiz
→ `CRAG Resolver` busca solução na KB com auto-correção

**Fase 4 — Langfuse:**
Cada etapa acima gerará um span rastreável no dashboard

**Fase 5 — RAGAS:**
Qualidade da resposta medida em faithfulness + relevancy + precision

---
*Log recebido: {len(log)} caracteres | Coleção KB: `{system.lower().replace(" ", "_")}_{module.lower().replace(" & ", "_").replace(" ", "_")}_{"pt" if language == "pt" else "en"}`*
"""
    return analysis, "🔗 Trace Langfuse: disponível na Fase 4"

# ── Interface Gradio ─────────────────────────────────────────
def build_ui():
    with gr.Blocks(
        title="EII — ERP Incident Intelligence",
        theme=gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="slate",
        ),
        css="""
        .header-box { text-align: center; padding: 20px; }
        .status-box { font-size: 0.9em; }
        """
    ) as demo:

        # ── Header ───────────────────────────────────────────
        gr.HTML("""
        <div class="header-box">
            <h1>🔍 EII — ERP Incident Intelligence</h1>
            <p style="color: #666; font-size: 1.1em;">
                Resolução de incidentes HCM com RAG + LangGraph + Langfuse
            </p>
            <p style="color: #888; font-size: 0.95em;">
                🔵 Workday &nbsp;·&nbsp; 🟢 Senior HCM &nbsp;·&nbsp; 🟠 UKG Pro · Ready · Dimensions
            </p>
            <p style="color: #999; font-size: 0.85em;">Fase 1 de 5 — Fundação</p>
        </div>
        """)

        # ── Tabs ─────────────────────────────────────────────
        with gr.Tabs():

            # Tab 1: Incident Resolver
            with gr.TabItem("🚨 Incident Resolver"):
                gr.Markdown("### Submeta um incidente para análise — Workday · Senior HCM · UKG")

                with gr.Row():
                    with gr.Column(scale=1):
                        system_input = gr.Dropdown(
                            choices=HCM_SYSTEMS,
                            value="Workday",
                            label="Sistema HCM",
                        )
                        module_input = gr.Dropdown(
                            choices=MODULES["Workday"],
                            value="Payroll",
                            label="Módulo",
                        )
                        language_input = gr.Radio(
                            choices=["pt", "en"],
                            value="pt",
                            label="Idioma da resposta"
                        )
                        load_sample_btn = gr.Button(
                            "📋 Carregar Exemplo",
                            variant="secondary",
                            size="sm"
                        )

                    with gr.Column(scale=2):
                        log_input = gr.Textbox(
                            label="Log do Incidente",
                            placeholder="Cole aqui o log de erro do sistema HCM...",
                            lines=6,
                            max_lines=15
                        )

                submit_btn = gr.Button(
                    "🔍 Analisar Incidente",
                    variant="primary",
                    size="lg"
                )

                analysis_output = gr.Markdown(
                    label="Análise e Resolução",
                    value="*Selecione o sistema, módulo e submeta um incidente...*"
                )

                trace_output = gr.Textbox(
                    label="Langfuse Trace",
                    value="",
                    interactive=False,
                )

                # Atualiza módulos quando sistema muda
                system_input.change(
                    fn=get_modules_for_system,
                    inputs=[system_input],
                    outputs=[module_input]
                )
                load_sample_btn.click(
                    fn=load_sample_incident,
                    inputs=[system_input, module_input],
                    outputs=[log_input]
                )
                submit_btn.click(
                    fn=process_incident_stub,
                    inputs=[log_input, system_input, module_input, language_input],
                    outputs=[analysis_output, trace_output]
                )

            # Tab 2: Status do Sistema
            with gr.TabItem("⚙️ Status do Sistema"):
                gr.Markdown("### Configuração e status das integrações")
                status_output = gr.Markdown(
                    value=get_system_status(),
                    elem_classes=["status-box"]
                )
                refresh_btn = gr.Button("🔄 Verificar Status", variant="secondary")
                refresh_btn.click(fn=get_system_status, outputs=[status_output])

            # Tab 3: Sobre o EII
            with gr.TabItem("📖 Sobre o EII"):
                gr.Markdown("""
## ERP Incident Intelligence (EII) — Multi-HCM

Sistema AIOps de resolução de incidentes para **Workday · Senior HCM · UKG**,
implementando RAG avançado com LangGraph e observabilidade via Langfuse.

### Sistemas e Módulos Cobertos

| Sistema | Módulos |
|---------|---------|
| **🔵 Workday** | Payroll, Benefits, Recruiting, Time & Attendance |
| **🟢 Senior HCM** | Folha, Benefícios, Recrutamento, Ponto & Jornada, eSocial |
| **🟠 UKG Pro** | Payroll, Benefits, HR Core |
| **🟠 UKG Ready** | Payroll, Time & Attendance |
| **🟠 UKG Dimensions** | Workforce Management, Time & Attendance |

### Pipeline de Resolução

```
Log Input → HCM Router → LogAnalysis → RootCause → CRAG → Resolução
                │
                ├── Workday KB  (PT/EN)
                ├── Senior KB   (PT)
                └── UKG KB      (PT/EN)
```

### Stack Tecnológico

- **LLM:** Groq API — Llama 3.1 70B (gratuito)
- **Orquestração:** LangGraph (multi-agente)
- **Vector Store:** ChromaDB — 26 coleções multi-HCM
- **Observabilidade:** Langfuse Cloud
- **Avaliação:** RAGAS
- **Deploy:** HuggingFace Spaces (Docker)
- **Custo total:** $0/mês
                """)

    return demo

# ── Entry Point ──────────────────────────────────────────────
if __name__ == "__main__":
    demo = build_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
    )
