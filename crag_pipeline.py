"""
EII — CRAG Pipeline
Corrective RAG: Retrieve → Grade → Generate
"""

import chromadb
from chromadb.utils import embedding_functions
import requests
import json
import re
import os
from knowledge_base import KB


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
        docs.append(doc)
        ids.append(item["id"])
        metas.append({
            "evento": item["evento"],
            "codigo_erro": item["codigo_erro"],
            "impacto": item["impacto"]
        })

    col.add(documents=docs, ids=ids, metadatas=metas)
    return col


# ─────────────────────────────────────────────────────────────────────────────
# LLM — Groq
# ─────────────────────────────────────────────────────────────────────────────

def _groq(messages: list, system: str = "", max_tokens: int = 800) -> str:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return "❌ GROQ_API_KEY não configurada. Adicione nas Secrets do HuggingFace Space."

    payload = {
        "model": "llama-3.3-70b-versatile",
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
            max_tokens=5
        ).strip().upper()
        if "RELEVANTE" in verdict:
            relevant.append(c)
    return relevant


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Generate
# ─────────────────────────────────────────────────────────────────────────────

def generate(parsed_xml, relevant: list, incident_id: str) -> dict:
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

    prompt = f"""Você é o EII (ERP Incident Intelligence), especialista em falhas de integração com o governo brasileiro — eSocial, webservices da RFB e obrigações acessórias.

INCIDENTE:
{incident_desc}

CONTEXTO DA BASE DE CONHECIMENTO:
{ctx}

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
    diagnosis  = generate(parsed_xml, relevant, incident_id)

    diagnosis["_meta"] = {
        "candidates_retrieved": len(candidates),
        "candidates_relevant": len(relevant),
        "query_used": query[:200],
    }
    return diagnosis
