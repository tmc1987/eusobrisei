# web-console (operacional + gestão de policies dev)

Painel técnico consumindo endpoints reais do servidor, com foco em operação e gestão de policies de desenvolvimento.

## Funcionalidades desta fase

- visão geral (`/v1/overview`)
- tabela de dispositivos (`/v1/devices`)
- detalhe de dispositivo (`/v1/devices/{id}`)
- alertas ativos (`/v1/alerts/active`)
- autoações recentes (`/v1/audit/actions`)
- recomendações técnicas (`/v1/recommendations`)
- recomendações agregadas por tenant (`/v1/recommendations/tenants/{tenant_id}`)
- gestão de policies:
  - listar/filter (`/v1/policies`)
  - detalhe (`/v1/policies/{policy_id}`)
  - criar (`POST /v1/policies`)
  - editar (`PUT /v1/policies/{policy_id}`)
  - desativar (`POST /v1/policies/{policy_id}/disable`)
  - efetiva por agente (`/v1/policies/effective/{agent_id}`)
  - efetiva por dispositivo (`/v1/policies/effective/device/{device_id}`)
  - auditoria (`/v1/policies/audit`)

## Rodar localmente

```bash
cd web-console
python -m http.server 5500
```

Abra: `http://127.0.0.1:5500/index.html`

## Fluxo completo no painel

1. Abra a seção **Gestão de Policies (Dev)**.
2. Use filtros por escopo/status para localizar policy.
3. Clique em **detalhe** para abrir no editor JSON.
4. Crie policy nova com **Criar** ou altere com **Salvar edição**.
5. Desative policy com **Desativar**.
6. Consulte **Policy efetiva** por `agent_id` ou `device_id`.
7. Consulte **Auditoria de Policies** para validar alterações.

> Provisório de desenvolvimento: sem login complexo e sem ações remotas perigosas.
