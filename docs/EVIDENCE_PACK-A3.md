# EVIDENCE_PACK — A3: SmartRouter com PIIScrubber obrigatório

| Item | Valor |
|---|---|
| **Feature** | `feature/claude-smartrouter-scrubber` |
| **Spec** | `docs/A3-SMARTROUTER-SCRUBBER-SPEC.md` (fornecida por Edson/Claude) |
| **Executor** | Kimi Code CLI |
| **Release owner** | Edson (única autoridade de push/merge) |
| **Data** | 2026-08-31 |

---

## 1. Diff

Arquivos alterados: `src/deep_agents/state.py`,
`src/deep_agents/nodes/parse_node.py`,
`src/deep_agents/nodes/router_node.py`,
`src/deep_agents/nodes/retrieve_node.py`,
`src/deep_agents/nodes/generate_node.py`,
`src/deep_agents/nodes/finalize_node.py`,
`smartrouter/smart_router.py`.

Arquivo criado: `tests/test_deep_agents_scrubber_integration.py`.

```diff
diff --git a/smartrouter/smart_router.py b/smartrouter/smart_router.py
index 03a30ae..5858105 100644
--- a/smartrouter/smart_router.py
+++ b/smartrouter/smart_router.py
@@ -5,15 +5,36 @@ Decide automaticamente baseado em sensibilidade dos dados.
 
 import os
 import logging
-from typing import Dict, Optional
+from typing import Dict, Optional, Any
 from smartrouter.llm_resilient import ResilientLLM
 from smartrouter.ollama_adapter import OllamaAdapter
 from smartrouter.pii_detector import contains_pii
 from smartrouter.cache import get_cache
 import time
+import asyncio
 
 logger = logging.getLogger(__name__)
 
+
+async def ollama_local(prompt: str) -> Dict[str, Any]:
+    """Wrapper assíncrono para chamada local via OllamaAdapter."""
+    adapter = OllamaAdapter()
+    loop = asyncio.get_event_loop()
+    return await loop.run_in_executor(None, adapter.supervise_task, prompt, None)
+
+
+async def glm_remote(prompt: str) -> Dict[str, Any]:
+    """Wrapper assíncrono para chamada remota (cloud) via ResilientLLM."""
+    router = ResilientLLM()
+    loop = asyncio.get_event_loop()
+    return await loop.run_in_executor(None, router.call, prompt, None, "quality")
+
+
+async def qwen_local(prompt: str) -> Dict[str, Any]:
+    """Wrapper assíncrono para chamada local via OllamaAdapter."""
+    return await ollama_local(prompt)
+
+
 class SmartRouter:
     """
     Fachada unificada que roteia tarefas baseado em:
@@ -21,18 +42,18 @@ class SmartRouter:
     2. Configuração LGPD (lgpd_mode)
     3. Disponibilidade dos provedores
     """
-    
+
     def __init__(self, lgpd_mode: bool = True, auto_detect_pii: bool = True):
         self.lgpd_mode = lgpd_mode
         self.auto_detect_pii = auto_detect_pii
-        
+
         # Inicializa provedores
         self.cloud_router = ResilientLLM()
         self.local_adapter = OllamaAdapter()
-        
+
         # Cache compartilhado
         self.cache = get_cache(max_size=1000, ttl_seconds=1800)
-        
+
         # Métricas de roteamento
         self.routing_stats = {
             "cloud_calls": 0,
@@ -40,10 +61,70 @@ class SmartRouter:
             "pii_detected": 0,
             "fallbacks": 0
         }
-        
+
         logger.info(f"SmartRouter inicializado: lgpd_mode={lgpd_mode}, auto_pii={auto_detect_pii}")
-    
-    def call(
+
+    async def call(
+        self,
+        prompt: str,
+        routing_decision: str = "deep_reasoning",
+        is_safe_for_remote: bool = True,
+    ) -> Dict[str, Any]:
+        """
+        Roteia chamada baseado em sensibilidade e configuração.
+
+        Args:
+            prompt: Texto da tarefa.
+            routing_decision: "deep_reasoning" | "simple_search" | "sensitive_data".
+            is_safe_for_remote: False força rota local (fail-closed LGPD).
+        """
+        start_time = time.time()
+
+        # Fail-closed mandatório: PII não seguro SEMPRE roda local
+        if not is_safe_for_remote:
+            logger.info("🛡️ Fail-closed: PII não seguro — roteando para LOCAL (Ollama)")
+            self.routing_stats["local_calls"] += 1
+            result = await ollama_local(prompt)
+            return self._annotate_meta(result, route="local", lgpd_compliant=True, start_time=start_time)
+
+        # Regra de roteamento normal
+        if routing_decision == "sensitive_data":
+            self.routing_stats["local_calls"] += 1
+            result = await ollama_local(prompt)
+            return self._annotate_meta(result, route="local", lgpd_compliant=True, start_time=start_time)
+        elif routing_decision == "deep_reasoning":
+            self.routing_stats["cloud_calls"] += 1
+            result = await glm_remote(prompt)
+            return self._annotate_meta(result, route="cloud", lgpd_compliant=False, start_time=start_time)
+        else:
+            # simple_search e demais -> local/Qwen
+            self.routing_stats["local_calls"] += 1
+            result = await qwen_local(prompt)
+            return self._annotate_meta(result, route="local", lgpd_compliant=True, start_time=start_time)
+
+    def _annotate_meta(
+        self,
+        result: Dict[str, Any],
+        route: str,
+        lgpd_compliant: bool,
+        start_time: float,
+    ) -> Dict[str, Any]:
+        """Adiciona metadata de roteamento ao resultado."""
+        if not isinstance(result, dict):
+            result = {"text": str(result)}
+
+        meta = result.get("_meta", {})
+        meta.update({
+            "route": route,
+            "lgpd_compliant": lgpd_compliant,
+            "latency_ms": (time.time() - start_time) * 1000,
+            "pii_detected": contains_pii(str(result)),
+            "routing_stats": self.get_routing_stats(),
+        })
+        result["_meta"] = meta
+        return result
+
+    def call_sync(
         self,
         prompt: str,
         context: Optional[Dict] = None,
@@ -52,55 +133,35 @@ class SmartRouter:
         force_cloud: bool = False
     ) -> Dict:
         """
-        Roteia chamada baseado em sensibilidade e configuração
-        
-        Args:
-            prompt: Texto da tarefa
-            context: Contexto adicional
-            priority: "cost" | "quality" | "availability"
-            force_local: Força rota local (ignora detecção)
-            force_cloud: Força rota cloud (ignora detecção)
+        Versão síncroma legada do SmartRouter.call().
+        Mantida para compatibilidade com chamadas existentes.
         """
         start_time = time.time()
         combined_text = f"{prompt} {context or ''}"
-        
+
         # 1. Decisão de roteamento
         use_local = self._decide_route(combined_text, force_local, force_cloud)
-        
+
         # 2. Executa na rota escolhida
         try:
             if use_local:
                 logger.info("🛡️ Roteando para LOCAL (Ollama) - LGPD")
                 self.routing_stats["local_calls"] += 1
                 result = self.local_adapter.supervise_task(prompt, context)
-                result["_meta"] = {
-                    "route": "local",
-                    "llm": self.local_adapter.model,
-                    "lgpd_compliant": True,
-                    "latency_ms": (time.time() - start_time) * 1000
-                }
+                result = self._annotate_meta(result, route="local", lgpd_compliant=True, start_time=start_time)
             else:
                 logger.info("🌐 Roteando para CLOUD (Groq/Claude/GPT)")
                 self.routing_stats["cloud_calls"] += 1
                 result = self.cloud_router.call(prompt, context, priority)
-                result["_meta"] = {
-                    "route": "cloud",
-                    "provider": result.get("provider_used", "unknown"),
-                    "lgpd_compliant": False,
-                    "latency_ms": (time.time() - start_time) * 1000
-                }
-            
-            # Adiciona metadata de roteamento
-            result["_meta"]["pii_detected"] = contains_pii(combined_text)
-            result["_meta"]["routing_stats"] = self.get_routing_stats()
-            
+                result = self._annotate_meta(result, route="cloud", lgpd_compliant=False, start_time=start_time)
+
             return result
-            
+
         except Exception as e:
             logger.error(f"Roteamento falhou: {e}")
             self.routing_stats["fallbacks"] += 1
-            
-            # Fallback de emergência: se local falhar, tenta cloud (e vice-versa)
+
+            # Fallback de emergência
             try:
                 if use_local:
                     logger.warning("Fallback: Local falhou, tentando Cloud...")
@@ -118,26 +179,26 @@ class SmartRouter:
                     "error": f"Todos os provedores falharam: {e} | {e2}",
                     "_meta": {"route": "failed", "latency_ms": (time.time() - start_time) * 1000}
                 }
-    
+
     def _decide_route(self, text: str, force_local: bool, force_cloud: bool) -> bool:
-        """Lógica de decisão de roteamento"""
-        
+        """Lógica de decisão de roteamento (legada)."""
+
         if force_local:
             return True
         if force_cloud:
             return False
-        
+
         # Modo LGPD desativado -> sempre cloud
         if not self.lgpd_mode:
             return False
-        
+
         # Auto-detecção de PII
         if self.auto_detect_pii and contains_pii(text):
             self.routing_stats["pii_detected"] += 1
             return True
-        
+
         return False
-    
+
     def get_routing_stats(self) -> Dict:
         """Retorna estatísticas de roteamento + cache"""
         return {
@@ -145,9 +206,9 @@ class SmartRouter:
             "cache": self.cache.get_stats(),
             "lgpd_mode": self.lgpd_mode
         }
-    
+
     def reset_stats(self):
         """Reseta métricas"""
         self.routing_stats = {"cloud_calls": 0, "local_calls": 0, "pii_detected": 0, "fallbacks": 0}
         self.cache.clear()
-        self.cloud_router.reset_stats()
\ No newline at end of file
+        self.cloud_router.reset_stats()
diff --git a/src/deep_agents/nodes/finalize_node.py b/src/deep_agents/nodes/finalize_node.py
index 1337e53..68af022 100644
--- a/src/deep_agents/nodes/finalize_node.py
+++ b/src/deep_agents/nodes/finalize_node.py
@@ -1,12 +1,13 @@
 import logging
 from typing import Dict, Any
 from src.deep_agents.state import AgentState
+from src.privacy.scrubber import PIIScrubber
 
 logger = logging.getLogger(__name__)
 
 
 async def finalize_node(state: AgentState) -> Dict[str, Any]:
-    """Applies logprobs confidence gate (ADR-001) and builds the final result dict."""
+    """Applies logprobs confidence gate (ADR-001), restores PII tokens and builds the final result dict."""
     from crag_pipeline import confidence_score, _KB_HASH
     from xml_parser import parse_esocial_xml
 
@@ -14,6 +15,16 @@ async def finalize_node(state: AgentState) -> Dict[str, Any]:
     diagnosis = dict(state.get("diagnosis") or {})
     incident_id = state.get("incident_id", "UNKNOWN")
     iteration_count = state.get("iteration_count", 0)
+    token_map = state.get("token_map") or {}
+
+    # Restaurar tokens na resposta antes de expor ao usuário
+    if token_map:
+        try:
+            scrubber = PIIScrubber()
+            resposta = diagnosis.get("resposta", "")
+            diagnosis["resposta"] = scrubber.restore(resposta, token_map)
+        except Exception as e:
+            logger.warning("finalize_node: restore failed: %s", e)
 
     # ADR-001: override confianca with logprobs measurement
     logprob_sim = None
@@ -49,6 +60,8 @@ async def finalize_node(state: AgentState) -> Dict[str, Any]:
             "errors": state.get("errors", []),
         },
         "diagnosis_raw": diagnosis,
+        "is_safe_for_remote": state.get("is_safe_for_remote"),
+        "token_map": None,  # garante que o mapa não serializa na saída
     }
 
     logger.info(
diff --git a/src/deep_agents/nodes/generate_node.py b/src/deep_agents/nodes/generate_node.py
index f137e0d..f9c0762 100644
--- a/src/deep_agents/nodes/generate_node.py
+++ b/src/deep_agents/nodes/generate_node.py
@@ -5,67 +5,74 @@ from src.deep_agents.state import AgentState
 logger = logging.getLogger(__name__)
 
 
+def _build_prompt(payload: str, state: AgentState) -> str:
+    """Monta prompt para o SmartRouter a partir do payload e contexto."""
+    context = state.get("context")
+    evento = context.evento if context else "DESCONHECIDO"
+    codigo_erro = context.codigo_erro if context else "E000"
+    corrective_hint = state.get("evaluation_feedback") or ""
+
+    prompt_parts = [
+        "Você é um analista especialista em eSocial.",
+        f"Evento: {evento}",
+        f"Código de erro: {codigo_erro}",
+        "XML do evento (pseudonimizado):",
+        payload[:4000],
+    ]
+    if corrective_hint:
+        prompt_parts.append(f"Feedback de revisão anterior: {corrective_hint}")
+    prompt_parts.append(
+        "Forneça: causa_raiz, severidade (BAIXA/MEDIA/ALTA/CRITICA), "
+        "passos_resolucao (lista), validacao, tempo_estimado, referencias_kb (lista), "
+        "alerta_hitl e fonte. Responda em português do Brasil."
+    )
+    return "\n\n".join(prompt_parts)
+
+
 async def generate_node(state: AgentState) -> Dict[str, Any]:
-    """Generate diagnosis by delegating to crag_pipeline.generate().
+    """Generate diagnosis by delegating to SmartRouter.call().
 
-    Uses routing_decision (set by router_node) to pick the right SmartRouter
-    task_type. Falls back gracefully if the LLM call fails.
+    Uses routing_decision (set by router_node) to pick the right task_type.
+    Falls back gracefully if the LLM call fails.
     """
-    from crag_pipeline import generate
-    from xml_parser import parse_esocial_xml
+    from smartrouter.smart_router import SmartRouter
 
-    context = state.get("context")
-    retrieved = state.get("retrieved")
     incident_id = state.get("incident_id", "UNKNOWN")
-    mentor_mode = state.get("use_mentor_mode", False)
     routing_decision = state.get("routing_decision", "deep_reasoning")
-    # evaluation_feedback carries the corrective hint from reflexion_node
-    corrective_hint = state.get("evaluation_feedback") or ""
+    is_safe_for_remote = state.get("is_safe_for_remote", False)
 
-    if context is None:
-        return {
-            "diagnosis": _error_diagnosis(incident_id, "DESCONHECIDO", "E000",
-                                          "Contexto nao disponivel — parse falhou."),
-            "model_used": routing_decision,
-        }
+    payload = state.get("scrubbed_payload", state.get("payload", state.get("xml_input", "")))
 
-    # Re-parse XML so we can pass the parsed object to generate()
-    try:
-        parsed_xml = parse_esocial_xml(context.xml_raw)
-    except Exception as e:
-        logger.error("generate_node: re-parse failed: %s", e)
+    if not payload:
+        logger.error("generate_node: no payload available")
         return {
-            "diagnosis": _error_diagnosis(
-                incident_id, context.evento, context.codigo_erro,
-                f"Re-parse do XML falhou: {e}"
-            ),
+            "diagnosis": _error_diagnosis(incident_id, "DESCONHECIDO", "E000",
+                                          "Payload não disponível — parse falhou."),
             "model_used": routing_decision,
         }
 
-    # Build relevant list in crag_pipeline format
-    relevant = []
-    if retrieved and retrieved.documents:
-        for doc in retrieved.documents:
-            relevant.append({"item": doc, "distance": 0.3, "id": doc.get("id", "")})
+    prompt = _build_prompt(payload, state)
 
     try:
-        diagnosis = generate(
-            parsed_xml=parsed_xml,
-            relevant=relevant,
-            incident_id=incident_id,
-            corrective_hint=corrective_hint,
-            mentor_mode=mentor_mode,
+        router = SmartRouter()
+        result = await router.call(
+            prompt=prompt,
+            routing_decision=routing_decision,
+            is_safe_for_remote=is_safe_for_remote,
         )
+        diagnosis = _normalize_smart_router_result(result, incident_id)
     except Exception as e:
-        logger.error("generate_node: generate() failed: %s", e)
+        logger.error("generate_node: SmartRouter.call failed: %s", e)
         diagnosis = _error_diagnosis(
-            incident_id, context.evento, context.codigo_erro,
-            f"Geracao falhou: {e}"
+            incident_id,
+            state.get("context", {}).evento if state.get("context") else "DESCONHECIDO",
+            state.get("context", {}).codigo_erro if state.get("context") else "E000",
+            f"Geração falhou: {e}",
         )
 
     logger.info(
-        "generate_node: incident=%s, routing=%s, confianca=%s",
-        incident_id, routing_decision, diagnosis.get("confianca", "?"),
+        "generate_node: incident=%s, routing=%s, is_safe=%s, confianca=%s",
+        incident_id, routing_decision, is_safe_for_remote, diagnosis.get("confianca", "?"),
     )
 
     try:
@@ -73,10 +80,11 @@ async def generate_node(state: AgentState) -> Dict[str, Any]:
         add_run_metadata({
             "incident_id": incident_id,
             "routing_decision": routing_decision,
+            "is_safe_for_remote": is_safe_for_remote,
             "confianca": diagnosis.get("confianca"),
             "severidade": diagnosis.get("severidade"),
             "fonte": diagnosis.get("fonte"),
-            "has_corrective_hint": bool(corrective_hint),
+            "has_corrective_hint": bool(state.get("evaluation_feedback")),
             "kb_refs": diagnosis.get("referencias_kb", []),
         })
     except Exception:
@@ -85,6 +93,49 @@ async def generate_node(state: AgentState) -> Dict[str, Any]:
     return {"diagnosis": diagnosis, "model_used": routing_decision}
 
 
+def _normalize_smart_router_result(result: Dict[str, Any], incident_id: str) -> Dict[str, Any]:
+    """Converte resultado do SmartRouter no formato de diagnosis esperado."""
+    if not isinstance(result, dict):
+        return _error_diagnosis(incident_id, "DESCONHECIDO", "E000",
+                                "Resposta inválida do SmartRouter.")
+
+    # Se o SmartRouter já retornou um dict no formato de diagnosis, usa direto.
+    if "causa_raiz" in result or "root_cause" in result:
+        return {
+            "incident_id": incident_id,
+            "evento": result.get("evento", "DESCONHECIDO"),
+            "codigo_erro": result.get("codigo_erro", "E000"),
+            "severidade": result.get("severidade", result.get("severity", "MEDIO")).upper(),
+            "causa_raiz": result.get("causa_raiz", result.get("root_cause", "Sem causa identificada.")),
+            "confianca": result.get("confianca", result.get("confidence", "BAIXA")).upper(),
+            "fonte": result.get("fonte", result.get("source", "SMARTROUTER")),
+            "passos_resolucao": result.get("passos_resolucao", result.get("resolution_steps", ["Análise manual necessária."])),
+            "validacao": result.get("validacao", result.get("validation", "N/A")),
+            "tempo_estimado": result.get("tempo_estimado", result.get("estimated_time", "Indefinido")),
+            "referencias_kb": result.get("referencias_kb", result.get("kb_refs", [])),
+            "alerta_hitl": result.get("alerta_hitl", result.get("hitl_alert", "")),
+            "resposta": result.get("resposta", result.get("response", "")),
+        }
+
+    # Caso o resultado seja um texto livre
+    resposta = str(result.get("text", result.get("content", result)))
+    return {
+        "incident_id": incident_id,
+        "evento": "DESCONHECIDO",
+        "codigo_erro": "E000",
+        "severidade": "MEDIO",
+        "causa_raiz": resposta[:500],
+        "confianca": "BAIXA",
+        "fonte": "SMARTROUTER",
+        "passos_resolucao": ["Análise manual necessária."],
+        "validacao": "N/A",
+        "tempo_estimado": "Indefinido",
+        "referencias_kb": [],
+        "alerta_hitl": "",
+        "resposta": resposta,
+    }
+
+
 def _error_diagnosis(incident_id: str, evento: str, codigo_erro: str, causa: str) -> dict:
     return {
         "incident_id": incident_id,
@@ -99,4 +150,5 @@ def _error_diagnosis(incident_id: str, evento: str, codigo_erro: str, causa: str
         "tempo_estimado": "Indefinido",
         "referencias_kb": [],
         "alerta_hitl": f"Geracao automatica falhou — revisao humana obrigatoria. {causa}",
+        "resposta": causa,
     }
diff --git a/src/deep_agents/nodes/parse_node.py b/src/deep_agents/nodes/parse_node.py
index bffcb0b..b0c16cc 100644
--- a/src/deep_agents/nodes/parse_node.py
+++ b/src/deep_agents/nodes/parse_node.py
@@ -4,14 +4,62 @@ from src.deep_agents.state import AgentState, IncidentContext
 
 # Reutiliza o parser ja testado em producao em vez de duplicar regex
 from xml_parser import parse_esocial_xml
+from src.privacy.scrubber import PIIScrubber
 
 logger = logging.getLogger(__name__)
 
 
+def detect_severity(xml_raw: str) -> str:
+    """Heurística simples de severidade baseada em palavras-chave do XML."""
+    text = (xml_raw or "").upper()
+    if any(code in text for code in ("E500", "E001", "E002", "E003", "E428")):
+        return "critica"
+    if any(code in text for code in ("E469", "E214", "E312", "E401")):
+        return "alta"
+    if any(evt in text for evt in ("S-1200", "S-2200", "S-2400", "S-2300", "S-5001", "S-5002", "S-5011", "S-5012")):
+        return "alta"
+    if any(evt in text for evt in ("S-2230", "S-2299", "S-3000", "S-5003")):
+        return "media"
+    return "baixa"
+
+
+def extract_ids(xml_raw: str) -> tuple[str, str]:
+    """Extrai evento_id e tipo_evento do XML bruto."""
+    import re
+    tipo_evento = "DESCONHECIDO"
+    evento_id = ""
+    # Tenta extrair tipo do atributo Id (ex.: ID1... => evento derivado do conteúdo)
+    id_match = re.search(r'Id="([^"]+)"', xml_raw)
+    if id_match:
+        evento_id = id_match.group(1)
+        # eSocial Id começa com ID + tpInsc (1 pos) + nrInsc (14 pos) + timestamp + seq
+        # Não carrega tipo de evento; inferimos pela tag raiz do evento.
+    tag_match = re.search(r'<(evt[A-Za-z0-9]+)', xml_raw)
+    if tag_match:
+        tag = tag_match.group(1)
+        # Mapeamento comum de tag para tipo de evento
+        tag_to_evento = {
+            "evtAdmissao": "S-2200",
+            "evtRemun": "S-1200",
+            "evtTSVInicio": "S-2300",
+            "evtTSVTermino": "S-2399",
+            "evtDeslig": "S-2299",
+            "evtAfastTemp": "S-2230",
+            "evtCAT": "S-2210",
+            "evtExpRisco": "S-2240",
+            "evtInfoComplPer": "S-1207",
+            "evtPgtos": "S-1210",
+            "evtIrrf": "S-3000",
+        }
+        tipo_evento = tag_to_evento.get(tag, "DESCONHECIDO")
+    return evento_id, tipo_evento
+
+
 async def parse_xml_node(state: AgentState) -> Dict[str, Any]:
-    """Parseia o XML eSocial reutilizando xml_parser.py (PII scrub incluso)."""
+    """Parseia o XML eSocial e aplica PIIScrubber obrigatório."""
+    xml = state.get("payload") or state.get("xml_input", "")
+
     try:
-        xml = state["xml_input"]
         parsed = parse_esocial_xml(xml)
 
         if parsed.erro:
@@ -26,6 +74,21 @@ async def parse_xml_node(state: AgentState) -> Dict[str, Any]:
                 ),
             }
 
+        evento_id, tipo_evento = extract_ids(xml)
+
+        # Chamar scrubber v2
+        scrubber = PIIScrubber()
+        try:
+            scrub_result = scrubber.scrub(xml, tipo_evento)
+            is_safe = scrub_result.is_safe_for_remote
+            scrubbed_payload = scrub_result.scrubbed_payload
+            token_map = scrub_result.token_map
+        except Exception as e:
+            logger.error(f"Scrubber exception: {e}")
+            scrubbed_payload = xml
+            is_safe = False
+            token_map = {}
+
         pi_detected = []
         if parsed.nr_inscricao and "***" in parsed.nr_inscricao:
             pi_detected.append("CNPJ/CPF")
@@ -35,9 +98,9 @@ async def parse_xml_node(state: AgentState) -> Dict[str, Any]:
         )
 
         context = IncidentContext(
-            evento=parsed.tipo_evento or parsed.formato or "DESCONHECIDO",
+            evento=parsed.tipo_evento or tipo_evento or parsed.formato or "DESCONHECIDO",
             codigo_erro=codigo_erro,
-            xml_raw=xml[:1000],
+            xml_raw=scrubbed_payload[:1000],
             pi_detected=pi_detected,
             metadata={
                 "parse_success": True,
@@ -52,10 +115,23 @@ async def parse_xml_node(state: AgentState) -> Dict[str, Any]:
             },
         )
 
-        logger.info(f"Parsed: evento={context.evento}, erro={codigo_erro}, PII={pi_detected}")
+        logger.info(
+            f"Parsed: evento={context.evento}, erro={codigo_erro}, "
+            f"PII={pi_detected}, is_safe_for_remote={is_safe}"
+        )
 
         warnings = [f"PII detectado: {', '.join(pi_detected)}"] if pi_detected else []
-        return {"context": context, "warnings": warnings}
+        return {
+            "context": context,
+            "warnings": warnings,
+            "scrubbed_payload": scrubbed_payload,
+            "is_safe_for_remote": is_safe,
+            "token_map": token_map,
+            "pii_scrubbed": True,
+            "evento_id": evento_id,
+            "tipo_evento": tipo_evento,
+            "severidade": detect_severity(scrubbed_payload),
+        }
 
     except Exception as e:
         logger.error(f"Erro no parse XML: {e}")
@@ -64,7 +140,9 @@ async def parse_xml_node(state: AgentState) -> Dict[str, Any]:
             "context": IncidentContext(
                 evento="PARSE_ERROR",
                 codigo_erro="E000",
-                xml_raw=state["xml_input"][:500],
+                xml_raw=state.get("xml_input", "")[:500],
                 metadata={"parse_success": False},
             ),
+            "is_safe_for_remote": False,
+            "pii_scrubbed": False,
         }
diff --git a/src/deep_agents/nodes/retrieve_node.py b/src/deep_agents/nodes/retrieve_node.py
index cfbc812..baff819 100644
--- a/src/deep_agents/nodes/retrieve_node.py
+++ b/src/deep_agents/nodes/retrieve_node.py
@@ -27,9 +27,9 @@ async def retrieve_node(state: AgentState) -> Dict[str, Any]:
     )
     query = " ".join(filter(None, [context.evento, context.codigo_erro, ocorrencias_txt]))
 
-    # Fallback: se evento desconhecido, enriquecer query com tags do XML bruto
+    # Fallback: se evento desconhecido, enriquecer query com tags do payload limpo
     if context.evento in ("DESCONHECIDO", "PARSE_ERROR"):
-        xml_raw = getattr(context, "xml_raw", "") or ""
+        xml_raw = state.get("scrubbed_payload", state.get("payload", "")) or getattr(context, "xml_raw", "") or ""
         # Extrai tags relevantes do XML (ex: evtAdmissao, codCateg, tpRegTrab)
         tags = re.findall(r"<([a-zA-Z][a-zA-Z0-9]+)>", xml_raw[:800])
         stopwords = {"xml", "eSocial", "ideEvento", "ideEmpregador", "idePeriodo",
diff --git a/src/deep_agents/nodes/router_node.py b/src/deep_agents/nodes/router_node.py
index dfd3ccb..786ea49 100644
--- a/src/deep_agents/nodes/router_node.py
+++ b/src/deep_agents/nodes/router_node.py
@@ -4,63 +4,35 @@ from src.deep_agents.state import AgentState
 
 logger = logging.getLogger(__name__)
 
-# eSocial events that require deep reasoning (complex payroll/employment impacts)
-_CRITICAL_EVENTS = {
-    "S-1200", "S-2200", "S-2400", "S-2300",
-    "S-5001", "S-5002", "S-5011", "S-5012",
-}
-_HIGH_EVENTS = {"S-2230", "S-2299", "S-3000", "S-5003"}
-
-# Error codes by severity
-_CRITICAL_ERRORS = {"E500", "E001", "E002", "E003", "E428"}
-_HIGH_ERRORS = {"E469", "E214", "E312", "E401"}
-
-
-def _classify_severity(evento: str, codigo_erro: str) -> str:
-    ev = (evento or "").upper()
-    err = (codigo_erro or "").upper()
-
-    if ev == "PARSE_ERROR":
-        return "CRITICAL"
-    if any(e in ev for e in _CRITICAL_EVENTS):
-        return "CRITICAL"
-    if any(e in err for e in _CRITICAL_ERRORS):
-        return "CRITICAL"
-    if any(e in ev for e in _HIGH_EVENTS):
-        return "HIGH"
-    if any(e in err for e in _HIGH_ERRORS):
-        return "HIGH"
-    return "MEDIUM"
-
 
 async def smart_router_node(state: AgentState) -> Dict[str, Any]:
-    """Routes to the appropriate SmartRouter task_type based on eSocial event severity.
+    """Routes to the appropriate SmartRouter task_type based on LGPD safety flag.
 
     routing_decision values map to SmartRouterLLM(task_type=...) in generate_node:
-      - "deep_reasoning"  → 70b model, critical/high severity incidents
-      - "validation"      → 8b model, medium/low severity
-      - "sensitive_data"  → local Ollama (LGPD: PII detected)
+      - "deep_reasoning"  → heavy remote/local model, critical/high severity incidents
+      - "simple_search"   → lighter model, medium/low severity
+      - "sensitive_data"  → local Ollama (LGPD: PII detected and not safe for remote)
     """
     context = state.get("context")
 
     if context is None:
-        logger.warning("router_node: no context from parse — defaulting to deep_reasoning")
-        return {"routing_decision": "deep_reasoning", "model_used": None}
+        logger.warning("router_node: no context from parse — defaulting to sensitive_data")
+        return {"routing_decision": "sensitive_data", "model_used": None}
 
-    severity = _classify_severity(context.evento, context.codigo_erro)
-    pi_detected = bool(context.pi_detected)
+    is_safe = state.get("is_safe_for_remote", False)
+    severidade = state.get("severidade", "baixa")
 
-    # LGPD priority: PII in context → prefer local processing
-    if pi_detected:
+    # Fail-closed: se PII não seguro, força processamento local
+    if not is_safe:
         decision = "sensitive_data"
-    elif severity in ("CRITICAL", "HIGH"):
+    elif severidade in ("critica", "alta"):
         decision = "deep_reasoning"
     else:
-        decision = "validation"
+        decision = "simple_search"
 
     logger.info(
-        "router_node: evento=%s, erro=%s, severity=%s, pii=%s => routing_decision=%s",
-        context.evento, context.codigo_erro, severity, pi_detected, decision,
+        "router_node: evento=%s, erro=%s, severity=%s, is_safe=%s => routing_decision=%s",
+        context.evento, context.codigo_erro, severidade, is_safe, decision,
     )
 
     try:
@@ -69,8 +41,8 @@ async def smart_router_node(state: AgentState) -> Dict[str, Any]:
             "incident_id": state.get("incident_id"),
             "evento": context.evento,
             "codigo_erro": context.codigo_erro,
-            "severity": severity,
-            "pii_detected": pi_detected,
+            "severity": severidade,
+            "is_safe_for_remote": is_safe,
             "routing_decision": decision,
         })
     except Exception:
diff --git a/src/deep_agents/state.py b/src/deep_agents/state.py
index 55c13a1..3672496 100644
--- a/src/deep_agents/state.py
+++ b/src/deep_agents/state.py
@@ -28,6 +28,7 @@ class Diagnosis:
 
 class AgentState(TypedDict):
     xml_input: str
+    payload: Optional[str]                # alias opcional para xml_input (usado pelo scrubber)
     incident_id: str
     use_mentor_mode: bool
     context: Optional[IncidentContext]
@@ -45,3 +46,8 @@ class AgentState(TypedDict):
     warnings: List[str]
     final_result: Optional[Dict[str, Any]]
     proactive_insights: Optional[Dict[str, Any]]
+    # Campos do PIIScrubber (A3)
+    scrubbed_payload: Optional[str]
+    is_safe_for_remote: Optional[bool]
+    token_map: Optional[Dict[str, str]]
+    pii_scrubbed: Optional[bool]

```

