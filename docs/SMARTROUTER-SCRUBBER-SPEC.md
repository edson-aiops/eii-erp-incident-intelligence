# A3 — SmartRouter com PIIScrubber obrigatório

> **Objetivo:** Integrar o scrubber de PII v2 (A23) no pipeline Deep Agents. Consolidar
> como motor único de produção. Garantir que nenhum dado sensível saia do servidor
> sem autorização explícita.

**Status:** Draft (spec apenas, não implementação)  
**Versão:** 1.0  
**Data:** 2026-08-31

---

## 1. Contexto e decisão

### 1.1 Bifurcação arquitetural atual

Dois pipelines concorrentes:

| Pipeline | Entrada | Saída | Status |
|---|---|---|---|
| **Leve** (`eii_api.py` → `glm_router.py`) | XML bruto | Diagnóstico simples | ✅ Rodando |
| **Completo** (Deep Agents + SmartRouter + CRAG) | XML bruto | Diagnóstico com grading | ❌ Código pronto, desligado |

Razão da desativação: Deep Agents não integrado com eii_api.py; SmartRouter não
recebe sinal de PII; recuperação usa Chroma sem scrubbing.

### 1.2 Decisão de consolidação

**Escolher Deep Agents + SmartRouter como pipeline único.** Motivos:

1. Scrubber v2 (A23) foi entregue robusto. Integrá-lo só em glm_router desperdiça valor.
2. Deep Agents + CRAG com grading provavelmente gera diagnósticos 30-50% melhores.
3. Duas pipelines = duas coisas pra manter. Débito cresce.
4. Deep Agents + SmartRouter têm rastreabilidade, métricas, spans.

### 1.3 Escopo de A3

```
A3.1 — Spec (este documento)
A3.2 — Implementar parse_node com scrubber + resultado no estado
A3.3 — Integrar is_safe_for_remote em router_node e generate_node
A3.4 — Testes (payload sem PII no remoto, fallback a local)
A3.5 — Ligar eii_api.py ao Deep Agents (mata glm_router.py)
```

Este documento cobre **A3.1 e a assinatura de A3.2-A3.4.**

---

## 2. Fluxo de dados integrado

```
[Evento XML bruto]
        ↓
parse_node
  ├→ PIIScrubber.scrub(xml, event_type)
  ├→ Desempacota ScrubResult
  ├→ Atualiza AgentState: scrubbed_payload, is_safe_for_remote, token_map
  └→ continua ✓
        ↓
retrieve_node
  ├→ busca em ChromaDB usando scrubbed_payload
  ├→ retorna chunks sem PII
  └→ continua ✓
        ↓
router_node
  ├→ lê is_safe_for_remote do state
  ├→ se False → força routing_decision = "sensitive_data" (Ollama local)
  ├→ senão → roteia por severidade/tipo (regra atual)
  └→ continua ✓
        ↓
generate_node
  ├→ SmartRouter.call(prompt, routing_decision, is_safe_for_remote)
  ├→ se is_safe_for_remote=False → força local mesmo se ask_cloud
  ├→ gera diagnosis com tokens no lugar de valores
  └→ continua ✓
        ↓
finalize_node
  ├→ restore(diagnosis.resposta, token_map)
  ├→ retorna ao usuário com dados reais
  └→ FIM ✓
```

---

## 3. Contrato público — alterações de assinatura

### 3.1 AgentState (src/deep_agents/state.py)

**Adicionar campos:**

```python
class AgentState(TypedDict):
    # ... campos existentes ...
    
    # Novos (A3):
    scrubbed_payload: str                    # XML após PIIScrubber.scrub()
    is_safe_for_remote: bool                 # resultado.is_safe_for_remote
    token_map: Dict[str, str]                # mapa de reversão (local, não serializar)
    pii_scrubbed: bool                       # True se scrubber foi chamado
```

**Compatibilidade:** os campos novos são opcionais; código que lê o estado sem
eles não quebra (usa `.get(..., default)`).

### 3.2 parse_node (src/deep_agents/nodes/parse_node.py)

**Assinatura nova:**

