"""
ResilientLLM - Failover chain com Qwen supervisor
Groq (rápido) → Qwen (supervisor econômico) → Claude (qualidade) → GPT (último)
"""

import os
import time
import logging
from typing import Dict, Optional, Callable
from tenacity import retry, stop_after_attempt, wait_exponential
from smartrouter.qwen_adapter import QwenAdapter

logger = logging.getLogger(__name__)


class ResilientLLM:
    """
    Failover chain aprimorada:
    Groq (rápido/gratuito) → Qwen (supervisor econômico) → Claude (qualidade) → GPT (último)
    """
    
    def __init__(self, groq_caller: Callable = None):
        self._groq_caller = groq_caller
        self._qwen = None  # Lazy init
        self._claude = None
        self._gpt = None
        
        # Circuit breaker config
        self._failure_count = 0
        self._circuit_open_until = None
        self._CIRCUIT_THRESHOLD = 5  # Aumentado para tolerar mais falhas
        self._CIRCUIT_TIMEOUT = 300  # 5 minutos
        
        # Stats para observabilidade
        self._stats = {
            "groq": {"calls": 0, "failures": 0, "last_call": None},
            "qwen": {"calls": 0, "failures": 0, "last_call": None},
            "claude": {"calls": 0, "failures": 0, "last_call": None},
            "gpt": {"calls": 0, "failures": 0, "last_call": None}
        }
    
    @property
    def qwen(self) -> Optional[QwenAdapter]:
        """Lazy initialization do adapter Qwen"""
        if self._qwen is None:
            try:
                self._qwen = QwenAdapter()
                logger.info("Qwen adapter inicializado com sucesso")
            except ValueError as e:
                logger.warning(f"Qwen não configurado: {e}")
                self._qwen = None
        return self._qwen
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
    def call(
        self,
        prompt: str,
        context: Optional[Dict] = None,
        priority: str = "cost",  # "cost" | "quality" | "availability"
        use_qwen_supervisor: bool = True,
        **kwargs
    ) -> Dict:
        """
        Executa chamada com failover inteligente
        
        Args:
            prompt: Prompt para o LLM
            context: Contexto adicional
            priority: 
                - "cost": prefere Groq/Qwen (econômico)
                - "quality": prefere Claude/GPT (qualidade)
                - "availability": usa primeiro disponível
            use_qwen_supervisor: se True, usa Qwen para planejamento de tarefas complexas
        
        Returns:
            Dict com resultado e metadados
        """
        
        # Verifica circuit breaker
        if self._is_circuit_open():
            logger.warning("Circuit breaker aberto - tentando fallbacks limitados")
            return self._call_with_fallback(prompt, context, priority, **kwargs)
        
        # Ordem de tentativa baseada em priority
        if priority == "cost":
            order = ["groq", "qwen", "claude", "gpt"]
        elif priority == "quality":
            order = ["claude", "gpt", "qwen", "groq"]
        else:  # availability
            order = ["groq", "qwen", "claude", "gpt"]
        
        last_error = None
        
        for provider in order:
            try:
                logger.debug(f"Tentando provider: {provider}")
                result = self._call_provider(provider, prompt, context, **kwargs)
                self._record_success(provider)
                
                # Log de economia se usou Qwen em vez de Claude
                if provider == "qwen":
                    logger.info(f"✓ Qwen usado (economia vs Claude)")
                
                return {
                    "success": True,
                    "provider_used": provider,
                    "result": result,
                    "stats": self._stats
                }
            except Exception as e:
                self._record_failure(provider)
                last_error = e
                logger.warning(f"Provider {provider} falhou: {str(e)[:100]}")
                continue
        
        # Todos falharam
        self._trip_circuit()
        logger.error(f"Todos os providers falharam. Circuit breaker ativado.")
        return {
            "success": False,
            "error": str(last_error),
            "tried_providers": order,
            "circuit_status": "open"
        }
    
    def _call_provider(self, provider: str, prompt: str, context: Dict, **kwargs) -> Dict:
        """Dispatch para o provider específico"""
        
        self._stats[provider]["last_call"] = time.time()
        
        if provider == "groq" and self._groq_caller:
            return self._groq_caller(prompt, **kwargs)
        
        elif provider == "qwen":
            # Qwen como supervisor: usa supervise_task
            if not self.qwen:
                raise ValueError("Qwen não configurado - verifique QWEN_API_KEY no .env")
            return self.qwen.supervise_task(prompt, context, output_format="json")
        
        elif provider == "claude":
            # Implementação existente do Claude
            from anthropic import Anthropic
            client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            response = client.messages.create(
                model="claude-sonnet-4-5-20251001",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            return {"content": response.content[0].text}
        
        elif provider == "gpt":
            # Implementação existente do GPT
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            return {"content": response.choices[0].message.content}
        
        raise ValueError(f"Provider desconhecido ou não configurado: {provider}")
    
    def _call_with_fallback(self, prompt: str, context: Dict, priority: str, **kwargs) -> Dict:
        """Chamada limitada quando circuit breaker está aberto"""
        # Tenta apenas providers gratuitos quando circuit breaker aberto
        limited_order = ["groq", "qwen"] if self.qwen else ["groq"]
        
        for provider in limited_order:
            try:
                result = self._call_provider(provider, prompt, context, **kwargs)
                self._record_success(provider)
                return {
                    "success": True,
                    "provider_used": provider,
                    "result": result,
                    "circuit_status": "open_limited"
                }
            except Exception as e:
                self._record_failure(provider)
                logger.warning(f"Fallback {provider} falhou: {str(e)[:100]}")
                continue
        
        raise Exception("Todos os fallbacks falharam com circuit breaker aberto")
    
    def _record_success(self, provider: str):
        """Registra sucesso e reseta circuit breaker se necessário"""
        self._stats[provider]["calls"] += 1
        # Reduz failure count apenas se estava alto
        if self._failure_count > 0:
            self._failure_count = max(0, self._failure_count - 1)
        
        # Reseta circuit breaker se sucesso consistente
        if self._failure_count == 0 and self._circuit_open_until:
            logger.info("Circuit breaker resetado após sucesso")
            self._circuit_open_until = None
    
    def _record_failure(self, provider: str):
        """Registra falha e ativa circuit breaker se necessário"""
        self._stats[provider]["calls"] += 1
        self._stats[provider]["failures"] += 1
        self._failure_count += 1
        
        if self._failure_count >= self._CIRCUIT_THRESHOLD and not self._circuit_open_until:
            self._trip_circuit()
    
    def _is_circuit_open(self) -> bool:
        """Verifica se circuit breaker está aberto"""
        if not self._circuit_open_until:
            return False
        
        if time.time() >= self._circuit_open_until:
            logger.info("Circuit breaker fechado após timeout")
            self._circuit_open_until = None
            return False
        
        return True
    
    def _trip_circuit(self):
        """Ativa circuit breaker"""
        self._circuit_open_until = time.time() + self._CIRCUIT_TIMEOUT
        logger.warning(
            f"Circuit breaker ativado por {self._CIRCUIT_TIMEOUT}s "
            f"(falhas: {self._failure_count})"
        )
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas de uso dos providers"""
        total_calls = sum(s["calls"] for s in self._stats.values())
        total_failures = sum(s["failures"] for s in self._stats.values())
        
        return {
            "stats": self._stats,
            "circuit_status": "open" if self._is_circuit_open() else "closed",
            "failure_count": self._failure_count,
            "totals": {
                "calls": total_calls,
                "failures": total_failures,
                "success_rate": round((1 - total_failures/total_calls) * 100, 2) if total_calls > 0 else 100
            }
        }
    
    def reset_stats(self):
        """Reseta estatísticas e circuit breaker"""
        for provider in self._stats:
            self._stats[provider] = {"calls": 0, "failures": 0}
        self._failure_count = 0
        self._circuit_open_until = None
        logger.info("Estatísticas e circuit breaker resetados")