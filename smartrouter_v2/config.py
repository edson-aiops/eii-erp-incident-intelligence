"""SmartRouter — Provider & Routing Configuration.

All 9 providers configured. API keys are read from environment variables.
All APIs are OpenAI-compatible — only base_url and api_key change.

Usage:
    export MOONSHOT_API_KEY=...
    export GROQ_API_KEY=...
    export CEREBRAS_API_KEY=...
    export GOOGLE_AI_API_KEY=...
    export MISTRAL_API_KEY=...
    export ANTHROPIC_API_KEY=...
    # Ollama: no key needed (local)
"""

from __future__ import annotations

from .schemas import (
    Complexity,
    ProviderConfig,
    ProviderID,
    RoutingRule,
    TaskType,
)

# ── Provider Definitions ─────────────────────────────────────────────────────

PROVIDERS: dict[str, ProviderConfig] = {
    # ── 7 FREE ───────────────────────────────────────────────────────────
    ProviderID.KIMI: ProviderConfig(
        id=ProviderID.KIMI,
        name="Llama 3.3 70B (Groq — fallback geral)",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        temperature=0.6,
        timeout_seconds=30.0,
    ),
    ProviderID.QWEN: ProviderConfig(
        id=ProviderID.QWEN,
        name="Qwen 3 235B (via Groq)",
        base_url="https://api.groq.com/openai/v1",
        model="qwen-qwq-32b",              # best free Qwen on Groq
        api_key_env="GROQ_API_KEY",
        temperature=0.7,
        timeout_seconds=30.0,
    ),
    ProviderID.CEREBRAS: ProviderConfig(
        id=ProviderID.CEREBRAS,
        name="Cerebras (Llama 3.3 70B )",
        base_url="https://api.cerebras.ai/v1",
        model="llama3.1-8b",
        api_key_env="CEREBRAS_API_KEY",
        temperature=0.3,                    # low temp for classification
        timeout_seconds=10.0,               # should be instant
    ),
    ProviderID.GEMINI: ProviderConfig(
        id=ProviderID.GEMINI,
        name="Gemini 2.5 Pro (Google)",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        model="gemini-2.5-flash",
        api_key_env="GOOGLE_AI_API_KEY",
        max_tokens=8192,
        timeout_seconds=60.0,
    ),
    ProviderID.GROQ: ProviderConfig(
        id=ProviderID.GROQ,
        name="Groq (Llama 3.3 70B)",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        timeout_seconds=15.0,
    ),
    ProviderID.MISTRAL: ProviderConfig(
        id=ProviderID.MISTRAL,
        name="Mistral Large 3",
        base_url="https://api.mistral.ai/v1",
        model="mistral-large-latest",
        api_key_env="MISTRAL_API_KEY",
        timeout_seconds=30.0,
    ),
    ProviderID.DEEPSEEK: ProviderConfig(
        id=ProviderID.DEEPSEEK,
        name="QwQ 32B reasoning (via Groq)",
        base_url="https://api.groq.com/openai/v1",
        model="qwen-qwq-32b",
        api_key_env="GROQ_API_KEY",
        temperature=0.6,
        timeout_seconds=45.0,
    ),

    # ── 1 PAID ───────────────────────────────────────────────────────────
    ProviderID.CLAUDE: ProviderConfig(
        id=ProviderID.CLAUDE,
        name="Claude Sonnet 4.6 (Anthropic)",
        base_url="https://api.anthropic.com/v1",
        model="claude-sonnet-4-6",
        api_key_env="ANTHROPIC_API_KEY",
        timeout_seconds=60.0,
    ),

    # ── 1 LOCAL ──────────────────────────────────────────────────────────
    ProviderID.OLLAMA: ProviderConfig(
        id=ProviderID.OLLAMA,
        name="Gemma 4 26B (Ollama local)",
        base_url="http://localhost:11434/v1",
        model="gemma4:26b",
        api_key_env="OLLAMA_API_KEY",       # dummy, Ollama ignores it
        timeout_seconds=120.0,              # local can be slow
    ),
}


# ── Routing Rules ────────────────────────────────────────────────────────────
# Each TaskType maps to a primary and fallback provider.

