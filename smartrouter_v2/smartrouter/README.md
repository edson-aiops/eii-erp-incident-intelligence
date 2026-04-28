# SmartRouter — Multi-LLM Orchestrator

> Routes tasks to the best LLM provider based on competency profiling.  
> 9 providers: 7 free + 1 paid + 1 local. All OpenAI-compatible.

## Architecture

```
Task Input → TaskClassifier → RoutingEngine → UnifiedClient → Response
                                    ↕
                             CircuitBreaker
                          (timeout/429 → fallback)
```

## Providers

| Provider | Specialty | Cost | Speed |
|----------|-----------|------|-------|
| **Kimi K2.5** | Coding complexo, reasoning | Free chat / $0.60/M API | ~60 tok/s |
| **Qwen 3** | Código limpo, schemas | Free (Groq) | ~200 tok/s |
| **Cerebras** | Validação ultra-rápida | Free (1M tok/dia) | ~3000 tok/s |
| **Gemini 2.5 Pro** | Contexto longo (1M) | Free | ~150 tok/s |
| **Groq** | Iteração, drafts | Free | ~300 tok/s |
| **Mistral Large 3** | EU compliance, Codestral | Free (1B tok/mês) | ~100 tok/s |
| **DeepSeek R1** | Raciocínio profundo | Free (Groq) | varies |
| **Claude** | Arquitetura, integração | Paid (Pro) | ~80 tok/s |
| **Ollama (Gemma 4)** | LGPD, dados sensíveis | Local (free) | ~10-30 tok/s |

## Routing Rules

| Task Type | Primary → Fallback |
|-----------|-------------------|
| Coding complexo | Kimi → Qwen |
| Código limpo | Qwen → Mistral |
| Validação rápida | Cerebras → Groq |
| Contexto longo | Gemini → Kimi |
| Raciocínio profundo | DeepSeek → Kimi |
| Arquitetura | Claude → Kimi |
| Dados sensíveis | Ollama → Claude |
| Iteração/draft | Groq → Cerebras |

## Quick Start

```bash
# Set API keys
export GROQ_API_KEY=your_key
export CEREBRAS_API_KEY=your_key
export GOOGLE_AI_API_KEY=your_key
export MOONSHOT_API_KEY=your_key
export MISTRAL_API_KEY=your_key

# Install deps
pip install openai pydantic pytest pytest-asyncio

# Run
python -m smartrouter "Implement a Pydantic schema for IntelItem"

# Classify only (no API call)
python -m smartrouter --classify "Debug the edge case in scoring"

# Force provider
python -m smartrouter --provider kimi "Refactor this module"

# Force task type
python -m smartrouter --type architecture "Review my design"

# Run tests
pytest tests/test_smartrouter.py -v
```

## Usage in Code

```python
import asyncio
from smartrouter import SmartRouter, TaskType, ProviderID

router = SmartRouter()

# Auto-routed
result = await router.route("Implement a LangGraph pipeline")
print(f"Provider: {result.provider_used}")  # → kimi
print(result.response)

# Force provider
result = await router.route("Quick check", force_provider=ProviderID.CEREBRAS)

# Force type
result = await router.route("Review this", force_type=TaskType.ARCHITECTURE)

# Stats
print(router.get_stats())
```

## Integration with EII

SmartRouter is the infrastructure layer. It replaces ResilientLLM's simple
failover with competency-based routing:

```python
# In EII agents:
from smartrouter import SmartRouter, TaskType

router = SmartRouter()

# DiagnosticAgent uses deep reasoning
result = await router.route(diagnosis_prompt, force_type=TaskType.DEEP_REASONING)

# EvaluatorAgent uses fast validation
result = await router.route(eval_prompt, force_type=TaskType.VALIDATION)

# IntelAgent SourceCollector uses iteration
result = await router.route(collect_prompt, force_type=TaskType.ITERATION)
```

## Roadmap

- **Phase 1** ✅ Rules Engine (keyword-based classification)
- **Phase 2** Smart Classification (Cerebras LLM as classifier)
- **Phase 3** Adaptive Routing (learn from historical performance)

---

Part of [EII — ERP Incident Intelligence](https://github.com/edson-aiops/eii-erp-incident-intelligence)
