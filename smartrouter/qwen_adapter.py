"""
Adapter para Qwen como supervisor econômico no SmartRouter-EII
"""

import json
import os
import re
from typing import Dict, Optional
from openai import OpenAI
from smartrouter.cache import get_cache, cached_task
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

logger = logging.getLogger(__name__)


class QwenAdapter:
    """Adapter para Qwen via provedores compatíveis com OpenAI API"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,  # ← Mudança 1: Optional
        model: Optional[str] = None,     # ← Mudança 2: Optional
        timeout: int = 30
    ):
        # Carrega do .env se não for passado como parâmetro
        self.api_key = api_key or os.getenv("QWEN_API_KEY")
        self.base_url = base_url or os.getenv("QWEN_BASE_URL", "https://api.groq.com/openai/v1")  # ← Default Groq
        self.model = model or os.getenv("QWEN_MODEL", "llama-3.1-8b-instant")  # ← Default Llama
        
        if not self.api_key:
            raise ValueError(
                "QWEN_API_KEY não configurada. "
                "Obtenha em https://console.groq.com/keys e adicione ao .env"
            )
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout
        )
    

    @cached_task(max_size=500, ttl_seconds=1800)  # Cache: 500 items, 30 min TTL
    def supervise_task(
        self,
        task: str,
        context: Optional[Dict] = None,
        output_format: str = "json"
    ) -> Dict:
        """Atua como supervisor: planeja, delega e valida tarefas (COM CACHE)"""
        
        system_prompt = self._build_supervisor_prompt(output_format)
        user_content = self._build_user_prompt(task, context)
        
        # Chamada SEM response_format para compatibilidade Groq
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
        logger.debug(f"Resposta bruta: {content[:300]}...")
        
        # Tenta parsear JSON direto, se falhar extrai do texto
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("JSON parse falhou, extraindo do texto...")
            result = self._extract_json_from_text(content)
        
        # Adiciona metadata de cache
        result["_meta"] = result.get("_meta", {})
        result["_meta"]["cache_hit"] = False  # Só chega aqui se foi cache miss
        
        return result
    
    def _build_supervisor_prompt(self, output_format: str) -> str:
        return f"""
Você é um supervisor especializado em sistemas multi-LLM para diagnóstico de incidentes ERP.

DOMÍNIO: eSocial, RFB, legislação trabalhista brasileira.

SUA FUNÇÃO:
1. Analisar tarefas de diagnóstico e classificação de incidentes
2. Planejar execução usando LLMs gratuitos (Groq: llama-3.1-8b, mistral-7b, gemma-2b)
3. Garantir que outputs sigam o schema do EII

FORMATO DE RESPOSTA:
- Responda APENAS com JSON válido
- Não inclua texto explicativo fora do JSON

EXEMPLO:
{{
  "plan": [{{"step": 1, "action": "parse_xml", "llm": "llama-3.1-8b"}}],
  "validation_rules": ["diagnosis não pode estar vazio"],
  "output_schema": {{"required": ["incident_id", "diagnosis"]}}
}}
"""
    
    def _build_user_prompt(self, task: str, context: Optional[Dict]) -> str:
        prompt = f"""
TAREFA PRINCIPAL: {task}

CONTEXTO DO PROJETO EII:
- Pipeline: CRAG (Retrieve → Grade → Generate → Validate)
- Domínio: Incidentes eSocial/ERP brasileiro
- KB: {context.get('kb_version', 'unknown') if context else 'unknown'}
"""
        if context:
            if context.get('incident_id'):
                prompt += f"- Incident ID: {context['incident_id']}\n"
            if context.get('error_code'):
                prompt += f"- Error Code: {context['error_code']}\n"
        prompt += "\nSua função: dividir em etapas, especificar LLMs, definir validação.\n"
        return prompt
    
    def _extract_json_from_text(self, text: str) -> Dict:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        return {
            "plan": [{"step": 1, "action": "fallback", "llm": "llama-3.1-8b"}],
            "validation_rules": ["revisar manualmente"],
            "warning": "JSON parsing fallback"
        }
    
    def translate_instruction(self, instruction: str, target_style: str = "qwen") -> str:
        if target_style == "qwen":
            return f"[SYSTEM] Output ONLY valid JSON.\n\n[TASK] {instruction}"
        elif target_style == "claude":
            return f"You are an expert supervisor.\n\nTask: {instruction}\n\nThink step-by-step."
        return instruction
    
    def get_usage_stats(self) -> Dict:
        return {"model": self.model, "base_url": self.base_url}