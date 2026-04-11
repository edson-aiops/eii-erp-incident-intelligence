"""
SmartRouter Dual-Profile: Roteamento Inteligente Cloud + Local (LGPD)
Decide automaticamente baseado em sensibilidade dos dados.
"""

import os
import logging
from typing import Dict, Optional
from smartrouter.llm_resilient import ResilientLLM
from smartrouter.ollama_adapter import OllamaAdapter
from smartrouter.pii_detector import contains_pii
from smartrouter.cache import get_cache
import time

logger = logging.getLogger(__name__)

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
    
    def call(
        self,
        prompt: str,
        context: Optional[Dict] = None,
        priority: str = "cost",
        force_local: bool = False,
        force_cloud: bool = False
    ) -> Dict:
        """
        Roteia chamada baseado em sensibilidade e configuração
        
        Args:
            prompt: Texto da tarefa
            context: Contexto adicional
            priority: "cost" | "quality" | "availability"
            force_local: Força rota local (ignora detecção)
            force_cloud: Força rota cloud (ignora detecção)
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
                result["_meta"] = {
                    "route": "local",
                    "llm": self.local_adapter.model,
                    "lgpd_compliant": True,
                    "latency_ms": (time.time() - start_time) * 1000
                }
            else:
                logger.info("🌐 Roteando para CLOUD (Groq/Claude/GPT)")
                self.routing_stats["cloud_calls"] += 1
                result = self.cloud_router.call(prompt, context, priority)
                result["_meta"] = {
                    "route": "cloud",
                    "provider": result.get("provider_used", "unknown"),
                    "lgpd_compliant": False,
                    "latency_ms": (time.time() - start_time) * 1000
                }
            
            # Adiciona metadata de roteamento
            result["_meta"]["pii_detected"] = contains_pii(combined_text)
            result["_meta"]["routing_stats"] = self.get_routing_stats()
            
            return result
            
        except Exception as e:
            logger.error(f"Roteamento falhou: {e}")
            self.routing_stats["fallbacks"] += 1
            
            # Fallback de emergência: se local falhar, tenta cloud (e vice-versa)
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
        """Lógica de decisão de roteamento"""
        
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