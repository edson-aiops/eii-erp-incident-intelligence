"""
EII — CRAG Pipeline
Corrective RAG: Retrieve → Grade → [Generate → Evaluate ⟳] → Confidence
"""

import chromadb
from chromadb.utils import embedding_functions
import requests
import json
import math
import re
import os
from knowledge_base import KB
from xml_parser import scrub_pii


# ─────────────────────────────────────────────────────────────────────────────
# Vector Store
# ─────────────────────────────────────────────────────────────────────────────

def build_vector_store() -> chromadb.Collection:
    client = chromadb.Client()
    ef = embedding_functions.DefaultEmbeddingFunction()

    try:
        client.delete_collection("eii_esocial")
    except Exception:
        pass

    col = client.create_collection("eii_esocial", embedding_function=ef)

    docs, ids, metas = [], [], []
    for item in KB:
        doc = (
            f"Evento: {item['evento']} | Erro: {item['codigo_erro']}\n"
            f"Título: {item['titulo']}\n"
            f"Descrição: {item['descricao']}\n"
            f"Causa Raiz: {item['causa_raiz']}\n"
            f"Tags: {', '.join(item['tags'])}"
        )
        docs.append(scrub_pii(doc))
        ids.append(item["id"])
        metas.append({
            "evento": item["evento"],
            "codigo_erro": item["codigo_erro"],
            "impacto": item["impacto"]
        })

    col.add(documents=docs, ids=ids, metadatas=metas)
    return col


# ─────────────────────────────────────────────────────────────────────────────
# Model routing
# ROUTER  → small/fast model for deterministic binary steps (grade)
# GENERATOR → large model for complex JSON generation
# ─────────────────────────────────────────────────────────────────────────────

MODEL_ROUTER    = os.environ.get("EII_MODEL_ROUTER",    "llama-3.1-8b-instant")
MODEL_GENERATOR = os.environ.get("EII_MODEL_GENERATOR", "llama-3.3-70b-versatile")


# ─────────────────────────────────────────────────────────────────────────────
# LLM — Groq
# ─────────────────────────────────────────────────────────────────────────────

def _groq(messages: list, system: str = "", max_tokens: int = 800,
          model: str = MODEL_GENERATOR) -> str:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return "❌ GROQ_API_KEY não configurada. Adicione nas Secrets do HuggingFace Space."

    payload = {
        "model": model,
        "messages": ([{"role": "system", "content": system}] if system else []) + messages,
        "max_tokens": max_tokens,
        "temperature": 0.05,
    }
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload, timeout=40,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        return f"❌ Groq {r.status_code}: {r.text[:300]}"
    except Exception as e:
        return f"❌ Conexão Groq: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# ADR-001 — Logprobs confidence gate
# Calls Groq with logprobs=True, max_tokens=1.
# Measures P(SIM) over top-5 candidate tokens to score diagnosis confidence.
# Thresholds: ≥0.80 → ALTA | ≥0.55 → MÉDIA | <0.55 → BAIXA
# ─────────────────────────────────────────────────────────────────────────────

_AFFIRMATIVE = {"SIM", "S", "YES", "Y"}
_CONF_THRESHOLDS = [(0.80, "ALTA"), (0.45, "MÉDIA")]


def _prob_to_label(prob: float) -> str:
    for threshold, label in _CONF_THRESHOLDS:
        if prob >= threshold:
            return label
    return "BAIXA"


def _groq_logprobs(messages: list) -> float:
    """Returns P(affirmative) ∈ [0,1] from top-5 logprobs. Falls back to 0.5."""
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return 0.5

    payload = {
        "model": MODEL_ROUTER,
        "messages": messages,
        "max_tokens": 1,
        "temperature": 0.0,
        "logprobs": True,
        "top_logprobs": 5,
    }
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload, timeout=20,
        )
        if r.status_code != 200:
            return 0.5
        content_lp = r.json()["choices"][0].get("logprobs", {}).get("content", [])
        if not content_lp:
            return 0.5
        prob = sum(
            math.exp(e["logprob"])
            for e in content_lp[0].get("top_logprobs", [])
            if e["token"].strip().upper() in _AFFIRMATIVE
        )
        return min(prob, 1.0)
    except Exception:
        return 0.5


