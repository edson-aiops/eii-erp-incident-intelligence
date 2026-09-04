# Relatório de Conformidade LGPD — EII Token Management

**Gerado em:** 2026-09-04T09:51:55.241632
**Período auditado:** N/A (sem dados)

## Resumo Executivo

- Total de restaurações auditadas: N/A (PostgreSQL indisponível)
- Taxa de sucesso: N/A%
- Violações de TTL (7 dias): N/A
- Status: ⚠️ INDISPONÍVEL (PostgreSQL offline)

## 1. Validação de TTL

⚠️ INDISPONÍVEL (PostgreSQL offline)

⚠️ Não foi possível validar: o PostgreSQL está indisponível nesta execução.
Execute novamente com o banco ativo para auditoria completa.

## 2. Padrões de Uso

Tokens mais restaurados:
```json
N/A (sem dados no período)
```

Distribuição por resultado:
```json
N/A (sem dados no período)
```

## 3. Conformidade LGPD

### Art. 5º, II — Finalidade e adequação

✅ Pseudonimização reversível implementada
- Método: token com mapa local (valores reais nunca saem do servidor)
- Cobertura: CPF, nome, e-mail, telefone e demais PII do S-2200
- Status: validado em testes A24 (payload limpo, tokens no lugar de PII)

### Art. 12 — Transparência e histórico de tratamento

⚠️ Histórico de tratamento registrado
- Armazenamento: PostgreSQL `tokenmap_audit` (A26)
- Rastreabilidade: incident_id, token_name, resultado e timestamp por restauração
- Metadados apenas — valores reais nunca persistidos (LGPD art. 12)

### Art. 18 — Direito de acesso do titular

✅ Dados acessíveis via `AuditLogStore.query_by_incident()`
- Método: consulta por incident_id no audit log
- Retenção: audit imutável; token_map com TTL de 7 dias (uso único)

### Art. 32 — Segurança e boas práticas

✅ Controles implementados
- TTL automático: 7 dias (Redis, A25) — expiração sem intervenção
- Fail-closed: PII não verificada aborta o processamento (A3.5)
- Audit: toda restauração registrada (A26)
- Fallback gracioso: indisponibilidade de Redis/PostgreSQL nunca expõe PII

## Conclusão

⚠️ **Conformidade não verificada** — PostgreSQL indisponível.

Recomendação: executar esta análise mensalmente e arquivar os relatórios
como evidência de accountability (art. 5º, XIV).
