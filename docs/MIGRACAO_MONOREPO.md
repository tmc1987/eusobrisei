# Plano de Migração do `realtime_agent` para Arquitetura de Plataforma

## Premissas

- Não apagar `realtime_agent` atual.
- Preservar funcionalidades já existentes (coleta, análise, regras, ações).
- Introduzir contratos V1 progressivamente, sem big-bang.

## Estrutura alvo inicial

```text
.
├─ realtime_agent/                # legado funcional (mantido)
├─ contracts/
│  ├─ openapi.yaml
│  └─ schemas/
├─ infra/
│  └─ sql/
├─ docs/
│  ├─ CONTRATO_PLATAFORMA_V1.md
│  ├─ AUTH_FLOW.md
│  ├─ POLICIES.md
│  ├─ AUDITORIA.md
│  └─ MIGRACAO_MONOREPO.md
└─ platform/                      # FUTURO (código servidor/painel)
   ├─ server/
   └─ web-console/
```

## Fases de migração

### Fase M1 (sem quebrar nada)
- Adicionar adaptador no agente para produzir payloads conforme `contracts/schemas`.
- Manter lógica local intacta.

### Fase M2
- Introduzir outbox local (`events` + `action_audit`) e retries.
- Adicionar cliente HTTP para endpoints V1.

### Fase M3
- Adotar política remota resolvida (`/v1/policies/resolved`) como fonte principal.
- `config.json` local vira fallback offline.

### Fase M4
- Separar `realtime_agent` em `platform/agent-windows` sem perder histórico (git mv).

## Critérios de sucesso

- Mesma capacidade local do agente antes/depois.
- Sem perda de eventos/auditoria durante offline.
- Sem regressão nos testes existentes.
