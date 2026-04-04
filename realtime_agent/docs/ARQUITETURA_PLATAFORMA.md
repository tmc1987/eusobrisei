# Arquitetura da Plataforma de Sustentação Operacional Autônoma (Windows)

## 1) Objetivo reposicionado

Evoluir o MVP atual para uma **plataforma cliente-servidor** com três camadas:

1. **Agente local Windows** (autonomia operacional)
2. **Servidor central (API + banco + motores de política/correlação)**
3. **Painel técnico web** (operação, governança e intervenção humana)

Princípio central: o agente deve manter o computador funcional localmente mesmo sem conectividade temporária, e sincronizar telemetria/eventos/ações com o backend assim que possível.

---

## 2) Arquitetura completa do sistema

## 2.1 Visão em alto nível

```text
[Windows Endpoint]
  └── Agent Service
      ├── Collector (métricas + eventos + sintomas)
      ├── Detector (anomalias + risco)
      ├── Local Rule Engine (políticas recebidas)
      ├── Local Action Executor (auto-remediação reversível)
      ├── Local Queue (offline-first)
      ├── Local Store (estado + auditoria + rollback)
      └── Secure Uplink (TLS + identidade de agente)
                ||
                \/
[Central Platform]
  ├── API Gateway + Auth
  ├── Ingestion Service (eventos/telemetria/ações)
  ├── Policy Service (cliente/grupo/máquina)
  ├── Device Registry (inventário e identidade)
  ├── Correlation & Risk Engine
  ├── Alerting/Notification Service
  ├── Audit Service
  ├── Timeseries Store (telemetria)
  ├── Relational DB (config, inventário, incidentes)
  └── Message Broker (event-driven)
                ||
                \/
[Technical Web Console]
  ├── Fleet health
  ├── Alert triage
  ├── Incident timeline
  ├── Policy management
  ├── Action approvals (quando necessário)
  └── Compliance/Audit reports
```

## 2.2 Estilo arquitetural

- **Edge autonomy + centralized governance**
- **Offline-first no agente**
- **Event-driven no servidor**
- **Policy-as-code** por escopo (tenant → grupo → máquina)
- **Observabilidade e auditoria by design**

---

## 3) Responsabilidades exatas por camada

## 3.1 Camada 1 — Agente local Windows

### Responsabilidades
- Coletar continuamente:
  - CPU, RAM, disco, temperatura (quando disponível), rede
  - processos e serviços do Windows
  - eventos críticos do Event Viewer/WER
- Detectar sinais de degradação e risco iminente.
- Aplicar ações automáticas **locais**, seguras e reversíveis.
- Persistir localmente telemetria/eventos/ações quando offline.
- Enviar dados e receber políticas do servidor central.

### Não é responsabilidade do agente
- Decisão estratégica de upgrade de hardware ou mudança de infraestrutura.
- Ajustes de política corporativa sem autorização central.
- Ações destrutivas sem política explícita.

## 3.2 Camada 2 — Servidor central (API + banco)

### Responsabilidades
- Autenticar e autorizar agentes.
- Registrar inventário de máquinas e relacionamento com cliente (tenant).
- Receber fluxo de eventos e telemetria em tempo real.
- Correlacionar recorrência/tendência e calcular risco agregado.
- Distribuir políticas por cliente, grupo e máquina.
- Armazenar trilha de auditoria imutável de ações executadas.
- Expor APIs para painel técnico e integrações.

## 3.3 Camada 3 — Painel técnico web

### Responsabilidades
- Visualizar saúde da frota e priorização por severidade.
- Investigar histórico de eventos, sintomas e ações locais.
- Operar políticas (limiares, auto-ação, aprovação humana).
- Aprovar/recusar ações sensíveis quando exigido.
- Emitir recomendações de manutenção preventiva e upgrade.

---

## 4) Limites entre autonomia local e decisão humana

## 4.1 Matriz de autonomia

- **Autonomia total (local):**
  - ações de baixo risco e reversíveis (ex.: ajuste temporário de prioridade, restart de serviço não crítico, mitigação térmica leve).
- **Autonomia condicionada:**
  - ações médias com rollback e política de janela (ex.: restart de processo de negócio não crítico).
- **Aprovação humana obrigatória:**
  - ações de alto impacto (desinstalar driver, alterar boot, mudanças permanentes de energia/registro/segurança).

## 4.2 Regras de guardrail

- Toda ação local deve:
  1. ter política explícita,
  2. registrar motivo e contexto,
  3. ter rollback definido (quando aplicável),
  4. registrar resultado pós-ação.

---

## 5) Estrutura de pastas ideal (monorepo)

```text
platform/
  agent-windows/
    src/
      collector/
      detector/
      rules/
      actions/
      queue/
      transport/
      audit/
      policy/
    tests/
    config/
  server/
    api/
    services/
      ingestion/
      policy/
      correlation/
      alerting/
      audit/
      registry/
    workers/
    migrations/
    tests/
  web-console/
    src/
      pages/
      components/
      modules/
    tests/
  contracts/
    openapi/
    events/
    schemas/
  infra/
    docker/
    k8s/
    terraform/
  docs/
    architecture/
    runbooks/
    security/
```

---

## 6) Modelo de dados inicial

## 6.1 Entidades centrais (relacional)

