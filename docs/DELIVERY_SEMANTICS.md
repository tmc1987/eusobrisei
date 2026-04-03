# Regras de Idempotência, Retry e Fila Offline (V1)

## 1) Idempotência

### Headers obrigatórios (escrita)
- `Idempotency-Key`
- `X-Request-Id`
- `X-Agent-Id`

### Regras
1. Mesmo `Idempotency-Key` + mesmo hash de payload => resposta reaproveitada.
2. Mesmo `Idempotency-Key` + payload diferente => `409 Conflict`.
3. TTL sugerido da chave no servidor: 24h.

## 2) Retry

### Política padrão do agente
- backoff exponencial: 1s, 2s, 4s, 8s, ... até 5 min
- jitter aleatório: 0-20%
- timeout por request: 10s
- tentativas máximas antes de reencolar: 10

### Códigos de resposta
- Retry: `408`, `429`, `5xx`, erro de rede
- Não retry: `400`, `401`, `403`, `404`, `409` (com payload divergente)

## 3) Fila offline local (outbox)

### Persistência
- SQLite WAL local
- Filas separadas:
  - `outbox_events`
  - `outbox_action_audit`

### Prioridade de envio
1. Auditoria de ações
2. Alertas/eventos críticos
3. Telemetria regular

### Retenção
- mínimo 72 horas (configurável)
- política de compactação para telemetria em caso de lotação

## 4) Garantias V1

- **At-least-once delivery** para eventos e auditoria.
- Ordenação por `occurred_at` dentro da mesma fila.
- Deduplicação no servidor por chave idempotente e IDs de domínio (`event_id`, `action_id`).