```python
async def parse_node(state: AgentState) -> Dict[str, Any]:
    """
    Parse evento XML e aplica PIIScrubber.
    
    Retorna:
      - scrubbed_payload: str (XML com PII tokenizado)
      - is_safe_for_remote: bool (verdade canônica sobre segurança)
      - token_map: Dict[str, str] (para restore em finalize_node)
      - pii_scrubbed: bool = True
      - evento_id, tipo_evento, severidade (como antes)
    
    Fail-closed: se scrubber falha, retorna is_safe_for_remote=False.
    Nunca vaza XML bruto pro estado.
    """
```

**Comportamento:**

1. Parse XML, extrai `evento_id`, `tipo_evento`
2. Chama `PIIScrubber().scrub(xml, event_type)`
3. Retorna `ScrubResult` desempacotado:
   ```python
   return {
       "scrubbed_payload": result.scrubbed_payload,
       "is_safe_for_remote": result.is_safe_for_remote,
       "token_map": result.token_map,
       "pii_scrubbed": True,
       "evento_id": evento_id,
       "tipo_evento": tipo_evento,
       "severidade": detect_severity(scrubbed_payload),
   }
   ```
4. Se scrubber levanta exceção: captura, loga, retorna `is_safe_for_remote=False`

### 3.3 router_node (src/deep_agents/nodes/router_node.py)

**Mudança:** usar `is_safe_for_remote` em vez de `context.pi_detected`.

**Assinatura (sem mudança):**

```python
async def smart_router_node(state: AgentState) -> Dict[str, Any]:
    """
    Roteamento baseado em severidade e segurança de payload.
    
    Retorna:
      - routing_decision: str ("deep_reasoning" | "sensitive_data" | "simple_search")
      - model_used: None
    """
```

**Lógica nova:**

```python
is_safe = state.get("is_safe_for_remote", False)
severidade = state.get("severidade", "baixa")

# Fail-closed: se PII detectado, força local
if not is_safe:
    return {"routing_decision": "sensitive_data", "model_used": None}

# Senão, regra de severidade (como antes)
if severidade in ("critica", "alta"):
    return {"routing_decision": "deep_reasoning", "model_used": None}
elif severidade == "media":
    return {"routing_decision": "simple_search", "model_used": None}
else:
    return {"routing_decision": "simple_search", "model_used": None}
```

**Compatibilidade:** código que esperava `context.pi_detected` precisa ser
atualizado a ler `is_safe_for_remote`. Não é breaking change ao contrato
público; é mudança interna de lógica.

### 3.4 retrieve_node (src/deep_agents/nodes/retrieve_node.py)

**Mudança:** usar `scrubbed_payload` em vez de XML bruto.

**Assinatura (sem mudança):**

```python
async def retrieve_node(state: AgentState) -> Dict[str, Any]:
    """
    Recuperação de contexto via ChromaDB.
    
    Retorna:
      - context: str (chunks relevantes)
      - context_confidence: float
    """
```

**Lógica nova:**

```python
payload = state.get("scrubbed_payload", state.get("payload", ""))
# resto como antes, mas busca usa payload sem PII
chunks = chroma_client.query(payload, n_results=5)
```

### 3.5 generate_node (src/deep_agents/nodes/generate_node.py)

**Mudança:** passar `is_safe_for_remote` ao SmartRouter.

**Assinatura (sem mudança):**

```python
async def generate_node(state: AgentState) -> Dict[str, Any]:
    """
    Geração de diagnóstico via SmartRouter.
    
    Retorna:
      - diagnosis: Dict com resposta, confiança, etc.
      - model_used: str (qual modelo rodou)
    """
```

**Lógica nova:**

```python
routing_decision = state.get("routing_decision", "deep_reasoning")
is_safe = state.get("is_safe_for_remote", False)
payload = state.get("scrubbed_payload", "")

diagnosis = await SmartRouter.call(
    prompt=build_prompt(payload, state),
    routing_decision=routing_decision,
    is_safe_for_remote=is_safe,  # NOVO
)
```

