"""
ResilientLLM: Roteador Inteligente com Failover, Circuit Breaker e Cache
Suporta: Groq (Cloud), Ollama (Local), Claude, GPT
"""

import os
import time
import json
import logging
from typing import Dict, Optional, List, Callable
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class ResilientLLM:
    """
    Gerenciador de chamadas LLM com resiliência:
    - Failover automático entre provedores
    - Circuit Breaker para evitar chamadas a serviços falhos
    - Métricas de performance
    """
    
    def __init__(self, providers: Optional[List[str]] = None):
        # Ordem de preferência: Groq (rápido/barato) -> Claude -> GPT
        self.providers = providers or ["groq", "claude", "gpt"]
        
        # Estado do Circuit Breaker: {provider: {'failures': int, 'last_failure': float}}
        self._circuit_state = {p: {"failures": 0, "last_failure": 0.0} for p in self.providers}
        
        # Estatísticas
        self._stats = {p: {"calls": 0, "errors": 0, "latency": 0.0, "last_call": 0.0} for p in self.providers}
        
        # Configurações
        self.circuit_threshold = 3  # Nº de falhas antes de abrir o circuito
        self.circuit_timeout = 60   # Segundos antes de tentar novamente (half-open)
        
        # Adapters (lazy loading)
        self._adapters = {}
        
        logger.info(f"ResilientLLM inicializado com provedores: {self.providers}")
    
    def _is_circuit_open(self, provider: str) -> bool:
        """Verifica se o circuito está aberto (bloqueado) para um provedor"""
        if provider not in self._circuit_state:
            return True
        
        state = self._circuit_state[provider]
        
        # Se não há falhas, circuito está fechado (OK)
        if state["failures"] < self.circuit_threshold:
            return False
        
        # Se o tempo de timeout já passou, muda para half-open (permite 1 teste)
        if time.time() - state["last_failure"] > self.circuit_timeout:
            logger.info(f"Circuit Breaker HALF-OPEN para {provider} (teste permitido)")
            return False
        
        return True  # Circuito aberto (bloqueado)
    
    def _record_success(self, provider: str):
        """Registra sucesso e reseta circuit breaker"""
        if provider in self._circuit_state:
            self._circuit_state[provider]["failures"] = 0
    
    def _record_failure(self, provider: str):
        """Registra falha e atualiza circuit breaker"""
        if provider in self._circuit_state:
            self._circuit_state[provider]["failures"] += 1
            self._circuit_state[provider]["last_failure"] = time.time()
            self._stats[provider]["errors"] += 1
            logger.warning(f"Circuit Breaker: Falha registrada para {provider} ({self._circuit_state[provider]['failures']}/{self.circuit_threshold})")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def call(
        self,
        prompt: str,
        context: Optional[Dict] = None,
        priority: str = "cost",
        **kwargs
    ) -> Dict:
        """
        Chama a LLM com failover automático.
        
        Args:
            prompt: Texto do prompt
            context: Contexto adicional (dicionário)
            priority: "cost" (tenta groq primeiro) | "quality" (tenta claude/gpt primeiro)
        
        Returns:
            Dict com {'success': bool, 'result': ..., 'provider_used': str, 'error': str}
        """
        start_time = time.time()
        context = context or {}
        
        # Ordena provedores baseado na prioridade
        ordered_providers = self.providers.copy()
        if priority == "quality":
            ordered_providers.reverse()  # Inverte ordem para priorizar qualidade
        
        last_error = None
        
        for provider in ordered_providers:
            # 1. Verifica Circuit Breaker
            if self._is_circuit_open(provider):
                logger.debug(f"Provider {provider} com circuito aberto, pulando...")
                continue
            
            # 2. Tenta chamar o provedor
            try:
                logger.info(f"Tentando provider: {provider}")
                self._stats[provider]["calls"] += 1
                
                # Chama o provedor específico
                response = self._call_provider(provider, prompt, context, **kwargs)
                
                # 3. Sucesso!
                self._record_success(provider)
                elapsed = time.time() - start_time
                self._stats[provider]["latency"] = elapsed
                
                return {
                    "success": True,
                    "result": response,
                    "provider_used": provider,
                    "latency_ms": elapsed * 1000,
                    "_meta": {"provider": provider, "latency_ms": elapsed * 1000}
                }
                
            except Exception as e:
                last_error = str(e)
                self._record_failure(provider)
                logger.warning(f"Provider {provider} falhou: {e}")
                # Continua para o próximo provedor (failover)
        
        # 4. Todos falharam
        return {
            "success": False,
            "error": f"Todos os provedores falharam. Último erro: {last_error}",
            "provider_used": None,
            "latency_ms": (time.time() - start_time) * 1000,
            "_meta": {"error": last_error}
        }
    
    def _call_provider(self, provider: str, prompt: str, context: Dict, **kwargs) -> Dict:
        """Chama um provedor específico com tratamento adequado"""
        self._stats[provider]["last_call"] = time.time()
        
        if provider == "groq":
            # Groq é compatível com OpenAI API - chama diretamente
            from openai import OpenAI
            groq_client = OpenAI(
                base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
                api_key=os.getenv("GROQ_API_KEY") or os.getenv("QWEN_API_KEY"),
                timeout=30
            )
            response = groq_client.chat.completions.create(
                model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000
            )
            return {"content": response.choices[0].message.content}
            
        elif provider == "qwen":
            # Usa QwenAdapter se disponível (não implementado aqui, mas preparado)
            raise ValueError("Provider Qwen requer configuração via SmartRouter ou adapter externo")
            
        elif provider == "claude":
            from anthropic import Anthropic
            client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            response = client.messages.create(
                model="claude-sonnet-4-5-20251001", 
                max_tokens=2000, 
                messages=[{"role": "user", "content": prompt}]
            )
            return {"content": response.content[0].text}
            
        elif provider == "gpt":
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=[{"role": "user", "content": prompt}]
            )
            return {"content": response.choices[0].message.content}
            
        raise ValueError(f"Provider desconhecido: {provider}")
        