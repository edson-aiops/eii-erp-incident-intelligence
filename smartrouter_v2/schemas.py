"""SmartRouter — Schemas & Enums.

Pydantic models for task classification, provider config and routing results.
Part of EII (ERP Incident Intelligence) infrastructure layer.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Task Categories ──────────────────────────────────────────────────────────

class TaskType(str, Enum):
    """Categories that drive routing decisions."""
    CODING_COMPLEX = "coding_complex"       # Módulos >100 linhas, lógica multi-step
    CODING_CLEAN = "coding_clean"           # Schemas, adapters, testes, boilerplate
    VALIDATION = "validation"               # Testar prompts, classificar, triagem
    LONG_CONTEXT = "long_context"           # Analisar codebase inteira, docs longos
    DEEP_REASONING = "deep_reasoning"       # Debug complexo, edge cases, lógica
    ARCHITECTURE = "architecture"           # Design patterns, integração, revisão
    SENSITIVE_DATA = "sensitive_data"       # PII, CPF, dados eSocial, LGPD
    ITERATION = "iteration"                 # Drafts, exploração, prompt engineering
    GENERAL = "general"                     # Fallback genérico


class Complexity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProviderID(str, Enum):
    KIMI = "kimi"
    QWEN = "qwen"
    CEREBRAS = "cerebras"
    GEMINI = "gemini"
    GROQ = "groq"
    MISTRAL = "mistral"
    DEEPSEEK = "deepseek"
    CLAUDE = "claude"
    OLLAMA = "ollama"


# ── Classification ───────────────────────────────────────────────────────────

class TaskClassification(BaseModel):
    """Output of the TaskClassifier."""
    task_type: TaskType
    complexity: Complexity
    requires_long_context: bool = False
    has_sensitive_data: bool = False
    estimated_tokens: int = Field(default=2000, ge=0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


# ── Provider Config ──────────────────────────────────────────────────────────

class ProviderConfig(BaseModel):
    """Configuration for a single LLM provider."""
    id: ProviderID
    name: str
    base_url: str
    model: str
    api_key_env: str                        # Nome da env var (nunca o valor)
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout_seconds: float = 30.0
    enabled: bool = True


class RoutingRule(BaseModel):
    """Maps a TaskType to primary + fallback provider."""
    task_type: TaskType
    primary: ProviderID
    fallback: ProviderID
    description: str = ""


# ── Execution Results ────────────────────────────────────────────────────────

class ProviderStatus(str, Enum):
    OK = "ok"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    CIRCUIT_OPEN = "circuit_open"


class RoutingResult(BaseModel):
    """Full trace of a routed request — for observability."""
    task_input: str
    classification: TaskClassification
    provider_used: ProviderID
    was_fallback: bool = False
    status: ProviderStatus = ProviderStatus.OK
    response: str = ""
    latency_ms: float = 0.0
    tokens_used: int = 0
    cost_estimate_usd: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
