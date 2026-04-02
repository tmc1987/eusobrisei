# Realtime Monitoring Agent (Windows MVP)

Agente local funcional com política remota efetiva e auditoria de autoações.

## Mantido

- Monitoramento local, regras e autoações locais.
- Outbox SQLite + retry/backoff + idempotência.

## Novo nesta fase

- Bootstrap inicial provisório em desenvolvimento.
- Fetch periódico de política efetiva (`/v1/policies/resolved`).
- Aplicação de política remota com fallback local seguro.
- Auditoria completa de ações autônomas enviada em lote (`/v1/audit/actions:batch`).

## Política central aplicada sobre config local

- `thresholds`
- `actions.enabled`
- `actions.safe_mode`
- `actions.cooldown_seconds`
- `processes.restart_allowlist`

Se política remota não estiver disponível, agente continua com configuração local.

## Execução local completa

1. Suba o servidor.
2. (Opcional) Cadastre política em `/v1/dev/policies`.
3. Rode o agente:
```bash
cd realtime_agent
python main.py --config config.json
```

## Verificações úteis

```bash
cat data/identity.json
sqlite3 ../server/data/dev.db 'select count(*) from policies;'
sqlite3 ../server/data/dev.db 'select count(*) from action_audit;'
```

## Provisório desta fase

- Bootstrap e auth bearer simplificados para desenvolvimento.
- **mTLS ainda não implementado**.
