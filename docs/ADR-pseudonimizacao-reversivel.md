# ADR A12: Pseudonimização com Mapa Reversível

**Status:** Aceita  
**Decisor:** Edson (arquiteto sênior HCM/eSocial)  
**Data:** 2026-09-03  
**Implementação:** A23 (PIIScrubber v2)  
**Validação:** A12 (testes de reversibilidade)

---

## 1. Contexto

O EII (ERP Incident Intelligence) processa eventos XML do eSocial com PII:
- CPF, nome, data de nascimento, filiação sindical, dados de saúde
- Regido por **LGPD art. 5º, II** (dados pessoais sensíveis)
- Precisa enviar diagnósticos para LLM remoto (cloud)
- Precisa retornar diagnósticos com dados reais ao usuário (para ação)

**Tensão central:** 
- Remoto não pode ver PII
- Usuário precisa ver PII na resposta
- Diagnóstico é inútil sem contexto (quem foi rejeitado?)

**Solução:** **Pseudonimização reversível com mapa local**.

---

## 2. Definições

### Anonimização (rejeitada)
Irreversível. Dados reais são destruídos, mapa não existe.

**Exemplo:** "CPF inválido" → "DADOS_PESSOAIS_001", e nunca mais se sabe qual CPF era.

**Problema:** Diagnóstico perde contexto. Usuário não sabe quem foi rejeitado. Inútil.

### Pseudonimização Reversível (aceita)
Dados reais mapeados para tokens. Mapa vive no servidor local, nunca sai.

**Exemplo:** 
```
Real: CPF = 11111111111, Nome = MARIA
Token: CPF_001 = 11111111111, NOME_001 = MARIA

Fluxo:
  1. XML bruto → scrubber
  2. XML scrubbed (tokens) → LLM remoto
  3. Diagnóstico com tokens → restaurar tokens → diagnóstico real → usuário
  
Mapa: local, morre após request, nunca enviado.
```

### Criptografia (rejeitada)
Reversível, mas problema diferente: chave de descriptografia precisaria sair ou ficar no servidor.

**Se chave sai:** não protege nada (remoto decripta).  
**Se chave fica:** remoto não consegue fazer processamento contextual.

---

## 3. Alternativas Consideradas

| Alternativa | Reversível | PII sai | Diagnóstico | LGPD | Custo | Decisão |
|---|---|---|---|---|---|---|
| **Anonimização** | ❌ | ❌ | ❌ (contexto perdido) | ✅ | Baixo | Rejeitada |
| **Pseudonimização reversível** | ✅ | ❌ | ✅ | ✅ | Médio | **ACEITA** |
| **Criptografia simetrica** | ✅ | Depende | ✅ | Depende | Alto | Rejeitada |
| **Suprimir PII** | ❌ | ❌ | ❌ (breaks rules) | ✅ | Baixo | Rejeitada |
| **Sem processar (reject)** | n/a | ❌ | ❌ | ✅ | Alto (usuário fica sem diagnóstico) | Rejeitada |

---

## 4. Decisão

**Pseudonimização reversível com mapa local** é a solução que:

1. ✅ **Respeita LGPD.** Dados sensíveis nunca deixam o servidor (art. 32, dever de segurança).
2. ✅ **Preserva diagnóstico.** Token `CPF_001` permite rastrear "quem foi rejeitado" sem expor CPF.
3. ✅ **Reversível.** `restore(diagnóstico, token_map)` retorna dados reais ao usuário.
4. ✅ **Auditável.** Fluxo transparente: XML → scrubbed → remoto → restaurado.
5. ✅ **Escalável.** Mapa por request, sem estado global.

---

## 5. Implementação (A23)

### Contrato público

```python
class ScrubResult:
    scrubbed_payload: str              # XML com tokens
    is_safe_for_remote: bool           # verdade sobre segurança
    token_map: Dict[str, str]          # mapa reversível (local, não serializa)
    fields_scrubbed: List[str]         # auditoria

scrubber.scrub(xml: str, event_type: str) -> ScrubResult
scrubber.restore(texto: str, token_map: Dict) -> str
```