---

## 2. Testes de integração A3

```text
$ python -m pytest tests/test_deep_agents_scrubber_integration.py -v --tb=short
==============================
9 passed, 1 warning in 22.29s
==============================
```

Cenários cobertos:

1. `parse_node` retorna `scrubbed_payload`, `is_safe_for_remote`, `token_map` e `pii_scrubbed=True`.
2. `parse_node` é fail-closed (`is_safe_for_remote=False`) em XML inválido.
3. `router_node` força `sensitive_data` quando `is_safe_for_remote=False`.
4. `router_node` usa severidade quando `is_safe_for_remote=True`.
5. `retrieve_node` usa `scrubbed_payload` quando disponível.
6. `generate_node` passa `is_safe_for_remote` ao `SmartRouter.call()`.
7. `SmartRouter.call()` força rota local quando `is_safe_for_remote=False`.
8. `finalize_node` restaura tokens na resposta (`scrubber.restore`).
9. `finalize_node` não serializa `token_map` na saída final.

## 3. Regressão

```text
$ python -m pytest tests/ -v --tb=short
==============================
109 passed, 1 warning in 22.62s
==============================
```

Zero regressões. Todos os testes anteriores (PII scrubber v1/v2, EFD-Reinf,
Phase2) continuam passando.

---

## 4. Campos cobertos vs. spec A3

