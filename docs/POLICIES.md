# Contrato de Políticas Centralizadas (V1)

## Hierarquia e precedência

1. Política de tenant
2. Política de grupo
3. Política de dispositivo

Regra: **mais específica vence**.

## Campos obrigatórios

Definidos no schema `contracts/schemas/policy_document.json`:
- `policy_id`, `version`, `scope`, `thresholds`, `actions`, `signature`

## Política efetiva resolvida

API `GET /v1/policies/resolved` sempre retorna o documento já resolvido para o agente.

## Compatibilidade com realtime_agent

Mapeamento direto esperado para `config.json` atual:
- `thresholds.cpu_percent`, `ram_percent`, `disk_percent`, `temperature_c`
- `actions.enabled`, `safe_mode`
- `actions.allowed_actions` -> whitelist local do executor

## FUTURO

- Janela de manutenção por fuso.
- Feature flags por versão do agente.
- Rollout canário automático por grupo.