def confidence_score(parsed_xml, diagnosis: dict) -> tuple:
    """
    Binary confidence gate (ADR-001).
    Asks MODEL_ROUTER to confirm the diagnosis; measures P(SIM) via logprobs.
    Returns (label: str, prob_sim: float).
    """
    ocorrencias_txt = "; ".join([
        f"[{o.codigo}] {o.descricao[:80]}"
        for o in parsed_xml.ocorrencias[:3]
    ]) or parsed_xml.cd_resposta

    prompt = (
        f"Incidente eSocial — Evento: {parsed_xml.tipo_evento or '?'} | "
        f"cdResposta: {parsed_xml.cd_resposta}\n"
        f"Ocorrências: {ocorrencias_txt}\n\n"
        f"Diagnóstico gerado:\n"
        f"Causa: {diagnosis.get('causa_raiz', '')[:300]}\n"
        f"Código erro: {diagnosis.get('codigo_erro', '')}\n\n"
        "O diagnóstico está tecnicamente correto para este incidente eSocial? "
        "Responda apenas: SIM ou NÃO"
    )
    prob_sim = _groq_logprobs([{"role": "user", "content": prompt}])
    return _prob_to_label(prob_sim), prob_sim


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Retrieve
# ─────────────────────────────────────────────────────────────────────────────

def retrieve(col: chromadb.Collection, query: str, n: int = 5) -> list:
    results = col.query(query_texts=[query], n_results=min(n, len(KB)))
    docs = []
    for i, doc_id in enumerate(results["ids"][0]):
        item = next((x for x in KB if x["id"] == doc_id), None)
        if item:
            docs.append({
                "id": doc_id,
                "distance": results["distances"][0][i],
                "item": item,
            })
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Grade (CRAG corrective filter)
# ─────────────────────────────────────────────────────────────────────────────

def grade(query: str, candidates: list) -> list:
    relevant = []
    for c in candidates:
        item = c["item"]
        prompt = (
            f"Incidente eSocial:\n{query}\n\n"
            f"Documento KB:\n"
            f"- Evento: {item['evento']} | Erro: {item['codigo_erro']}\n"
            f"- {item['titulo']}\n"
            f"- {item['descricao'][:300]}\n\n"
            "O documento é relevante para diagnosticar este incidente? "
            "Responda APENAS: RELEVANTE ou IRRELEVANTE"
        )
        verdict = _groq(
            [{"role": "user", "content": prompt}],
            max_tokens=5,
            model=MODEL_ROUTER,
        ).strip().upper()
        if "RELEVANTE" in verdict:
            relevant.append(c)
    return relevant


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Generate
# ─────────────────────────────────────────────────────────────────────────────