**SmartRouter.call() recebe novo parâmetro:**

```python
async def call(
    self,
    prompt: str,
    routing_decision: str = "deep_reasoning",
    is_safe_for_remote: bool = True,  # NOVO
) -> Dict[str, Any]:
    """
    Roteamento condicional a segurança de PII.
    
    Se is_safe_for_remote=False, força Ollama local (nunca cloud).
    Senão, segue routing_decision.
    """
    
    if not is_safe_for_remote:
        # Força local: Ollama
        return await ollama_local(prompt)
    
    # Senão, regra de roteamento normal
    if routing_decision == "sensitive_data":
        return await ollama_local(prompt)
    elif routing_decision == "deep_reasoning":
        return await glm_remote(prompt)  # ou Groq, depende da config
    else:
        return await qwen_local(prompt)
```

**Fail-closed:** se `is_safe_for_remote=False`, **nenhuma combinação de
`routing_decision` ou configuração força o cloud.** O cloud só é chamado se
ambas as condições são verdadeiras: `is_safe_for_remote=True` E
`routing_decision` permite.

### 3.6 finalize_node (src/deep_agents/nodes/finalize_node.py)

**Mudança:** restaurar tokens em resposta antes de retornar ao usuário.

**Assinatura (sem mudança):**

```python
async def finalize_node(state: AgentState) -> Dict[str, Any]:
    """
    Finalização e retorno ao usuário.
    
    Retorna:
      - result: Dict com diagnosis, metadata, etc.
    """
```

**Lógica nova:**

```python
diagnosis = state.get("diagnosis", {})
token_map = state.get("token_map", {})

# Restaurar tokens na resposta
if token_map:
    resposta = diagnosis.get("resposta", "")
    resposta_restaurada = PIIScrubber().restore(resposta, token_map)
    diagnosis["resposta"] = resposta_restaurada

# Resto como antes
return {
    "result": {
        "diagnosis": diagnosis,
        "routing_decision": state.get("routing_decision"),
        "is_safe_for_remote": state.get("is_safe_for_remote"),
        # ... mais fields ...
    }
}
```

**Nota:** `token_map` **não é serializado** para o cliente; fica local para a
restauração. Nenhum token sai da máquina.

---

## 4. Invariantes de segurança

1. **Payload bruto nunca entra no estado.** Só `scrubbed_payload` fica acessível
   aos nodes após parse_node.

2. **is_safe_for_remote é verdade canônica.** Qualquer lógica de "PII detectado?"
   precisa checar este campo, não regex local ou heurística.

3. **Fail-closed é mandatório.** Se scrubber levanta exceção ou fica indeciso
   (`is_safe_for_remote=None`), tratar como `False`.

4. **token_map nunca sai do servidor.** Não serializar, não logar, não passar ao
   cliente. Vive no escopo do AgentState e morre após finalize_node.

5. **Restauração é pré-envio.** O diagnóstico sai com dados reais ao usuário;
   não há "modo anônimo" pra cliente.

---

## 5. Pontos de integração

### 5.1 Onde PIIScrubber entra

**Arquivo:** `src/deep_agents/nodes/parse_node.py`

**Linha de código (aproximada):**

```python
from src.privacy.scrubber import PIIScrubber

async def parse_node(state: AgentState) -> Dict[str, Any]:
    evento_id, tipo_evento = extract_ids(state["payload"])
    
    # INTEGRAÇÃO A3
    scrubber = PIIScrubber()
    result = scrubber.scrub(state["payload"], tipo_evento)
    # FIM INTEGRAÇÃO A3
    
    return {
        "scrubbed_payload": result.scrubbed_payload,
        "is_safe_for_remote": result.is_safe_for_remote,
        "token_map": result.token_map,
        "pii_scrubbed": True,
        "evento_id": evento_id,
        "tipo_evento": tipo_evento,
        "severidade": detect_severity(result.scrubbed_payload),
    }
```

### 5.2 Onde is_safe_for_remote flui

```
parse_node (gera) → state
                ↓
          router_node (lê)
          retrieve_node (lê)
          generate_node (passa ao SmartRouter)
          finalize_node (lê)
```

