"""
Adapter para Ollama Local (LGPD-Compliant)
Compatível com OpenAI API, roda 100% local, zero egresso.
"""

import os
import json
import re
from typing import Dict, Optional
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from smartrouter.cache import cached_task
import logging

logger = logging.getLogger(__name__)

class OllamaAdapter:
    """Adapter para modelos locais via Ollama OpenAI-compatible endpoint"""
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 120
    ):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.model = model or os.getenv("OLLAMA_MODEL", "gemma2:27b")
        self.timeout = timeout
        
        # Ollama aceita qualquer chave, usamos "ollama" por padrão
        self.client = OpenAI(
            base_url=self.base_url,
            api_key="ollama",
            timeout=timeout
        )
        
        logger.info(f"OllamaAdapter inicializado: {self.model} @ {self.base_url}")
    
    @cached_task(max_size=300, ttl_seconds=3600)  # Cache local mais longo
    def supervise_task(
        self,
        task: str,
        context: Optional[Dict] = None,
        output_format: str = "json"
    ) -> Dict:
        """Supervisão local LGPD-compliant"""
        
        system_prompt = f"""
Você é um supervisor LOCAL e LGPD-compliant para diagnóstico de incidentes ERP.
DOMÍNIO: eSocial, RFB, legislação trabalhista brasileira.
REGRA CRÍTICA: NUNCA envie dados para servidores externos. Processe localmente.
Retorne APENAS JSON válido.

EXEMPLO:
{{
  "plan": [{{"step": 1, "action": "parse_xml", "llm": "local"}}],
  "validation_rules": ["dados_sensitivos_mascarados"],
  "output_schema": {{"required": ["incident_id", "diagnosis"]}}
}}
"""
        
        user_content = f"""
TAREFA: {task}
CONTEXTO: {context or {}}
INSTRUÇÃO: Divida em etapas, especifique validação, retorne JSON.
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            logger.debug(f"Ollama response: {content[:200]}...")
            
            # Parse JSON com fallback
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return self._extract_json(content)
                
        except Exception as e:
            logger.error(f"Ollama falhou: {e}")
            return {
                "error": str(e),
                "fallback": "local_processing_failed",
                "plan": [{"step": 1, "action": "manual_review", "llm": "human"}]
            }
    
    def _extract_json(self, text: str) -> Dict:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        return {
            "plan": [{"step": 1, "action": "fallback_local", "llm": "human"}],
            "warning": "JSON extraction failed"
        }
    
    def check_health(self) -> bool:
        """Verifica se Ollama está rodando"""
        try:
            response = self.client.models.list()
            models = [m.id for m in response.data]
            logger.info(f"Ollama models disponíveis: {models[:5]}...")
            return self.model in models
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False