"""
Cache System para SmartRouter - Reduz chamadas à API em tarefas repetitivas
Implementa: LRU Cache + TTL (Time-To-Live) + Métricas de Hit/Miss
"""

import hashlib
import json
import time
import logging
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple
from collections import OrderedDict
import threading

logger = logging.getLogger(__name__)


class CacheMetrics:
    """Métricas de desempenho do cache"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.total_requests = 0
    
    def record_hit(self):
        with self._lock:
            self.hits += 1
            self.total_requests += 1
    
    def record_miss(self):
        with self._lock:
            self.misses += 1
            self.total_requests += 1
    
    def record_eviction(self):
        with self._lock:
            self.evictions += 1
    
    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.hits / self.total_requests) * 100
    
    def get_stats(self) -> Dict:
        with self._lock:
            return {
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "total_requests": self.total_requests,
                "hit_rate_percent": round(self.hit_rate, 2)
            }
    
    def reset(self):
        with self._lock:
            self.hits = 0
            self.misses = 0
            self.evictions = 0
            self.total_requests = 0


class TTLCache:
    """
    Cache com TTL (Time-To-Live) + LRU Eviction
    Thread-safe e com métricas embutidas
    """
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """
        Args:
            max_size: Máximo de itens no cache (LRU eviction)
            ttl_seconds: Tempo de vida de cada entrada (1 hora padrão)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, Dict] = OrderedDict()
        self._lock = threading.RLock()
        self.metrics = CacheMetrics()
    
    def _make_key(self, *args, **kwargs) -> str:
        """Cria chave única e hashable para os argumentos"""
        key_parts = []
        
        # Processa argumentos posicionais
        for arg in args:
            if isinstance(arg, dict):
                key_parts.append(json.dumps(arg, sort_keys=True, default=str))
            elif isinstance(arg, (list, tuple)):
                key_parts.append(json.dumps(arg, default=str))
            else:
                key_parts.append(str(arg))
        
        # Processa argumentos nomeados
        for k, v in sorted(kwargs.items()):
            if isinstance(v, dict):
                key_parts.append(f"{k}={json.dumps(v, sort_keys=True, default=str)}")
            else:
                key_parts.append(f"{k}={v}")
        
        # Cria hash MD5 para manter a chave curta
        raw_key = "|".join(key_parts)
        return hashlib.md5(raw_key.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Retorna valor do cache se válido (não expirado)"""
        with self._lock:
            if key not in self._cache:
                self.metrics.record_miss()
                return None
            
            entry = self._cache[key]
            
            # Verifica TTL
            if time.time() - entry["timestamp"] > self.ttl_seconds:
                # Expirou - remove
                del self._cache[key]
                self.metrics.record_miss()
                logger.debug(f"Cache miss (TTL expired): {key[:8]}...")
                return None
            
            # Válido - move para o fim (LRU)
            self._cache.move_to_end(key)
            self.metrics.record_hit()
            logger.debug(f"Cache hit: {key[:8]}...")
            return entry["value"]
    
    def set(self, key: str, value: Any):
        """Armazena valor no cache com timestamp"""
        with self._lock:
            # Se já existe, atualiza
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = {
                    "value": value,
                    "timestamp": time.time()
                }
                return
            
            # Eviction LRU se necessário
            if len(self._cache) >= self.max_size:
                # Remove o item mais antigo (primeiro da OrderedDict)
                self._cache.popitem(last=False)
                self.metrics.record_eviction()
                logger.debug(f"Cache eviction: removed oldest entry")
            
            # Adiciona novo item
            self._cache[key] = {
                "value": value,
                "timestamp": time.time()
            }
            logger.debug(f"Cache set: {key[:8]}...")
    
    def clear(self):
        """Limpa todo o cache"""
        with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")
    
    def cleanup_expired(self) -> int:
        """Remove entradas expiradas - retorna número de itens removidos"""
        with self._lock:
            now = time.time()
            expired_keys = [
                key for key, entry in self._cache.items()
                if now - entry["timestamp"] > self.ttl_seconds
            ]
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired entries")
            
            return len(expired_keys)
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas completas do cache"""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl_seconds,
                "metrics": self.metrics.get_stats(),
                "estimated_memory_mb": self._estimate_memory_size()
            }
    
    def _estimate_memory_size(self) -> float:
        """Estimativa grosseira de uso de memória (MB)"""
        # Aproximação: cada entrada ~1-5KB dependendo do conteúdo
        avg_entry_size_kb = 2.0
        return (len(self._cache) * avg_entry_size_kb) / 1024


# Instância global singleton para uso compartilhado
_default_cache: Optional[TTLCache] = None
_cache_lock = threading.Lock()


def get_cache(
    max_size: int = 1000,
    ttl_seconds: int = 3600,
    force_new: bool = False
) -> TTLCache:
    """
    Obtém ou cria instância singleton do cache
    
    Args:
        max_size: Máximo de itens no cache
        ttl_seconds: TTL em segundos
        force_new: Força criação de nova instância (útil para testes)
    """
    global _default_cache
    
    with _cache_lock:
        if _default_cache is None or force_new:
            _default_cache = TTLCache(max_size=max_size, ttl_seconds=ttl_seconds)
            logger.info(
                f"Cache initialized: max_size={max_size}, ttl={ttl_seconds}s"
            )
        return _default_cache


def cached_task(
    max_size: int = 1000,
    ttl_seconds: int = 3600
):
    """
    Decorator para cachear resultados de tarefas do SmartRouter
    
    Usage:
        @cached_task(max_size=500, ttl_seconds=1800)
        def supervise_task(self, task: str, context: Dict = None):
            # Sua lógica aqui
            return result
    """
    def decorator(func):
        cache = TTLCache(max_size=max_size, ttl_seconds=ttl_seconds)
        
        def wrapper(*args, **kwargs):
            # Extrai o 'self' se for método de classe
            if args and hasattr(args[0], func.__name__):
                self_obj = args[0]
                call_args = args[1:]
            else:
                self_obj = None
                call_args = args
            
            # Cria chave do cache
            key = cache._make_key(*call_args, **kwargs)
            
            # Tenta obter do cache
            cached_result = cache.get(key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                cached_result["_meta"] = cached_result.get("_meta", {})
                cached_result["_meta"]["cache_hit"] = True
                return cached_result
            
            # Cache miss - executa função
            logger.debug(f"Cache miss for {func.__name__}")
            result = func(*args, **kwargs)
            
            # Armazena no cache
            cache.set(key, result)
            result["_meta"] = result.get("_meta", {})
            result["_meta"]["cache_hit"] = False
            
            return result
        
        # Expõe métodos do cache para monitoramento
        wrapper.cache = cache
        wrapper.cache_clear = cache.clear
        wrapper.cache_stats = cache.get_stats
        
        return wrapper
    
    return decorator