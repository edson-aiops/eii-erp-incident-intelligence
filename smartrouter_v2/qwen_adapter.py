"""
Adapter para Qwen como supervisor econômico no SmartRouter-EII
Traduz instruções entre 'dialetos' Claude ↔ Qwen
Baseado em: https://github.com/andersonamaral2/Claude-Code-to-Deep-Agents-Skills-Converter
"""

import json
import os
import re
from typing import Dict, Optional, List
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

logger = logging.getLogger(__name__)


class QwenAdapter:
    """
    Adapter para Qwen via provedores compatíveis com OpenAI API:
    - AIMLAPI: https://aimlapi.com (recomendado - free tier generoso)
    - Together.ai: https://together.ai
    - Alibaba Cloud: https://www.alibabacloud.com
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.aimlapi.com/v1",
        model: str = "qwen/qwen2.5-72b-instruct",
        timeout: int = 30
    ):
        self.api_key = api_key or os.getenv("QWEN_API_KEY")
        if not self.api_key:
            raise ValueError(
                "QWEN_API_KEY não configurada. "
                "Obtenha gratuitamente em https://aimlapi.com e adicione ao .env"
            )
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=base_url,
            timeout=timeout
        )
        self.model = model
        self.base_url = base_url
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def supervise_task(
        self,
        task: str,
        context: Optional[Dict] = None,
        output_format: str = "json"
    ) -> Dict:
        """
        Atua como supervisor: planeja, delega e valida tarefas do CRAG/EII
        
        Args:
            task: Descrição da tarefa principal
            context: Contexto adicional (ex: incident_id, xml_content, kb_version)
            output_format: "json" (padrão) ou "structured"
        
        Returns:
            Dict com plano de execução estruturado
        """
        
        system_prompt = self._build_supervisor_prompt(output_format)
        user_content = self._build_user_prompt(task, context)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"} if output_format == "json" else None,
            temperature=0.1,  # Baixa temperatura para consistência
            max_tokens=2000
        )
        
        content = response.choices[0].message.content
        logger.debug(f"Qwen response: {content[:200]}...")
        
        # Parse JSON com fallback
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Qwen retornou JSON inválido, tentando extrair...")
            return self._extract_json_from_text(content)
    
    def _build_supervisor_prompt(self, output_format: str) -> str:
        """Prompt de sistema otimizado para Qwen"""
        return f"""
Você é um supervisor especializado em sistemas multi-LLM para diagnóstico de incidentes ERP.

DOMÍNIO: eSocial, RFB, legislação trabalhista brasileira, XML schema validation, eventos S-1000 a S-5000.

SUA FUNÇÃO:
1. Analisar tarefas de diagnóstico e classificação de incidentes
2. Planejar execução usando LLMs gratuitos (Groq: llama-3.1-8b, mistral-7b, gemma-2b, phi-3-mini)
3. Garantir que outputs sigam o schema do EII:
   {{
     "incident_id": "string",
     "error_code": "string", 
     "severity": "green|yellow|red",
     "diagnosis": "string",
     "resolution_steps": ["step1", "step2", ...],
     "confidence": 0.0-1.0,
     "requires_hitl": boolean,
     "kb_references": ["KB001", ...],
     "_meta": {{"retrieval_backend": "chromadb|ragflow", "llm_used": "string"}}
   }}
4. Incluir validação: cada etapa deve ter critérios de sucesso explícitos
5. Aplicar as 8 Transformações do Skill Converter:
   - T1: Mapear ferramentas/LLMs disponíveis
   - T2: Criar checklist de execução
   - T3: Verificar pré-requisitos (quota, backend, etc)
   - T4: Instruções explícitas (sem ambiguidade)
   - T5: Validação após cada etapa
   - T6: Paralelismo quando possível (subtasks)
   - T7: Documentação do workflow
   - T8: Troubleshooting e fallbacks

FORMATO DE RESPOSTA:
- Responda APENAS com JSON válido
- Não inclua texto explicativo fora do JSON
- Use campos obrigatórios do schema EII
- Para tarefas complexas, use "subtasks" para paralelismo

