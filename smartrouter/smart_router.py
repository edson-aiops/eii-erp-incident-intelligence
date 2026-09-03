"""
SmartRouter Dual-Profile: Roteamento Inteligente Cloud + Local (LGPD)
Decide automaticamente baseado em sensibilidade dos dados.
"""

import os
import logging
from typing import Dict, Optional, Any
from smartrouter.llm_resilient import ResilientLLM
from smartrouter.ollama_adapter import OllamaAdapter
from smartrouter.pii_detector import contains_pii
from smartrouter.cache import get_cache
import time
import asyncio

logger = logging.getLogger(__name__)


async def ollama_local(prompt: str) -> Dict[str, Any]:
    """Wrapper assíncrono para chamada local via OllamaAdapter."""
    adapter = OllamaAdapter()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, adapter.supervise_task, prompt, None)


async def glm_remote(prompt: str) -> Dict[str, Any]:
    """Wrapper assíncrono para chamada remota (cloud) via ResilientLLM."""
    router = ResilientLLM()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, router.call, prompt, None, "quality")


async def qwen_local(prompt: str) -> Dict[str, Any]:
    """Wrapper assíncrono para chamada local via OllamaAdapter."""
    return await ollama_local(prompt)


class SmartRouter:
    """
    Fachada unificada que roteia tarefas baseado em:
    1. Sensibilidade dos dados (PII detection)
    2. Configuração LGPD (lgpd_mode)
    3. Disponibilidade dos provedores
    """

    def __init__(self, lgpd_mode: bool = True, auto_detect_pii: bool = True):
        self.lgpd_mode = lgpd_mode
        self.auto_detect_pii = auto_detect_pii

        # Inicializa provedores
        self.cloud_router = ResilientLLM()
        self.local_adapter = OllamaAdapter()

        # Cache compartilhado
        self.cache = get_cache(max_size=1000, ttl_seconds=1800)

        # Métricas de roteamento
        self.routing_stats = {
            "cloud_calls": 0,
            "local_calls": 0,
            "pii_detected": 0,
            "fallbacks": 0
        }

        logger.info(f"SmartRouter inicializado: lgpd_mode={lgpd_mode}, auto_pii={auto_detect_pii}")

    async def call(
        self,
        prompt: str,
        routing_decision: str = "deep_reasoning",
        is_safe_for_remote: bool = True,
    ) -> Dict[str, Any]:
        """
        Roteia chamada baseado em sensibilidade e configuração.

        Args:
            prompt: Texto da tarefa.
            routing_decision: "deep_reasoning" | "simple_search" | "sensitive_data".
            is_safe_for_remote: False força rota local (fail-closed LGPD).
        """
        start_time = time.time()

        # Fail-closed mandatório: PII não seguro SEMPRE roda local
        if not is_safe_for_remote:
            logger.info("🛡️ Fail-closed: PII não seguro — roteando para LOCAL (Ollama)")
            self.routing_stats["local_calls"] += 1
            result = await ollama_local(prompt)
            return self._annotate_meta(result, route="local", lgpd_compliant=True, start_time=start_time)

        # Regra de roteamento normal
        if routing_decision == "sensitive_data":
            self.routing_stats["local_calls"] += 1
            result = await ollama_local(prompt)
            return self._annotate_meta(result, route="local", lgpd_compliant=True, start_time=start_time)
        elif routing_decision == "deep_reasoning":
            self.routing_stats["cloud_calls"] += 1
            result = await glm_remote(prompt)
            return self._annotate_meta(result, route="cloud", lgpd_compliant=False, start_time=start_time)
        else:
            # simple_search e demais -> local/Qwen
            self.routing_stats["local_calls"] += 1
            result = await qwen_local(prompt)
            return self._annotate_meta(result, route="local", lgpd_compliant=True, start_time=start_time)

    def _annotate_meta(
        self,
        result: Dict[str, Any],
        route: str,
        lgpd_compliant: bool,
        start_time: float,
    ) -> Dict[str, Any]:
        """Adiciona metadata de roteamento ao resultado."""
        if not isinstance(result, dict):
            result = {"text": str(result)}

        meta = result.get("_meta", {})
        meta.update({
            "route": route,
            "lgpd_compliant": lgpd_compliant,
            "latency_ms": (time.time() - start_time) * 1000,
            "pii_detected": contains_pii(str(result)),
            "routing_stats": self.get_routing_stats(),
        })
        result["_meta"] = meta
        return result

    def call_sync(
        self,
        prompt: str,
        context: Optional[Dict] = None,
        priority: str = "cost",
        force_local: bool = False,
        force_cloud: bool = False
    ) -> Dict:
        """
        Versão síncroma legada do SmartRouter.call().
        Mantida para compatibilidade com chamadas existentes.
        """
        start_time = time.time()
        combined_text = f"{prompt} {context or ''}"

        # 1. Decisão de roteamento
        use_local = self._decide_route(combined_text, force_local, force_cloud)

        # 2. Executa na rota escolhida
        try:
            if use_local:
                logger.info("🛡️ Roteando para LOCAL (Ollama) - LGPD")
                self.routing_stats["local_calls"] += 1
                result = self.local_adapter.supervise_task(prompt, context)
                result = self._annotate_meta(result, route="local", lgpd_compliant=True, start_time=start_time)
            else:
                logger.info("🌐 Roteando para CLOUD (Groq/Claude/GPT)")
                self.routing_stats["cloud_calls"] += 1
                result = self.cloud_router.call(prompt, context, priority)
                result = self._annotate_meta(result, route="cloud", lgpd_compliant=False, start_time=start_time)

            return result

        except Exception as e:
            logger.error(f"Roteamento falhou: {e}")
            self.routing_stats["fallbacks"] += 1

            # Fallback de emergência
            try:
                if use_local:
                    logger.warning("Fallback: Local falhou, tentando Cloud...")
                    result = self.cloud_router.call(prompt, context, priority)
                    result["_meta"]["route"] = "cloud_fallback"
                    return result
                else:
                    logger.warning("Fallback: Cloud falhou, tentando Local...")
                    result = self.local_adapter.supervise_task(prompt, context)
                    result["_meta"]["route"] = "local_fallback"
                    return result
            except Exception as e2:
                return {
                    "success": False,
                    "error": f"Todos os provedores falharam: {e} | {e2}",
                    "_meta": {"route": "failed", "latency_ms": (time.time() - start_time) * 1000}
                }

    def _decide_route(self, text: str, force_local: bool, force_cloud: bool) -> bool:
        """Lógica de decisão de roteamento (legada)."""

        if force_local:
            return True
        if force_cloud:
            return False

        # Modo LGPD desativado -> sempre cloud
        if not self.lgpd_mode:
            return False

        # Auto-detecção de PII
        if self.auto_detect_pii and contains_pii(text):
            self.routing_stats["pii_detected"] += 1
            return True

        return False

    def get_routing_stats(self) -> Dict:
        """Retorna estatísticas de roteamento + cache"""
        return {
            "routing": self.routing_stats.copy(),
            "cache": self.cache.get_stats(),
            "lgpd_mode": self.lgpd_mode
        }

    def reset_stats(self):
        """Reseta métricas"""
        self.routing_stats = {"cloud_calls": 0, "local_calls": 0, "pii_detected": 0, "fallbacks": 0}
        self.cache.clear()
        self.cloud_router.reset_stats()