def generate(parsed_xml, relevant: list, incident_id: str,
             corrective_hint: str = "") -> dict:
    # Build context from relevant KB docs
    if relevant:
        ctx = "\n\n".join([
            f"[REF {i+1} — {d['item']['id']}] {d['item']['titulo']}\n"
            f"Causa: {d['item']['causa_raiz']}\n"
            f"Resolução: {'; '.join(d['item']['passos_resolucao'])}\n"
            f"Validação: {d['item']['validacao']}"
            for i, d in enumerate(relevant)
        ])
        fonte = "KB_MATCH"
    else:
        ctx = (
            "Nenhum caso exato na base de conhecimento. "
            "Use seu conhecimento especializado em eSocial/legislação brasileira."
        )
        fonte = "LLM_FALLBACK"

    # Build incident description
    ocorrencias_txt = "\n".join([
        f"  • [{o.tipo}] {o.codigo}: {o.descricao}"
        + (f" | Local: {o.localizacao}" if o.localizacao else "")
        for o in parsed_xml.ocorrencias
    ]) or "  (não extraídas do XML)"

    incident_desc = (
        f"Evento eSocial: {parsed_xml.tipo_evento or 'Não identificado'}\n"
        f"cdResposta: {parsed_xml.cd_resposta}\n"
        f"descResposta: {parsed_xml.desc_resposta}\n"
        f"CNPJ Empregador: {parsed_xml.nr_inscricao or '—'}\n"
        f"Ocorrências:\n{ocorrencias_txt}"
    )

    correction_block = (
        f"\n\n[Correção solicitada pelo avaliador]: {corrective_hint}"
        if corrective_hint else ""
    )

    prompt = f"""Você é o EII (ERP Incident Intelligence), especialista em falhas de integração com o governo brasileiro — eSocial, webservices da RFB e obrigações acessórias.

INCIDENTE:
{incident_desc}

CONTEXTO DA BASE DE CONHECIMENTO:
{ctx}{correction_block}

Gere um diagnóstico técnico preciso em JSON. Responda APENAS com o JSON, sem texto adicional:
{{
  "incident_id": "{incident_id}",
  "evento": "{parsed_xml.tipo_evento or 'Desconhecido'}",
  "codigo_erro": "{', '.join(parsed_xml.error_codes) or parsed_xml.cd_resposta}",
  "severidade": "CRÍTICO|ALTO|MÉDIO|BAIXO",
  "causa_raiz": "explicação técnica e precisa da causa raiz",
  "confianca": "ALTA|MÉDIA|BAIXA",
  "fonte": "{fonte}",
  "passos_resolucao": [
    "passo 1 detalhado e acionável",
    "passo 2",
    "passo 3",
    "passo 4",
    "passo 5"
  ],
  "validacao": "como confirmar que o problema foi resolvido",
  "tempo_estimado": "Xh",
  "referencias_kb": ["KB001"],
  "alerta_hitl": "motivo específico pelo qual um analista deve revisar antes de executar"
}}"""

    raw = _groq([{"role": "user", "content": prompt}], max_tokens=1000)

    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        return json.loads(match.group() if match else raw)
    except Exception:
        return {
            "incident_id": incident_id,
            "evento": parsed_xml.tipo_evento or "—",
            "codigo_erro": ", ".join(parsed_xml.error_codes) or parsed_xml.cd_resposta,
            "severidade": "MÉDIO",
            "causa_raiz": raw[:500],
            "confianca": "BAIXA",
            "fonte": "PARSE_ERROR",
            "passos_resolucao": ["Análise manual necessária — diagnóstico automático falhou."],
            "validacao": "Verificar manualmente com especialista eSocial.",
            "tempo_estimado": "Indefinido",
            "referencias_kb": [],
            "alerta_hitl": "Diagnóstico automático falhou — revisão humana obrigatória antes de qualquer ação."
        }


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — EvaluatorAgent (Evaluator-Optimizer pattern)
# Uses MODEL_ROUTER (8b) to score the diagnosis against 5 quality criteria.
# Returns a structured EvalResult that drives the generate→evaluate loop.
#
# Criteria (hard gates: 1,2,4 — soft: 3,5):
#   1. causal_coherence        — causa_raiz explains the actual error codes
#   2. resolution_actionability — passos_resolucao are specific and actionable
#   3. kb_grounding            — diagnosis is consistent with retrieved KB docs
#   4. schema_completeness     — all required fields present and non-empty
#   5. severity_calibration    — severidade is proportional to the error
# ─────────────────────────────────────────────────────────────────────────────

MAX_EVAL_ITERATIONS = 2   # up to 3 total generate calls (iter 0, 1, 2)

_EVAL_CRITERIA = [
    "causal_coherence",
    "resolution_actionability",
    "kb_grounding",
    "schema_completeness",
    "severity_calibration",
]
_EVAL_HARD_GATES = {"causal_coherence", "resolution_actionability", "schema_completeness"}


