# server/ (visibilidade operacional + recomendações explicáveis)

Servidor de desenvolvimento com persistência SQLite, API de leitura operacional e recomendações técnicas baseadas em regras.

## Endpoints principais

Operacionais:
- `GET /v1/overview`
- `GET /v1/devices`
- `GET /v1/devices/{device_id}`
- `GET /v1/alerts/active`
- `GET /v1/audit/actions`
- `GET /v1/policies/effective/{agent_id}`
- `GET /v1/health/tenants/{tenant_id}`

Recomendações (somente leitura):
- `GET /v1/recommendations`
- `GET /v1/recommendations/devices/{device_id}`
- `GET /v1/recommendations/tenants/{tenant_id}`

Fluxo base já existente:
- `POST /v1/agents/bootstrap` (provisório)
- `GET /v1/policies/resolved`
- `POST /v1/agents/heartbeat`
- `POST /v1/ingestion/events:batch`
- `POST /v1/audit/actions:batch`
- `POST /v1/dev/policies` (provisório)

Gestão de policies para web-console (provisório):
- `GET /v1/policies` (filtros: `tenant_id`, `group_id`, `device_id`, `status`)
- `POST /v1/policies` (criar)
- `GET /v1/policies/{policy_id}` (detalhe)
- `PUT /v1/policies/{policy_id}` (editar)
- `POST /v1/policies/{policy_id}/disable` (desativar)
- `GET /v1/policies/audit` (auditoria, opcional `policy_id`)
- `GET /v1/policies/effective/{agent_id}`
- `GET /v1/policies/effective/device/{device_id}`

Observação CORS/local:
- o servidor expõe `Access-Control-Allow-Headers` incluindo `X-Dev-Actor`, usado pelo painel no create/edit/disable.

## Regras de recomendação (explicáveis)

A camada de recomendação usa heurísticas auditáveis (sem ML) sobre histórico:
- recorrência de eventos de RAM -> sugestão de upgrade RAM
- recorrência de disco -> sugestão HDD->SSD
- alertas térmicos/thermal_protect -> investigação de refrigeração
- indícios de energia/rede -> suspeitas correspondentes
- mensagem recorrente -> revisão de software/processo
- alta recorrência de autoações/falhas -> manutenção preventiva

Cada recomendação retorna: tipo, resumo, evidências, impacto, confiança, severidade, timestamp e status.
Recomendações estruturais (RAM/CPU/Storage) priorizam evidência de recorrência + mitigação local insuficiente, evitando sugestão precoce.

## Importante

- Recomendações **não executam ações**.
- São suporte à decisão humana do técnico.
- mTLS e autenticação forte ainda não implementados nesta fase.

## Fluxo de policy (painel)

1. Criar policy em `POST /v1/policies`.
2. Editar policy em `PUT /v1/policies/{policy_id}` (incrementa `version_no`).
3. Desativar policy em `POST /v1/policies/{policy_id}/disable`.
4. Consultar policy efetiva por agente/dispositivo.
5. Validar trilha em `GET /v1/policies/audit`.

> Tudo acima é provisório de desenvolvimento; sem ações remotas perigosas.
