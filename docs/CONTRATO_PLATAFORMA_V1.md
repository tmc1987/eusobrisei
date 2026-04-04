# CONTRATO_DE_PLATAFORMA_V1

## Status deste documento

- **Contrato real (v1):** formatos, campos obrigatórios, endpoints e regras mínimas aqui definidos.
- **Fase futura:** tudo marcado explicitamente como `FUTURO`.

Este contrato mantém compatibilidade conceitual com `realtime_agent/` existente e **não substitui nem remove** o agente atual.

---

## 1. Escopo do V1

V1 cobre:
1. OpenAPI inicial do servidor central.
2. Schemas JSON de comunicação agente-servidor.
3. Modelo SQL inicial.
4. Fluxo de autenticação de agente.
5. Contrato de políticas centralizadas.
6. Contrato de auditoria de ações.
7. Regras de idempotência/retry/fila offline.
8. Estrutura inicial de monorepo e migração do agente atual.

Não cobre implementação completa de backend/painel.

---

## 2. Artefatos normativos (fonte da verdade)

1. `contracts/openapi.yaml`
2. `contracts/schemas/*.json`
3. `infra/sql/001_initial_schema.sql`
4. `docs/AUTH_FLOW.md`
5. `docs/POLICIES.md`
6. `docs/AUDITORIA.md`
7. `docs/MIGRACAO_MONOREPO.md`
8. `docs/DELIVERY_SEMANTICS.md`

Se houver conflito, a precedência é: **OpenAPI/Schemas > SQL > docs narrativas**.

---

## 3. Compatibilidade com realtime_agent atual

Compatibilidades garantidas no V1:
- conceitos de alerta, ação e severidade continuam.
- agente local continua com autonomia e fallback offline.
- políticas centralizadas seguem semântica de thresholds + ações permitidas.

Adaptações necessárias (sem quebrar MVP atual):
- padronizar payloads com `event_id`, `occurred_at`, `policy_version`.
- introduzir envio por lote com idempotência.
- separar claramente `alert` vs `action_audit` no transporte.

---

## 4. Limites claros do V1

- Backend completo: **fora do escopo**.
- Painel completo: **fora do escopo**.
- Modelos de IA avançados: **FUTURO**.
- Integrações externas (ticketing/SIEM): **FUTURO**.

---

## 5. Princípios obrigatórios do contrato

1. **Segurança por padrão:** autenticação forte de agente.
2. **Idempotência:** toda escrita remota precisa de chave idempotente.
3. **Auditabilidade:** toda auto-ação local deve gerar trilha assinável.
4. **Autonomia segura:** ações locais reversíveis priorizadas.
5. **Evolução versionada:** schemas e políticas com versionamento explícito.
