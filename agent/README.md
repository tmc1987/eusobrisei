# agent/ (fase 0)

Esta pasta representa o destino da evolução do agente Windows na nova arquitetura.

## Status
- **Scaffold** (sem migração completa ainda).
- O agente funcional atual continua em `realtime_agent/`.

## Estratégia incremental
1. Manter `realtime_agent/` como runtime de produção atual.
2. Migrar módulos por adapter para contratos em `contracts/`.
3. Quando estável, mover gradualmente para `agent/` com `git mv`.
