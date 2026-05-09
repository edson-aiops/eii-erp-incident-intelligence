"""
EII — IntelAgent
Agente de inteligencia proativa: analisa padroes historicos e sugere
incidentes relacionados sem chamar LLMs — puro Python sincrono.

Entrada: final_result (dict) produzido pelo finalize_node
Saida:   ProactiveInsights (dict)
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Thresholds para risco de recorrencia
_RISCO_ALTO_MIN = 5     # >= 5 ocorrencias em 90 dias
_RISCO_MEDIO_MIN = 2    # 2-4 ocorrencias
_TENDENCIA_WINDOW = 30  # dias para calculo de tendencia
_RELATED_TOP_N = 3      # max incidentes relacionados retornados


def _resolve_db_path() -> str:
    path = os.environ.get("DB_PATH", "eii_incidents.db")
    if path.startswith("/data"):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except OSError:
            return "eii_incidents.db"
    return path


class IntelAgent:
    """
    Agente de inteligencia proativa do EII.

    Uso:
        agent = IntelAgent()
        insights = agent.run(final_result)
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _resolve_db_path()

    # ─────────────────────────────────────────────────────────────────────────
    # SQLite helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _load_history(self, since: datetime) -> List[Dict[str, Any]]:
        """Carrega incidentes do SQLite criados a partir de `since`."""
        try:
            con = sqlite3.connect(self.db_path)
            con.execute("PRAGMA busy_timeout=3000")
            cur = con.execute(
                "SELECT id, created_at, diagnosis_json, status, decided_at "
                "FROM incidents WHERE created_at >= ? ORDER BY created_at DESC",
                (since.isoformat(),),
            )
            rows = cur.fetchall()
            con.close()
        except Exception as e:
            logger.warning("IntelAgent: erro ao ler SQLite: %s", e)
            return []

        result = []
        for row in rows:
            inc_id, created_at, diag_json, status, decided_at = row
            try:
                diag = json.loads(diag_json)
            except Exception:
                diag = {}
            result.append({
                "id": inc_id,
                "created_at": created_at,
                "status": status,
                "decided_at": decided_at,
                "diag": diag,
            })
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Pattern analysis
    # ─────────────────────────────────────────────────────────────────────────

    def analyze_patterns(
        self,
        evento: str,
        codigo_erro: str,
        history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Analisa frequencia, taxa de aprovacao HITL, tempo medio de resolucao
        e tendencia para o par (evento, codigo_erro) no historico fornecido.
        """
        now = datetime.utcnow()
        cutoff_trend = now - timedelta(days=_TENDENCIA_WINDOW)

        matched: List[Dict] = []
        for inc in history:
            diag = inc["diag"]
            ev = diag.get("evento", "")
            ce = diag.get("codigo_erro", "")
            # match parcial: codigo_erro pode ser "E428, E001"
            ev_match = evento and ev and (evento.upper() in ev.upper() or ev.upper() in evento.upper())
            ce_match = codigo_erro and ce and any(
                c.strip().upper() in ce.upper() or ce.upper() in c.strip().upper()
                for c in codigo_erro.split(",")
            )
            if ev_match or ce_match:
                matched.append(inc)

        total = len(matched)
        approved = sum(1 for m in matched if m["status"] == "APPROVED")
        taxa_aprovacao = round(approved / total, 2) if total else 0.0

        # Tempo medio de resolucao (created_at → decided_at) em horas
        tempos: List[float] = []
        for m in matched:
            if m.get("decided_at") and m.get("created_at"):
                try:
                    t0 = datetime.fromisoformat(m["created_at"])
                    t1 = datetime.fromisoformat(m["decided_at"])
                    tempos.append((t1 - t0).total_seconds() / 3600)
                except Exception:
                    pass
        tempo_medio = round(sum(tempos) / len(tempos), 1) if tempos else None

        # Tendencia: comparar 30d mais recentes com os 30d anteriores
        recentes = [
            m for m in matched
            if _parse_dt(m["created_at"]) and _parse_dt(m["created_at"]) >= cutoff_trend
        ]
        anteriores = [
            m for m in matched
            if _parse_dt(m["created_at"]) and _parse_dt(m["created_at"]) < cutoff_trend
        ]
        if len(recentes) > len(anteriores):
            tendencia = "CRESCENTE"
        elif len(recentes) < len(anteriores):
            tendencia = "DECRESCENTE"
        else:
            tendencia = "ESTAVEL"

        return {
            "total_90d": total,
            "total_30d": len(recentes),
            "taxa_aprovacao": taxa_aprovacao,
            "tempo_medio_resolucao_h": tempo_medio,
            "tendencia": tendencia,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # KB tag-based similarity
    # ─────────────────────────────────────────────────────────────────────────

    def suggest_related(
        self,
        referencias_kb: List[str],
        exclude_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Encontra incidentes KB relacionados por sobreposicao de tags.
        Retorna top-N mais relacionados, excluindo os ja referenciados.
        """
        try:
            from knowledge_base import KB
        except ImportError:
            logger.warning("IntelAgent: nao foi possivel importar knowledge_base")
            return []

        exclude = set(referencias_kb or [])
        if exclude_ids:
            exclude.update(exclude_ids)

        # Coleta as tags dos itens referenciados
        ref_tags: set = set()
        for item in KB:
            if item["id"] in referencias_kb:
                ref_tags.update(item.get("tags", []))

        if not ref_tags:
            return []

        scored: List[Tuple[int, Dict]] = []
        for item in KB:
            if item["id"] in exclude:
                continue
            item_tags = set(item.get("tags", []))
            overlap = len(ref_tags & item_tags)
            if overlap > 0:
                scored.append((overlap, item))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            {
                "id": item["id"],
                "titulo": item["titulo"],
                "evento": item["evento"],
                "codigo_erro": item["codigo_erro"],
                "impacto": item.get("impacto", ""),
                "tempo_estimado": item.get("tempo_estimado", ""),
                "tags_comuns": list(ref_tags & set(item.get("tags", []))),
            }
            for _, item in scored[:_RELATED_TOP_N]
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # Alert generation
    # ─────────────────────────────────────────────────────────────────────────

    def build_alerts(
        self,
        patterns: Dict[str, Any],
        evento: str,
        codigo_erro: str,
    ) -> List[str]:
        """Gera alertas proativos baseados nos padroes detectados."""
        alerts: List[str] = []
        total = patterns.get("total_90d", 0)
        total_30d = patterns.get("total_30d", 0)
        tendencia = patterns.get("tendencia", "ESTAVEL")
        taxa = patterns.get("taxa_aprovacao", 0.0)
        tempo = patterns.get("tempo_medio_resolucao_h")

        if total >= _RISCO_ALTO_MIN:
            alerts.append(
                f"ATENCAO: Erro {codigo_erro}/{evento} ocorreu {total}x nos ultimos 90 dias. "
                "Considere revisao do processo ou automacao da correcao."
            )
        elif total >= _RISCO_MEDIO_MIN:
            alerts.append(
                f"Erro {codigo_erro}/{evento} e recorrente ({total}x em 90 dias). "
                "Verifique se ha causa sistemica nao resolvida."
            )

        if tendencia == "CRESCENTE" and total_30d >= 2:
            alerts.append(
                f"Tendencia CRESCENTE: {total_30d} ocorrencias nos ultimos 30 dias "
                "— frequencia aumentando em relacao ao periodo anterior."
            )

        if taxa < 0.5 and total >= 3:
            alerts.append(
                f"Taxa de aprovacao HITL baixa ({int(taxa*100)}%) para este tipo de erro. "
                "Revise a qualidade dos diagnosticos automaticos gerados."
            )

        if tempo and tempo > 8:
            alerts.append(
                f"Tempo medio de resolucao alto ({tempo}h). "
                "Este tipo de incidente pode exigir escalation ou documentacao adicional na KB."
            )

        return alerts

    # ─────────────────────────────────────────────────────────────────────────
    # Main entry point
    # ─────────────────────────────────────────────────────────────────────────

    def run(self, final_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa analise proativa sobre o final_result do pipeline.

        Args:
            final_result: dict retornado pelo finalize_node (ou format_for_gradio)

        Returns:
            ProactiveInsights dict com padrao_historico, incidentes_relacionados,
            alertas e risco_recorrencia.
        """
        try:
            from observability import traceable as _obs_traceable
            _run = _obs_traceable(
                name="EII.IntelAgent.run",
                run_type="chain",
                metadata={"component": "intel_agent", "pipeline": "Phase4"},
            )(self._run_impl)
            return _run(final_result)
        except Exception:
            return self._run_impl(final_result)

    def _run_impl(self, final_result: Dict[str, Any]) -> Dict[str, Any]:
        diag_raw = final_result.get("diagnosis_raw") or final_result
        evento = diag_raw.get("evento", "")
        codigo_erro = diag_raw.get("codigo_erro", "")
        referencias_kb = final_result.get("referencias_kb") or diag_raw.get("referencias_kb") or []

        since = datetime.utcnow() - timedelta(days=90)
        history = self._load_history(since)

        patterns = self.analyze_patterns(evento, codigo_erro, history)
        related = self.suggest_related(referencias_kb)
        alerts = self.build_alerts(patterns, evento, codigo_erro)

        # Risco de recorrencia
        total = patterns["total_90d"]
        tendencia = patterns["tendencia"]
        if total >= _RISCO_ALTO_MIN or tendencia == "CRESCENTE":
            risco = "ALTO"
        elif total >= _RISCO_MEDIO_MIN:
            risco = "MEDIO"
        else:
            risco = "BAIXO"

        insights = {
            "padrao_historico": patterns,
            "incidentes_relacionados": related,
            "alertas": alerts,
            "risco_recorrencia": risco,
            "evento": evento,
            "codigo_erro": codigo_erro,
        }

        logger.info(
            "IntelAgent: evento=%s, codigo_erro=%s, total_90d=%d, risco=%s, alertas=%d",
            evento, codigo_erro, total, risco, len(alerts),
        )

        return insights


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None
