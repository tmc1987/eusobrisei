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
- Classificação operacional de resposta local por ação: `resolved`, `mitigated`, `failed`.
- Supressão de autoação ineficaz recorrente para evitar loops operacionais.
- Recomendação humana explícita quando mitigação local não basta.
- Estratégia inteligente por recorrência/causa provável:
  - começa com mitigação conservadora (`throttle`)
  - em recorrência processual pode escalar para `restart_process` (quando permitido)
  - em pressão estrutural recorrente aplica guardrail (`thermal_protect`) e prioriza escalonamento humano
- Máquina de estado de incidentes para consolidar recorrência operacional por assinatura:
  - estados: `open` → `mitigating` → `stabilized` / `escalated`
  - inclusão de `incident_id` estável, tempo aberto e contagem de falhas no contexto de alerta/auditoria
- Ranking dinâmico local de estratégias por efetividade real (por causa provável/recurso):
  - compara `throttle_top_cpu_process`, `restart_process` e `thermal_protect`
  - ajusta a próxima ação com base no histórico local de resultados (`resolved`, `mitigated`, `failed`)
- SLO operacional de remediação enviado no `post_state` da auditoria:
  - `% estabilizados sem intervenção humana`
  - `tempo médio para estabilizar`
  - `% escalados com evidência completa`
- Playbooks por classe de processo (maturidade operacional):
  - `critical_service`: somente ações conservadoras e escalonamento humano antecipado
  - `user_app`: throttling/restart/thermal com riscos e rollback documentados
  - `protected_process`: bloqueio de ações invasivas locais
  - metadados de playbook (`classe`, `ações permitidas`, `risco`, `rollback`, `documentação`) anexados na auditoria
- Orçamento de ação por incidente:
  - limite de tentativas locais por incidente (`actions.max_attempts_per_incident`)
  - incidente escala automaticamente quando o orçamento é esgotado
  - estado, tentativas usadas e orçamento remanescente seguem no contexto de alerta/auditoria

## Política central aplicada sobre config local

- `thresholds`
- `actions.enabled`
- `actions.safe_mode`
- `actions.cooldown_seconds`
- `processes.restart_allowlist`

Se política remota não estiver disponível, agente continua com configuração local.

## Maturidade operacional local (atual)

- cooldown por alvo de ação (evita repetição excessiva)
- supressão após recorrência ineficaz
- contexto operacional/evidências no `post_state` de auditoria
- recomendação humana em caso de falha persistente
- diagnóstico de causa provável com top processos (CPU/RAM) antes de escalar recomendação estrutural
- evidência de limitação estrutural somente após recorrência + mitigação local insuficiente
- diagnóstico também expandido para disco (top processos de I/O e causa provável)

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

## Testes locais

```bash
cd realtime_agent
python -m unittest discover -s tests -p 'test_*.py'
```

## Provisório desta fase

- Bootstrap e auth bearer simplificados para desenvolvimento.
- **mTLS ainda não implementado**.
