# Transição do `realtime_agent` atual para `agent/` (incremental)

## Situação atual

- `realtime_agent/` continua sendo a base funcional executável.
- `agent/` foi criado como destino arquitetural futuro (scaffold fase 0).

## O que NÃO acontece nesta fase

- Não há migração em massa de código.
- Não há remoção ou quebra do fluxo atual.

## Estratégia de transição

1. **Adapter de contratos:**
   - `realtime_agent` passa a emitir payloads seguindo `contracts/schemas`.
2. **Outbox e transporte:**
   - incluir envio incremental para server quando disponível.
3. **Política remota com fallback local:**
   - usar `/v1/policies/resolved` quando online.
   - manter `config.json` local para modo offline.
4. **Migração física gradual:**
   - mover módulos de forma controlada para `agent/` com `git mv`.

## Critérios de segurança de migração

- Testes atuais do `realtime_agent` devem continuar verdes.
- Sem perda de trilha de auditoria.
- Sem perda de autonomia local em desconexão.