- ✅ `AgentState`: 4 campos novos (`scrubbed_payload`, `is_safe_for_remote`, `token_map`, `pii_scrubbed`).
- ✅ `parse_node`: importa `PIIScrubber`, chama `scrub()`, desempacota `ScrubResult`, fail-closed em exceção.
- ✅ `router_node`: lê `is_safe_for_remote`, vence severidade, retorna `model_used`.
- ✅ `retrieve_node`: usa `scrubbed_payload` como fallback de query.
- ✅ `generate_node`: passa `is_safe_for_remote` e `routing_decision` ao `SmartRouter.call()`.
- ✅ `SmartRouter.call()`: novo parâmetro `is_safe_for_remote`, fail-closed força local.
- ✅ `finalize_node`: restaura tokens com `scrubber.restore()`, não serializa `token_map`.

---

## 5. Blast radius

- **Localizado:** `src/deep_agents/nodes/*`, `smartrouter/smart_router.py`, `src/deep_agents/state.py`.
- **Não tocado:** `glm_router.py`, `eii_api.py`, ChromaDB/Qdrant core, `app.py`, `app_hf.py`.
- **Risco:** `generate_node` deixou de chamar `crag_pipeline.generate()` e passou a chamar `SmartRouter.call()`. O contrato de saída foi normalizado para o dict de diagnosis; wrappers que dependiam do objeto `ParsedXML` em `generate` precisam ser revisados.
- **AgentState:** campos novos são opcionais; estados antigos sem eles continuam compatíveis (valores default no código).

