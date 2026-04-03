# Fluxo de Autenticação de Agente (V1)

## Objetivo
Estabelecer identidade forte para cada agente, com rotação e revogação controladas.

## Fluxo completo (V1)

1. **Provisionamento humano (pré-boot):**
   - Técnico gera `activation_token` por dispositivo no servidor.
   - Token com TTL curto (ex.: 15 min) e uso único.

2. **Bootstrap do agente:**
   - Agente chama `POST /v1/agents/bootstrap` com token + metadados.
   - Servidor valida token, cria/associa `tenant/device/agent`.

3. **Credencial inicial:**
   - Servidor retorna `access_token` de curta duração.
   - Se mTLS habilitado, retorna material de certificado inicial (`mtls.cert_pem` + `ca_pem`).

4. **Comunicação operacional:**
   - Requisições posteriores usam `Authorization: Bearer` + `X-Agent-Id`.
   - `FUTURO`: exigir mTLS obrigatório para todos os agentes em produção.

5. **Rotação:**
   - Token/credencial renovados periodicamente.
   - Certificado revogado em comprometimento.

6. **Revogação imediata:**
   - Alterar `agents.auth_status = revoked`.
   - API passa a rejeitar chamadas com aquele agente.

## Regras mínimas

- Toda chamada do agente deve ter `X-Request-Id`.
- Chamadas de escrita devem ter `Idempotency-Key`.
- Clock skew tolerado: 120s.
- Rejeitar replay de requisições já idempotentes com payload divergente.
