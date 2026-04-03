# Contrato de Auditoria de Ações (V1)

## Objetivo
Garantir rastreabilidade completa de toda auto-ação local executada pelo agente.

## Transporte

- Endpoint: `POST /v1/audit/actions:batch`
- Schema: `contracts/schemas/action_audit_batch_request.json`

## Campos críticos de auditoria

- `action_id` (idempotência por ação)
- `trigger_event_id`
- `action_name`
- `risk_level`
- `pre_state` e `post_state`
- `rollback_possible` e `rollback_executed`
- `execution_status` + `error_message`
- `policy_version`

## Regras operacionais

- Auditoria deve ser gravada localmente antes do envio remoto.
- Falha no envio não pode apagar trilha local.
- Se envio duplicado ocorrer, servidor deve tratar por `action_id`.