ROUTING_RULES: list[RoutingRule] = [
    RoutingRule(
        task_type=TaskType.CODING_COMPLEX,
        primary=ProviderID.KIMI,
        fallback=ProviderID.QWEN,
        description="Kimi K2.5 thinking mode para código complexo. Qwen como backup.",
    ),
    RoutingRule(
        task_type=TaskType.CODING_CLEAN,
        primary=ProviderID.QWEN,
        fallback=ProviderID.MISTRAL,
        description="Qwen preciso em código limpo. Codestral (Mistral) como alternativa.",
    ),
    RoutingRule(
        task_type=TaskType.VALIDATION,
        primary=ProviderID.CEREBRAS,
        fallback=ProviderID.GROQ,
        description="Cerebras 3000 tok/s = feedback instantâneo. Groq como segundo.",
    ),
    RoutingRule(
        task_type=TaskType.LONG_CONTEXT,
        primary=ProviderID.GEMINI,
        fallback=ProviderID.KIMI,
        description="Gemini 1M ctx é imbatível. Kimi 256K como segunda opção.",
    ),
    RoutingRule(
        task_type=TaskType.DEEP_REASONING,
        primary=ProviderID.DEEPSEEK,
        fallback=ProviderID.KIMI,
        description="DeepSeek R1 chain-of-thought nativo. Kimi thinking mode como alt.",
    ),
    RoutingRule(
        task_type=TaskType.ARCHITECTURE,
        primary=ProviderID.CLAUDE,
        fallback=ProviderID.KIMI,
        description="Claude insubstituível para decisões arquiteturais.",
    ),
    RoutingRule(
        task_type=TaskType.SENSITIVE_DATA,
        primary=ProviderID.OLLAMA,
        fallback=ProviderID.CLAUDE,
        description="Dados nunca saem da rede. Gemma 4 local + scrub_pii().",
    ),
    RoutingRule(
        task_type=TaskType.ITERATION,
        primary=ProviderID.GROQ,
        fallback=ProviderID.CEREBRAS,
        description="Groq bom equilíbrio velocidade/qualidade para drafts.",
    ),
    RoutingRule(
        task_type=TaskType.GENERAL,
        primary=ProviderID.GROQ,
        fallback=ProviderID.QWEN,
        description="Groq como default generalista. Qwen como fallback.",
    ),
]


# ── Classification Keywords ──────────────────────────────────────────────────
# Phase 1: rule-based classifier uses keyword matching.
# Phase 2: this will be replaced by Cerebras LLM classification.

CLASSIFICATION_KEYWORDS: dict[TaskType, list[str]] = {
    TaskType.CODING_COMPLEX: [
        "implement", "implementar", "refactor", "refatorar", "module", "módulo",
        "class", "classe", "multi-step", "pipeline", "agent", "agente",
        "langgraph", "graph", "grafo", "orchestrat", "orquestrar",
    ],
    TaskType.CODING_CLEAN: [
        "schema", "pydantic", "adapter", "template", "test", "teste",
        "unittest", "pytest", "boilerplate", "crud", "model", "dataclass",
        "enum", "config", "yaml", "json",
    ],
    TaskType.VALIDATION: [
        "validate", "validar", "check", "verificar", "classify", "classificar",
        "triage", "triagem", "smoke", "quick", "rápido", "fast",
    ],
    TaskType.LONG_CONTEXT: [
        "codebase", "entire", "inteiro", "whole", "todo", "analyze all",
        "analisar tudo", "merge", "consolidate", "consolidar", "documentation",
        "documentação", "all files", "todos arquivos",
    ],
    TaskType.DEEP_REASONING: [
        "debug", "debugar", "edge case", "corner case", "why", "por que",
        "root cause", "causa raiz", "logic", "lógica", "math", "proof",
        "reasoning", "raciocínio",
    ],
    TaskType.ARCHITECTURE: [
        "architecture", "arquitetura", "design", "pattern", "padrão",
        "integration", "integração", "qdrant", "langraph", "review",
        "revisão", "decision", "decisão", "adr", "trade-off",
    ],
    TaskType.SENSITIVE_DATA: [
        "pii", "cpf", "cnpj", "nis", "lgpd", "sensitive", "sensível",
        "personal", "pessoal", "esocial", "trabalhador", "employee",
        "scrub", "anonimizar", "anonymize",
    ],
    TaskType.ITERATION: [
        "draft", "rascunho", "try", "tentar", "explore", "explorar",
        "prompt", "experiment", "experimentar", "brainstorm", "idea",
    ],
}


# ── Cost Estimates (USD per 1M tokens) ───────────────────────────────────────
# Used for observability / cost tracking. "0" = free tier.

COST_PER_MILLION_TOKENS: dict[ProviderID, dict[str, float]] = {
    ProviderID.KIMI:     {"input": 0.60, "output": 2.50},
    ProviderID.QWEN:     {"input": 0.00, "output": 0.00},   # free via Groq
    ProviderID.CEREBRAS: {"input": 0.00, "output": 0.00},   # free tier
    ProviderID.GEMINI:   {"input": 0.00, "output": 0.00},   # free tier
    ProviderID.GROQ:     {"input": 0.00, "output": 0.00},   # free tier
    ProviderID.MISTRAL:  {"input": 0.00, "output": 0.00},   # 1B tok/month free
    ProviderID.DEEPSEEK: {"input": 0.00, "output": 0.00},   # free via Groq
    ProviderID.CLAUDE:   {"input": 3.00, "output": 15.00},  # Sonnet 4.6
    ProviderID.OLLAMA:   {"input": 0.00, "output": 0.00},   # local
}