### 5.3 Onde token_map é usado

```
parse_node (gera, não serializa) → state (local)
                                      ↓
                              finalize_node (consome)
                                  ↓
                         restore(diagnosis, token_map)
```

---

## 6. Testes black-box esperados

### 6.1 Integração parse_node + scrubber

**Cenário:** XML com CPF do trabalhador entra em parse_node.

```python
def test_parse_node_scrubba_pii_e_retorna_resultado():
    """CPF não sai de parse_node em claro."""
    xml_com_cpf = "<trabalhador><cpfTrab>11111111111</cpfTrab>..."
    state = {"payload": xml_com_cpf}
    
    result = await parse_node(state)
    
    assert "11111111111" not in result["scrubbed_payload"]
    assert result["is_safe_for_remote"] == True
    assert "CPF_001" in result["scrubbed_payload"]
    assert len(result["token_map"]) > 0
```

### 6.2 Fail-closed em scrubber

**Cenário:** scrubber levanta exceção (malformed XML, etc.).

```python
def test_scrubber_exception_vira_is_safe_false():
    """Qualquer erro no scrubber → is_safe_for_remote=False."""
    xml_invalido = "<evento>não é XML bem formado"
    state = {"payload": xml_invalido}
    
    result = await parse_node(state)
    
    assert result["is_safe_for_remote"] == False
    # parse_node faz fallback: trata como "payload bruto, não seguro"
```

### 6.3 Router_node respeita is_safe_for_remote

**Cenário:** payload com PII não seguro; espera que router force local.

```python
def test_router_node_forca_local_quando_is_safe_false():
    """is_safe_for_remote=False → routing_decision='sensitive_data'."""
    state = {
        "is_safe_for_remote": False,
        "severidade": "baixa",
    }
    
    result = await router_node(state)
    
    assert result["routing_decision"] == "sensitive_data"
```

### 6.4 SmartRouter força local quando is_safe_for_remote=False

**Cenário:** mesmo que routing_decision diga "deep_reasoning", se is_safe=False,
vai local.

```python
def test_smartrouter_forca_local_mesmo_se_ask_deep():
    """is_safe_for_remote=False vence routing_decision."""
    result = await SmartRouter.call(
        prompt="diagnóstico",
        routing_decision="deep_reasoning",
        is_safe_for_remote=False,
    )
    
    # Deve ter rodado Ollama local, não GLM remoto
    assert result["model_used"] in ("ollama-local", "qwen-local")
```

### 6.5 Finalize_node restaura tokens

**Cenário:** diagnóstico tem tokens; saída ao usuário tem dados reais.

```python
def test_finalize_node_restaura_tokens():
    """Tokens dentro do diagnóstico são revertidos antes de retornar."""
    state = {
        "diagnosis": {
            "resposta": "Rejeitado: CPF_001 inválido no CNIS.",
            "confianca": 0.95,
        },
        "token_map": {"CPF_001": "11111111111"},
    }
    
    result = await finalize_node(state)
    
    assert "11111111111" in result["result"]["diagnosis"]["resposta"]
    assert "CPF_001" not in result["result"]["diagnosis"]["resposta"]
```

### 6.6 Payload sem PII seguro pra remoto

**Cenário:** XML válido, sem dados sensíveis. Espera is_safe=True.

```python
def test_payload_sem_pii_e_seguro_para_remoto():
    """Evento estrutural sem PII → is_safe_for_remote=True."""
    xml_estrutural = """
    <evento>
        <ideEvento><indRetif>1</indRetif></ideEvento>
        <ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
    </evento>
    """
    state = {"payload": xml_estrutural}
    
    result = await parse_node(state)
    
    assert result["is_safe_for_remote"] == True
    assert result["pii_scrubbed"] == True  # scrubber rodou, mas nada pra fazer
```

### 6.7 Dados sensíveis não saem em claro pra cloud

**Cenário:** evita regressão — payload scrubbed é o que vai para SmartRouter.