- `tenants` (clientes)
- `device_groups` (grupos por perfil: escritório, CAD, PDV etc.)
- `devices` (máquinas)
- `agent_identities` (credenciais/certificados/chaves)
- `policies` (versão + escopo + assinatura)
- `incidents` (abertura, status, severidade, causa provável)
- `action_audit` (ação local, antes/depois, rollback, resultado)
- `operators` (técnicos)

## 6.2 Séries temporais

- `metrics_cpu`, `metrics_memory`, `metrics_disk`, `metrics_network`, `metrics_temperature`
- dimensões mínimas: `tenant_id`, `device_id`, `timestamp`, `sample_interval`

## 6.3 Eventos

- `event_type` (ALERT, ACTION_EXECUTED, ACTION_ROLLBACK, AGENT_HEARTBEAT, POLICY_APPLIED, ERROR)
- payload JSON versionado por schema em `contracts/schemas`

---

## 7) Estratégia de autenticação dos agentes

## 7.1 Recomendado (produção)

- **mTLS com certificado por agente** + rotação periódica.
- Provisionamento inicial por token de bootstrap de curta duração.
- Associação agente ↔ dispositivo ↔ tenant no `Device Registry`.

## 7.2 Fluxo resumido

1. Instalação do agente com token único de ativação.
2. Agente registra hardware fingerprint mínimo (não invasivo).
3. Servidor emite credencial curta + certificado do agente.
4. Comunicação posterior via mTLS + assinatura de payload.

## 7.3 Segurança adicional

- Revogação de credencial por comprometimento.
- Policy signature verification no agente.
- Clock skew tolerance e nonce anti-replay.

---

## 8) Fila local para funcionamento offline temporário

## 8.1 Requisitos

- Persistência local durável (ex.: SQLite WAL).
- Ordenação por timestamp + prioridade.
- Backpressure e retenção por janela configurável.
- Reenvio com retry exponencial + jitter.

## 8.2 Estratégia prática

- Tabelas locais:
  - `outbox_events`
  - `outbox_actions`
  - `delivery_attempts`
- Política de envio:
  - prioridade: auditoria de ação > alertas > métricas brutas
- Deduplicação via `event_id` idempotente.

---

## 9) Mecanismo de auditoria de ações

Cada ação local deve registrar:
- `action_id`, `device_id`, `policy_version`
- `trigger_alert_id`, `reason`, `risk_level`
- `pre_state` e `post_state`
- `rollback_possible`, `rollback_executed`
- `execution_status`, `error_message`
- `operator_override` (quando houver)

Auditoria precisa existir **local e centralmente**.

---

## 10) Classificação de severidade de alertas

- **S0 (info):** telemetria fora do ideal sem risco imediato.
- **S1 (low):** degradação leve, sem impacto percebido.
- **S2 (medium):** impacto moderado, tendência de piora.
- **S3 (high):** impacto alto com risco de travamento/indisponibilidade.
- **S4 (critical):** indisponibilidade iminente ou em curso.

### Exemplo de mapeamento
- CPU/RAM alta sustentada: S2/S3 conforme duração.
- Temperatura acima do limite crítico: S3/S4.
- Processo de serviço essencial parado: S3.
- Loop de falha repetida + erro de disco: S4.

---

## 11) Estratégia de políticas centralizadas

## 11.1 Hierarquia de escopo

1. Global do tenant
2. Grupo de dispositivos
3. Dispositivo específico

Regra de precedência: **mais específico vence**.

## 11.2 Conteúdo de política

- limiares dinâmicos por perfil de máquina
- catálogo de ações permitidas
- ações que exigem aprovação humana
- janelas de manutenção
- limites de frequência de auto-ação (anti-loop)

## 11.3 Versionamento e rollout

- políticas versionadas e assinadas
- rollout progressivo (canary por grupo)
- rollback de política em 1 clique no painel

---

## 12) Plano por fases (sem implementar tudo agora)

## Fase 0 — Fundacional (curto prazo)
- Congelar contrato de eventos e modelo de política.
- Formalizar boundary entre autonomia local e aprovação humana.
- Definir baseline de segurança (identidade de agente e assinatura).

## Fase 1 — Plataforma mínima integrada
- Servidor API de ingestão + registry + autenticação básica.
- Agente com outbox local e envio near-real-time.
- Painel inicial: inventário, alertas, timeline de ações.

## Fase 2 — Governança operacional
- Policy service por tenant/grupo/dispositivo.
- Auditoria completa e relatórios de conformidade.
- Motor de correlação para recorrência e tendência.

## Fase 3 — Autonomia avançada
- Ações condicionadas por confiança e contexto histórico.
- Recomendações técnicas automatizadas (upgrade/manutenção).
- Integrações externas (ticketing, notificação, SIEM).

---

## 13) Recomendação objetiva para próximo passo

Próxima entrega deve ser o **“Contrato de Plataforma v1”** contendo:
1. OpenAPI inicial (ingestão, registro, políticas, auditoria)
2. Schemas de eventos (JSON Schema)
3. Política v1 (formato + assinatura + precedência)
4. Modelo SQL inicial (migrations)
5. Fluxo de autenticação de agente ponta a ponta (bootstrap → mTLS)

Isso cria a base certa para evoluir de monitor local para plataforma operacional autônoma multi-tenant.
