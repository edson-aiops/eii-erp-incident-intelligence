"""
A25 — TokenMapStore: armazenamento de token_map com TTL e fallback.

O token_map (token -> valor real) NUNCA pode ser serializado na saida do
pipeline (ADR A12). A3 mantinha o mapa em AgentState (memoria do grafo),
o que escala apenas com 1 worker. A25 move o mapa para Redis com TTL
automatico e fallback para memoria quando Redis nao esta disponivel.

Contrato:
    store.set(incident_id, token_map, ttl_seconds)  -> escreve com TTL
    store.get(incident_id)                          -> {token: valor} | {}
    store.delete(incident_id)                       -> remove apos restore

Config via .env: REDIS_ENABLED, REDIS_HOST, REDIS_PORT, REDIS_DB.
"""

import redis
import json
import time
import logging
import os
from abc import ABC, abstractmethod
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TokenMapStore(ABC):
    """Interface abstrata para armazenar token_map."""

    @abstractmethod
    def set(self, incident_id: str, token_map: Dict[str, str], ttl_seconds: int = 604800) -> bool:
        """Armazena token_map com TTL."""
        pass

    @abstractmethod
    def get(self, incident_id: str) -> Dict[str, str]:
        """Recupera token_map. Retorna {} se não encontrado."""
        pass

    @abstractmethod
    def delete(self, incident_id: str) -> bool:
        """Remove token_map."""
        pass


class MemoryTokenMapStore(TokenMapStore):
    """Fallback em memória com TTL simulado."""

    def __init__(self):
        self._store = {}  # {incident_id: (token_map, expiry_time)}

    def set(self, incident_id: str, token_map: Dict[str, str], ttl_seconds: int = 604800) -> bool:
        expiry = time.time() + ttl_seconds
        self._store[incident_id] = (token_map, expiry)
        return True

    def get(self, incident_id: str) -> Dict[str, str]:
        if incident_id not in self._store:
            return {}

        token_map, expiry = self._store[incident_id]
        if time.time() > expiry:
            del self._store[incident_id]
            return {}

        return token_map

    def delete(self, incident_id: str) -> bool:
        if incident_id in self._store:
            del self._store[incident_id]
        return True


class RedisTokenMapStore(TokenMapStore):
    """Armazenamento em Redis com fallback automático."""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        try:
            # Timeouts curtos: se Redis estiver fora, o fallback nao pode
            # travar o pipeline (TCP connect em host morto pode levar ~1min)
            self.redis_client = redis.Redis(
                host=host, port=port, db=db, decode_responses=True,
                socket_connect_timeout=2, socket_timeout=2,
            )
            self.redis_client.ping()  # Verificar conexão
        except Exception as e:
            logger.warning(f"Redis não disponível ({e}), usando fallback memória")
            self.redis_client = None

        self.fallback = MemoryTokenMapStore()

    def set(self, incident_id: str, token_map: Dict[str, str], ttl_seconds: int = 604800) -> bool:
        if not self.redis_client:
            return self.fallback.set(incident_id, token_map, ttl_seconds)

        try:
            key = f"eii:tokenmap:{incident_id}"
            value_json = json.dumps(token_map)
            self.redis_client.setex(key, ttl_seconds, value_json)
            return True
        except Exception as e:
            logger.warning(f"Redis set falhou, usando fallback memória: {e}")
            self.fallback.set(incident_id, token_map, ttl_seconds)
            return False

    def get(self, incident_id: str) -> Dict[str, str]:
        if not self.redis_client:
            return self.fallback.get(incident_id)

        try:
            key = f"eii:tokenmap:{incident_id}"
            value_json = self.redis_client.get(key)
            if value_json:
                return json.loads(value_json)
        except Exception as e:
            logger.warning(f"Redis get falhou: {e}")

        # Fallback
        return self.fallback.get(incident_id)

    def delete(self, incident_id: str) -> bool:
        if not self.redis_client:
            return self.fallback.delete(incident_id)

        try:
            key = f"eii:tokenmap:{incident_id}"
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis delete falhou: {e}")

        return self.fallback.delete(incident_id)


# Singleton factory
_store_instance: Optional[TokenMapStore] = None


def get_token_map_store() -> TokenMapStore:
    """Factory singleton para TokenMapStore."""
    global _store_instance
    if _store_instance is None:
        if os.getenv("REDIS_ENABLED", "true").lower() == "true":
            try:
                _store_instance = RedisTokenMapStore(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", 6379)),
                    db=int(os.getenv("REDIS_DB", 0)),
                )
            except Exception as e:
                logger.error(f"Redis init falhou, usando memória: {e}")
                _store_instance = MemoryTokenMapStore()
        else:
            _store_instance = MemoryTokenMapStore()

    return _store_instance