### Fluxo de dados

```
1. XML bruto (CPF=11111111111, Nome=MARIA)
   ↓
2. scrubber.scrub()
   ├─ CPF_001 = 11111111111
   ├─ NOME_001 = MARIA
   └─ token_map = {CPF_001: 11111111111, NOME_001: MARIA}
   ↓
3. XML scrubbed (CPF_001, NOME_001) → LLM remoto
   ↓
4. Diagnóstico: "Rejeitado: CPF_001 inválido"
   ↓
5. scrubber.restore(diagnóstico, token_map)
   → "Rejeitado: 11111111111 inválido"
   ↓
6. Retorna ao usuário com dados reais
```

### Garantias de segurança

**A23 implementa (verificado em testes):**

1. **token_map nunca é serializado.** Morre após `finalize_node`.
2. **Valores reais nunca saem em claro.** Regex + run de dígitos + varredura por campo.
3. **Fail-closed em exceção.** `is_safe_for_remote=False` se scrubber falha.
4. **Restauração é idêntica.** `restore()` reverte tokens exatamente.

---

## 6. Consequências

### Positivas
- ✅ LGPD compliance (art. 5º, II e 32)
- ✅ Diagnóstico acionável (contexto preservado)
- ✅ Transparente (tokens são óbvios, não ofuscados)
- ✅ Reversível (auditoria end-to-end possível)

### Negativas
- ⚠️ Mapa em memória (perde-se ao reiniciar); usar DB em produção (A25+)
- ⚠️ Tokens ocupam espaço no payload (negligível: `CPF_001` vs `11111111111`)
- ⚠️ Requer restauração pré-envio (implementado em `finalize_node`)

### Riscos residuais
- **Se token_map for serializado acidentalmente:** PII sai junto. Mitigado: testes verificam.
- **Se scrubber falhar silenciosamente:** PII não é scrubbed. Mitigado: fail-closed + testes.
- **Se remoto guarda tokens e os corrompe com PII:** Novo risco fora deste sistema.

---

## 7. Conformidade

### LGPD art. 5º, II (dado pessoal sensível)
> "tratamento de dado pessoal sensível será realizado para fins de **prevenção de risco**
> ou **necessidade operacional** da pessoa natural"

✅ EII previne rejeição de eventos eSocial (prevenção de risco, operacional).

### LGPD art. 32 (dever de segurança)
> "Controlador deve **manter controle efetivo sobre os dados** usando **medidas técnicas e administrativas**"

✅ Pseudonimização com mapa local = controle do servidor, técnica de segurança reconhecida.

### LGPD art. 18 (direito de acesso)
> "Titular tem direito de **obter informações sobre seus dados**"

✅ Diagnóstico restaurado retorna contexto real ao usuário (informação sobre seu evento).

---

## 8. Decisões futuras (fora do escopo A12)

1. **A25:** Migrar token_map para DB (Redis/PostgreSQL) — hoje em memória
2. **A26:** Audit log de reversões (quem restaurou qual token, quando)
3. **A27:** TTL de token_map — expirar após X minutos se não for usado
4. **A28:** Criptografia de token_map em transit (se usar DB remoto)

---

## 9. Registro de aprovação

| Papel | Decisão | Data |
|---|---|---|
| Arquiteto | Pseudonimização reversível | 2026-09-03 |
| Validação (A12) | Testes de reversibilidade passam | 2026-09-03 |
| Release owner | Edson (push/merge) | Pendente |

---

## Referências

- LGPD Lei 13.709/2018 — arts. 5º, 18, 32
- eSocial — Tabelas de layout (S-1.3, S-2.1)
- PIIScrubber v2 (A23) — Implementação
- SmartRouter (A3) — Integração com is_safe_for_remote
