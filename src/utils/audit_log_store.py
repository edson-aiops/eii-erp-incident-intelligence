"""
A26 — AuditLogStore: log de reversões de token_map em PostgreSQL.

A25 moveu token_map para Redis (uso único, apagado no restore) — sem auditoria.
A26 registra cada token restaurado no finalize_node, criando histórico de
tratamento acessível (LGPD art. 12).

LGPD / segurança:
    NUNCA registrar o valor real do token. Apenas metadados:
    token_name (ex.: "CPF_001") e token_value_length (int).
    incident_id é UUID/aleatório — não expõe PII.

Fallback gracioso:
    Se PostgreSQL estiver indisponível, log_restore/log_batch retornam
    False/0 e query_by_incident retorna [] — o pipeline NUNCA quebra
    por causa do audit log.

Config via .env:
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
"""

import logging
from typing import Optional
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timezone
import os

logger = logging.getLogger(__name__)


class AuditLogStore:
    """Registra reversões de token_map em PostgreSQL."""

    def __init__(self,
                 host: str = None,
                 port: int = None,
                 database: str = None,
                 user: str = None,
                 password: str = None):
        self.host = host or os.getenv("POSTGRES_HOST", "localhost")
        self.port = int(port or os.getenv("POSTGRES_PORT", 5432))
        self.database = database or os.getenv("POSTGRES_DB", "eii")
        self.user = user or os.getenv("POSTGRES_USER", "eii")
        self.password = password or os.getenv("POSTGRES_PASSWORD", "")

        self.conn = None
        self._connect()

    def _connect(self):
        """Conectar ao PostgreSQL."""
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                connect_timeout=5,
            )
            logger.info(f"Conectado ao PostgreSQL: {self.host}:{self.port}/{self.database}")
        except psycopg2.Error as e:
            logger.error(f"Falha ao conectar PostgreSQL: {e}")
            self.conn = None

    def log_restore(self,
                    incident_id: str,
                    token_name: str,
                    token_value_length: int,
                    result: str = "success",
                    error_msg: str = None,
                    job_id: str = None,
                    source: str = "finalize_node") -> bool:
        """Registra restauração de token (apenas metadados — nunca o valor)."""
        if not self.conn:
            logger.warning("PostgreSQL não disponível, audit log ignorado")
            return False

        try:
            cursor = self.conn.cursor()
            query = """
                INSERT INTO tokenmap_audit
                (incident_id, job_id, token_name, token_value_length, result, error_msg, source, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (
                incident_id,
                job_id,
                token_name,
                token_value_length,
                result,
                error_msg,
                source,
                datetime.now(timezone.utc).replace(tzinfo=None),
            ))
            self.conn.commit()
            cursor.close()
            return True
        except psycopg2.Error as e:
            logger.error(f"Erro ao registrar audit: {e}")
            return False

    def log_batch(self, records: list) -> int:
        """Registra múltiplos tokens em uma transação."""
        if not self.conn or not records:
            return 0

        try:
            cursor = self.conn.cursor()
            values = [
                (
                    r.get("incident_id"),
                    r.get("job_id"),
                    r.get("token_name"),
                    r.get("token_value_length"),
                    r.get("result", "success"),
                    r.get("error_msg"),
                    r.get("source", "batch"),
                    datetime.now(timezone.utc).replace(tzinfo=None),
                )
                for r in records
            ]
            query = """
                INSERT INTO tokenmap_audit
                (incident_id, job_id, token_name, token_value_length, result, error_msg, source, timestamp)
                VALUES %s
            """
            execute_values(cursor, query, values)
            self.conn.commit()
            count = len(records)
            logger.info(f"Registrados {count} audit logs")
            cursor.close()
            return count
        except psycopg2.Error as e:
            logger.error(f"Erro ao registrar batch: {e}")
            return 0

    def query_by_incident(self, incident_id: str, limit: int = 100) -> list:
        """Recupera audit logs de um incident (mais recentes primeiro)."""
        if not self.conn:
            return []

        try:
            cursor = self.conn.cursor()
            query = """
                SELECT id, token_name, result, timestamp, error_msg
                FROM tokenmap_audit
                WHERE incident_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """
            cursor.execute(query, (incident_id, limit))
            rows = cursor.fetchall()
            cursor.close()
            return rows
        except psycopg2.Error as e:
            logger.error(f"Erro ao buscar audit: {e}")
            return []

    def close(self):
        """Fechar conexão."""
        if self.conn:
            try:
                self.conn.close()
            except psycopg2.Error:
                pass
            self.conn = None