EXEMPLO DE OUTPUT VÁLIDO:
{{
  "plan": [
    {{"step": 1, "action": "parse_xml", "llm": "llama-3.1-8b", "input": "xml_content"}},
    {{"step": 2, "action": "retrieve_kb", "llm": "mistral-7b", "params": {{"backend": "chromadb"}}}},
    {{"step": 3, "action": "grade_relevance", "llm": "gemma-2b", "threshold": 0.7}},
    {{"step": 4, "action": "generate_diagnosis", "llm": "llama-3.1-8b", "context": "filtered_kb"}}
  ],
  "validation_rules": [
    "diagnosis não pode estar vazio",
    "confidence deve ser 0.0-1.0",
    "se severity=red, requires_hitl deve ser true"
  ],
  "output_schema": {{
    "required": ["incident_id", "error_code", "severity", "diagnosis"],
    "optional": ["resolution_steps", "confidence", "kb_references", "_meta"]
  }}
}}
"""
    
    def _build_user_prompt(self, task: str, context: Optional[Dict]) -> str:
        """Constroi prompt do usuário com contexto do EII"""
        prompt = f"""
TAREFA PRINCIPAL: {task}

CONTEXTO DO PROJETO EII:
- Pipeline: CRAG (Retrieve → Grade → Generate → Validate)
- Domínio: Incidentes eSocial/ERP brasileiro (eventos S-1000 a S-5000)
- Restrições: Human-in-the-Loop obrigatório para ações críticas (severity=red)
- KB: {context.get('kb_version', 'unknown') if context else 'unknown'}
- Incidentes: {context.get('incident_count', '?')} incidentes na base
"""
        
        if context:
            # Adiciona contexto específico
            if context.get('incident_id'):
                prompt += f"- Incident ID: {context['incident_id']}\n"
            if context.get('xml_snippet'):
                xml_preview = context['xml_snippet'][:300]
                prompt += f"- XML Snippet: {xml_preview}...\n"
            if context.get('error_code'):
                prompt += f"- Error Code: {context['error_code']}\n"
            if context.get('event_type'):
                prompt += f"- Event Type: {context['event_type']}\n"
        
        prompt += """
Sua função como supervisor:
1. Dividir esta tarefa em etapas executáveis pelos LLMs gratuitos disponíveis
2. Especificar qual LLM usar para cada etapa (llama-3.1-8b, mistral-7b, gemma-2b, phi-3)
3. Definir critérios de validação para cada resultado parcial
4. Estruturar o output final no formato esperado pelo EII
"""
        
        return prompt
    
    def _extract_json_from_text(self, text: str) -> Dict:
        """Extrai JSON de texto livre (fallback para outputs não-estruturados)"""
        # Tenta encontrar bloco JSON entre chaves
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError as e:
                logger.error(f"JSON extraction failed: {e}")
        
        # Fallback: retorna estrutura mínima
        return {
            "plan": [{"step": 1, "action": "fallback", "llm": "llama-3.1-8b"}],
            "validation_rules": ["output deve ser revisado manualmente"],
            "warning": "JSON parsing fallback - revisar output",
            "raw_response": text[:500]
        }
    
    def translate_instruction(self, instruction: str, target_style: str = "qwen") -> str:
        """
        Traduz instrução entre estilos de LLM (conceito do Skill Converter)
        
        target_style: 
          - "qwen": estruturado, JSON-first, direto
          - "claude": narrativo, chain-of-thought, explicativo
        """
        if target_style == "qwen":
            return f"""
[SYSTEM] Output ONLY valid JSON. No explanations outside JSON.

[TASK] {instruction}

[SCHEMA] Use fields: plan[], validation_rules[], output_schema{{}}
"""
        elif target_style == "claude":
            return f"""
You are an expert incident diagnosis supervisor.

Please analyze this task: {instruction}

Think through your reasoning step-by-step:
1. What information is needed?
2. How to retrieve it efficiently?
3. How to validate each step?

When ready, provide your execution plan in JSON format.
"""
        return instruction  # No translation needed
    
    def get_usage_stats(self) -> Dict:
        """Retorna estatísticas de uso (se disponível na API)"""
        # AIMLAPI geralmente não expõe stats detalhados via API pública
        # Implementar se necessário
        return {
            "model": self.model,
            "base_url": self.base_url,
            "note": "Stats detalhados disponíveis no dashboard do provider"
        }