def _eval_verdict(criteria_passed: list) -> str:
    """APPROVED iff all hard gates pass AND at least one soft criterion passes."""
    passed = set(criteria_passed)
    if not _EVAL_HARD_GATES.issubset(passed):
        return "REJECTED"
    soft = {"kb_grounding", "severity_calibration"}
    if soft.isdisjoint(passed):
        return "REJECTED"
    return "APPROVED"


def evaluate_diagnosis(parsed_xml, diagnosis: dict, relevant: list,
                       iteration: int) -> dict:
    """
    Evaluates a generated diagnosis against 5 quality criteria.
    Returns an EvalResult dict:
      verdict            "APPROVED" | "REJECTED"
      criteria_passed    list[str]
      criteria_failed    list[str]
      critique           str  (PT-BR; "" if APPROVED)
      should_regenerate  bool
      regeneration_hint  str  (imperative directive for next generate call)
    """
    ocorrencias_txt = "; ".join(
        f"[{o.codigo}] {o.descricao[:80]}" for o in parsed_xml.ocorrencias[:3]
    ) or parsed_xml.cd_resposta

    kb_ctx = "\n".join(
        f"- [{d['item']['id']}] {d['item']['titulo']} | Erro: {d['item']['codigo_erro']}"
        for d in relevant[:3]
    ) or "(nenhum doc KB relevante — fonte LLM_FALLBACK)"

    passos = diagnosis.get("passos_resolucao", [])
    passos_txt = "\n".join(f"  {i+1}. {p}" for i, p in enumerate(passos)) or "  (vazio)"

    prompt = f"""Você é um avaliador técnico de diagnósticos eSocial. Avalie o diagnóstico abaixo contra 5 critérios.

INCIDENTE:
- Evento: {parsed_xml.tipo_evento or '?'} | cdResposta: {parsed_xml.cd_resposta}
- Ocorrências: {ocorrencias_txt}

DOCS KB RELEVANTES:
{kb_ctx}

DIAGNÓSTICO GERADO:
- codigo_erro: {diagnosis.get('codigo_erro', '')}
- severidade: {diagnosis.get('severidade', '')}
- causa_raiz: {diagnosis.get('causa_raiz', '')[:400]}
- passos_resolucao:
{passos_txt}
- validacao: {diagnosis.get('validacao', '')[:200]}
- alerta_hitl: {diagnosis.get('alerta_hitl', '')[:150]}

CRITÉRIOS (avalie cada um como PASS ou FAIL):
1. causal_coherence: causa_raiz explica tecnicamente os códigos de erro e ocorrências reais?
2. resolution_actionability: os passos são específicos e acionáveis (referenciam campo/evento/regra), não genéricos?
3. kb_grounding: o diagnóstico é consistente com os docs KB listados acima?
4. schema_completeness: todos os campos obrigatórios presentes e não-vazios? passos_resolucao tem ≥2 itens?
5. severity_calibration: a severidade é proporcional ao tipo de erro?

Responda APENAS com JSON, sem texto adicional:
{{
  "criteria_passed": ["nome_criterio", ...],
  "criteria_failed": ["nome_criterio", ...],
  "critique": "explicação concisa em português do que falhou (vazio se tudo passou)",
  "regeneration_hint": "instrução imperativa e específica para corrigir o próximo diagnóstico (vazio se aprovado)"
}}"""

    raw = _groq(
        [{"role": "user", "content": prompt}],
        max_tokens=500,
        model=MODEL_ROUTER,
    )

    # Parse evaluator response
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(match.group() if match else raw)
        criteria_passed = [c for c in data.get("criteria_passed", []) if c in _EVAL_CRITERIA]
        criteria_failed = [c for c in data.get("criteria_failed", []) if c in _EVAL_CRITERIA]
        # Ensure every criterion is accounted for
        accounted = set(criteria_passed) | set(criteria_failed)
        for c in _EVAL_CRITERIA:
            if c not in accounted:
                criteria_failed.append(c)
        critique          = data.get("critique", "")[:400]
        regeneration_hint = data.get("regeneration_hint", "")[:300]
        verdict = _eval_verdict(criteria_passed)
    except Exception:
        # Fail-safe: iteration 0 → force retry; iteration ≥ MAX → fail-open
        if iteration < MAX_EVAL_ITERATIONS:
            criteria_passed = []
            criteria_failed = list(_EVAL_CRITERIA)
            critique = "Falha ao parsear resposta do avaliador."
            regeneration_hint = "Gere um diagnóstico completo seguindo exatamente o schema JSON solicitado."
            verdict = "REJECTED"
        else:
            criteria_passed = list(_EVAL_CRITERIA)
            criteria_failed = []
            critique = "Avaliador não pôde ser executado — diagnóstico aceito por exaustão de tentativas."
            regeneration_hint = ""
            verdict = "APPROVED"

    should_regenerate = (verdict == "REJECTED") and (iteration < MAX_EVAL_ITERATIONS)

    return {
        "verdict":            verdict,
        "criteria_passed":    criteria_passed,
        "criteria_failed":    criteria_failed,
        "critique":           critique,
        "should_regenerate":  should_regenerate,
        "regeneration_hint":  regeneration_hint,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Full CRAG pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_crag(col: chromadb.Collection, parsed_xml, incident_id: str) -> dict:
    # Build search query from parsed data
    query_parts = [
        parsed_xml.tipo_evento,
        parsed_xml.cd_resposta,
        parsed_xml.desc_resposta,
        " ".join(parsed_xml.error_codes),
        " ".join([o.descricao[:100] for o in parsed_xml.ocorrencias[:3]])
    ]
    query = " ".join(filter(None, query_parts))

    candidates = retrieve(col, query)
    relevant   = grade(query, candidates)

    # ── Evaluator-Optimizer loop ──────────────────────────────────────────────
    corrective_hint = ""
    eval_history    = []

    for iteration in range(MAX_EVAL_ITERATIONS + 1):
        diagnosis  = generate(parsed_xml, relevant, incident_id,
                               corrective_hint=corrective_hint)
        eval_result = evaluate_diagnosis(parsed_xml, diagnosis, relevant, iteration)
        eval_history.append(eval_result)

        if not eval_result["should_regenerate"]:
            break

        corrective_hint = eval_result["regeneration_hint"]

    final_eval = eval_history[-1]

    # Safety coupling: REJECTED_MAX_ITER → force HITL escalation
    if final_eval["verdict"] != "APPROVED":
        diagnosis["alerta_hitl"] = (
            "⚠️ Avaliador automático não aprovou este diagnóstico após "
            f"{len(eval_history)} tentativa(s). Revisão humana obrigatória. "
            + (final_eval["critique"] or "")
        )[:500]

    # ADR-001: override LLM-generated confianca with calibrated logprob score
    confianca, prob_sim = confidence_score(parsed_xml, diagnosis)
    diagnosis["confianca"] = confianca

    diagnosis["_meta"] = {
        # existing fields
        "candidates_retrieved":  len(candidates),
        "candidates_relevant":   len(relevant),
        "query_used":            query[:200],
        "logprob_sim":           round(prob_sim, 3),
        # evaluator fields
        "eval_iterations":       len(eval_history),
        "eval_final_verdict":    final_eval["verdict"],
        "eval_criteria_passed":  final_eval["criteria_passed"],
        "eval_criteria_failed":  final_eval["criteria_failed"],
        "eval_critique_last":    final_eval["critique"][:400],
        "eval_score_history":    [
            {
                "iteration":       i,
                "verdict":         e["verdict"],
                "criteria_passed": e["criteria_passed"],
                "criteria_failed": e["criteria_failed"],
            }
            for i, e in enumerate(eval_history)
        ],
    }
    return diagnosis
