"""
Batch Processor para EII — Processamento em massa com SmartRouter LGPD
Suporta: paralelismo, cache, retry, métricas e progresso em tempo real
"""

import os
import time
import json
import logging
from typing import List, Dict, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

from smartrouter.smart_router import SmartRouter
from crag_pipeline import run_crag, build_vector_store, diagnosticar_incidente
from xml_parser import parse_esocial_xml, scrub_pii
from knowledge_base import KB

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    """Resultado estruturado de um item processado em lote"""
    incident_id: str
    success: bool
    diagnosis: Optional[Dict] = None
    error: Optional[str] = None
    route_used: Optional[str] = None
    lgpd_compliant: bool = False
    latency_ms: float = 0.0
    pii_detected: bool = False
    cache_hit: bool = False
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class BatchStats:
    """Estatísticas agregadas do processamento em lote"""
    total: int = 0
    successful: int = 0
    failed: int = 0
    cloud_calls: int = 0
    local_calls: int = 0
    pii_detected: int = 0
    cache_hits: int = 0
    total_latency_ms: float = 0.0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    @property
    def success_rate(self) -> float:
        return (self.successful / self.total * 100) if self.total > 0 else 0.0
    
    @property
    def avg_latency_ms(self) -> float:
        return (self.total_latency_ms / self.total) if self.total > 0 else 0.0
    
    @property
    def elapsed_seconds(self) -> float:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0
    
    def to_dict(self) -> Dict:
        elapsed = self.elapsed_seconds
        return {
            "total": self.total,
            "successful": self.successful,
            "failed": self.failed,
            "success_rate_percent": round(self.success_rate, 2),
            "cloud_calls": self.cloud_calls,
            "local_calls": self.local_calls,
            "pii_detected": self.pii_detected,
            "cache_hits": self.cache_hits,
            "cache_hit_rate_percent": round((self.cache_hits / self.total * 100) if self.total > 0 else 0, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "elapsed_seconds": round(elapsed, 2),
            "throughput_per_second": round(self.total / elapsed, 2) if elapsed > 0 else 0
        }


class BatchProcessor:
    """Processador em lote com roteamento LGPD automático"""
    
    def __init__(
        self,
        router: Optional[SmartRouter] = None,
        max_workers: int = 4,
        retry_attempts: int = 2,
        progress_callback: Optional[Callable[[int, int, BatchResult], None]] = None
    ):
        self.router = router or SmartRouter(lgpd_mode=True)
        self.max_workers = max_workers
        self.retry_attempts = retry_attempts
        self.progress_callback = progress_callback
        self.stats = BatchStats()
        logger.info(f"BatchProcessor inicializado: {max_workers} workers")
    
    def _process_single(
        self,
        xml_path: str,
        incident_id: str,
        error_code: Optional[str] = None,
        mentor_mode: bool = False
    ) -> BatchResult:
        """Processa um único arquivo XML"""
        start = time.time()
        
        try:
            with open(xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            # Parse XML com função correta
            parsed = parse_esocial_xml(xml_content)
            
            # Chamar diagnóstico via SmartRouter (já integrado no crag_pipeline)
            result = diagnosticar_incidente(
                xml_content=xml_content,
                incident_id=incident_id,
                error_code=error_code,
                mentor_mode=mentor_mode
            )
            
            elapsed = (time.time() - start) * 1000
            meta = result.get("_meta", {})
            routing = result.get("_routing", {})
            
            return BatchResult(
                incident_id=incident_id,
                success=result.get("success", False),
                diagnosis=result if result.get("success") else None,
                error=result.get("error"),
                route_used=meta.get("route") or routing.get("route_used"),
                lgpd_compliant=meta.get("lgpd_compliant", routing.get("lgpd_mode", False)),
                latency_ms=elapsed,
                pii_detected=routing.get("pii_detected", False),
                cache_hit=meta.get("cache_hit", False),
                metadata={
                    "provider": meta.get("provider") or meta.get("llm"),
                    "eval_iterations": meta.get("eval_iterations"),
                }
            )
            
        except FileNotFoundError:
            return BatchResult(
                incident_id=incident_id,
                success=False,
                error=f"Arquivo não encontrado: {xml_path}",
                latency_ms=(time.time() - start) * 1000
            )
        except Exception as e:
            logger.warning(f"Erro ao processar {incident_id}: {e}")
            return BatchResult(
                incident_id=incident_id,
                success=False,
                error=str(e),
                latency_ms=(time.time() - start) * 1000
            )
    
    def _with_retry(self, func: Callable, *args, **kwargs) -> BatchResult:
        """Wrapper com retry exponencial"""
        last_error = None
        
        for attempt in range(self.retry_attempts + 1):
            try:
                result = func(*args, **kwargs)
                if result.success or attempt == self.retry_attempts:
                    return result
                last_error = result.error
            except Exception as e:
                last_error = str(e)
                if attempt == self.retry_attempts:
                    return BatchResult(
                        incident_id=kwargs.get("incident_id") or (args[1] if len(args) > 1 else "unknown"),
                        success=False,
                        error=f"Retry falhou: {last_error}"
                    )
            if attempt < self.retry_attempts:
                time.sleep(2 ** attempt)  # Backoff exponencial
        
        return BatchResult(incident_id="unknown", success=False, error=f"Max retries: {last_error}")
    
    def _update_stats(self, result: BatchResult):
        """Atualiza estatísticas em tempo real"""
        self.stats.total += 1
        if result.success:
            self.stats.successful += 1
        else:
            self.stats.failed += 1
        if result.route_used == "cloud":
            self.stats.cloud_calls += 1
        elif result.route_used in ["local", "local_fallback"]:
            self.stats.local_calls += 1
        if result.pii_detected:
            self.stats.pii_detected += 1
        if result.cache_hit:
            self.stats.cache_hits += 1
        self.stats.total_latency_ms += result.latency_ms
    
    def process_batch(
        self,
        xml_files: List[str],
        incident_ids: Optional[List[str]] = None,
        error_codes: Optional[List[Optional[str]]] = None,
        mentor_mode: bool = False
    ) -> List[BatchResult]:
        """Processa lista de arquivos XML em paralelo"""
        if not xml_files:
            return []
        
        if incident_ids is None:
            incident_ids = [f"BATCH-{i+1:04d}" for i in range(len(xml_files))]
        if error_codes is None:
            error_codes = [None] * len(xml_files)
        
        if len(xml_files) != len(incident_ids):
            raise ValueError("xml_files e incident_ids devem ter mesmo tamanho")
        
        self.stats = BatchStats(total=len(xml_files), start_time=time.time())
        results = []
        
        logger.info(f"Iniciando batch: {len(xml_files)} arquivos, {self.max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_idx = {
                executor.submit(
                    self._with_retry,
                    self._process_single,
                    xml_file, inc_id, err_code, mentor_mode
                ): i
                for i, (xml_file, inc_id, err_code) in enumerate(
                    zip(xml_files, incident_ids, error_codes)
                )
            }
            
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    result = future.result()
                    results.append(result)
                    self._update_stats(result)
                    if self.progress_callback:
                        self.progress_callback(idx + 1, len(xml_files), result)
                except Exception as e:
                    logger.error(f"Future {idx} falhou: {e}")
        
        self.stats.end_time = time.time()
        results.sort(key=lambda r: incident_ids.index(r.incident_id) if r.incident_id in incident_ids else 999)
        
        # Log final com cálculo seguro de throughput
        elapsed = self.stats.elapsed_seconds
        throughput = self.stats.total / elapsed if elapsed > 0 else 0
        logger.info(f"Batch concluído: {self.stats.successful}/{self.stats.total} sucesso, {elapsed:.1f}s, {throughput:.1f} itens/s")
        
        return results
    
    def get_stats(self) -> Dict:
        return self.stats.to_dict()
    
    def save_results(self, results: List[BatchResult], output_path: str, format: str = "json"):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        if format == "json":
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "stats": self.get_stats(),
                    "results": [r.to_dict() for r in results],
                    "timestamp": datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)


def process_batch(
    xml_files: List[str],
    router: Optional[SmartRouter] = None,
    max_workers: int = 4,
    incident_ids: Optional[List[str]] = None,
    error_codes: Optional[List[Optional[str]]] = None,
    mentor_mode: bool = False,
    output_path: Optional[str] = None,
    progress_callback: Optional[Callable] = None
) -> Dict:
    """Interface simplificada para processamento em lote"""
    processor = BatchProcessor(
        router=router, max_workers=max_workers, progress_callback=progress_callback
    )
    results = processor.process_batch(
        xml_files=xml_files, incident_ids=incident_ids,
        error_codes=error_codes, mentor_mode=mentor_mode
    )
    if output_path:
        processor.save_results(results, output_path)
    
    return {
        "success": True,
        "stats": processor.get_stats(),
        "results": [r.to_dict() for r in results],
        "summary": {
            "total": len(results),
            "successful": sum(1 for r in results if r.success),
            "failed": sum(1 for r in results if not r.success),
            "cloud_ratio": round(processor.stats.cloud_calls / len(results) * 100, 1) if results else 0,
            "local_ratio": round(processor.stats.local_calls / len(results) * 100, 1) if results else 0,
            "lgpd_compliant_count": sum(1 for r in results if r.lgpd_compliant)
        }
    }