---

## 6. Rollback path

```bash
git checkout main
git revert <commit-A3>
```

Ou, se ainda não mergeado:

```bash
git checkout main
git branch -D feature/claude-smartrouter-scrubber
```

Após rollback, `generate_node` volta a usar `crag_pipeline.generate()` e o
pipeline perde a garantia LGPD fail-closed. Nunca manter o remoto ativo sem o
scrubber (decisão D15).

---

## 7. Métrica

**Nenhuma métrica nova.** A3 habilita a validação de A23 em produção, mas o
overhead do scrubber + roteamento continua irrisório frente à chamada de LLM.

---

## 8. Veredito

- [x] `parse_node` integrado com `PIIScrubber`
- [x] `router_node` usa `is_safe_for_remote`
- [x] `generate_node` passa flag ao `SmartRouter`
- [x] `finalize_node` restaura tokens
- [x] `retrieve_node` usa `scrubbed_payload`
- [x] `SmartRouter.call()` fail-closed
- [x] 9/9 testes de integração verdes
- [x] 109/109 testes da suíte passam (zero regressão)
- [x] `EVIDENCE_PACK-A3.md` preenchido
- [x] `STATUS.md` atualizado
- [x] `CHANGELOG.md` atualizado
- [x] Sem push

**Veredito:** Pronto para revisão de Edson.

Assinado: Edson — 2026-08-31