```python
def test_smartrouter_recebe_payload_scrubbed():
    """generate_node passa scrubbed_payload ao SmartRouter, não bruto."""
    xml_com_cpf = "<trabalhador><cpfTrab>11111111111</cpfTrab>..."
    state = {
        "payload": xml_com_cpf,
        "scrubbed_payload": "<trabalhador><cpfTrab>CPF_001</cpfTrab>...",
        "is_safe_for_remote": True,
        "routing_decision": "deep_reasoning",
    }
    
    # Mock SmartRouter para capturar o que recebe
    with patch("smartrouter.SmartRouter.call") as mock_sr:
        await generate_node(state)
        
        call_args = mock_sr.call_args
        prompt = call_args.kwargs["prompt"]
        
        assert "11111111111" not in prompt
        assert "CPF_001" in prompt
```

---

## 7. Migração de eii_api.py para Deep Agents

**Fora do escopo de A3.1 (spec).** Mas para referência:

**Hoje:**
```
POST /diagnose → glm_router.py → qwen_local ou glm_remote → JSON
```

**Depois (A3.5):**
```
POST /diagnose → diagnose_incident_deep_agents() → graph.invoke(state)
                 → AgentState com scrubbed_payload, is_safe_for_remote
                 → JSON com diagnosis restaurado
```

---

## 8. EVIDENCE_PACK esperado

Quando A3.2-A3.4 estiverem implementados:

```markdown
## A3 — SmartRouter com PIIScrubber obrigatório

### Diff
- src/deep_agents/state.py: 3 campos novos ao AgentState
- src/deep_agents/nodes/parse_node.py: integração com PIIScrubber
- src/deep_agents/nodes/router_node.py: usar is_safe_for_remote
- src/deep_agents/nodes/retrieve_node.py: usar scrubbed_payload
- src/deep_agents/nodes/generate_node.py: passar is_safe_for_remote ao SmartRouter
- src/deep_agents/nodes/finalize_node.py: restore de tokens
- smartrouter/smart_router.py: novo parâmetro is_safe_for_remote

### Testes
- tests/test_deep_agents_scrubber_integration.py (7 cenários)
- tests/test_smartrouter_fail_closed.py (3 cenários)
- Regressão: tests/test_deep_agents/* (todos devem passar)

### Cobertura
- ✅ Payload sem PII seguro pra remoto
- ✅ Payload com PII não sai em claro
- ✅ fail-closed em exceção do scrubber
- ✅ Tokens restaurados antes de retorno ao usuário
- ✅ is_safe_for_remote não pode ser vencido por routing_decision

### Blast radius
- Localizado a Deep Agents e SmartRouter
- glm_router.py não é tocado (morrer em A3.5)
- ChromaDB usado como-está

### Rollback
```
git revert <commit A3.2>
# ou
git reset --hard <commit anterior a A3>
```

### Métrica
Nenhuma métrica nova. A3 habilita validação de A23 em produção.
```

---

## 9. Limitações e pontos abertos

1. **token_map não é persistido.** Cada request gera mapa novo; não há
   reversão cruzada entre requests. É por design (fail-closed).

2. **ChromaDB search usa scrubbed_payload.** Recuperação melhor ou pior que antes
   depende de qualidade do scrubber. Não é bug; é trade-off documentado.

3. **SMartRouter.call() pode listar qual modelo rodou?** Sim, retorna
   `model_used`. Informado ao usuário em metadata.

4. **Rollback de versão de scrubber?** Se versão v3 quebra, voltar a v2:
   ```
   git checkout v2:src/privacy/scrubber.py
   ```
   Os testes de A3 continuam valem pra v2 se contrato for mantido.

---

## 10. Próximos passos (fora desta spec)

- **A3.2:** Implementar parse_node + integração scrubber
- **A3.3:** router_node + generate_node + SmartRouter.call()
- **A3.4:** Testes black-box (7 cenários acima)
- **A3.5:** Ligar eii_api.py, mata glm_router.py (nova spec)
- **A12:** ADR sobre pseudonimização (reutiliza material de seção 3 v2)
- **A24:** Testes de integração com payload real (depende de A3.5)
