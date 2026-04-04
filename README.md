# eusobrisei

Monorepo em evolução incremental para plataforma cliente-servidor.

## Estado atual

- `realtime_agent/`: agente local preservado.
- `server/`: persistência SQLite + API operacional de leitura + recomendações técnicas explicáveis.
- `web-console/`: painel operacional com visual executivo, gestão de policies de desenvolvimento e foco em decisão rápida.

## Passo a passo local

1. Subir servidor:
```bash
export SERVER_DB_PATH=server/data/dev.db
export SERVER_BOOTSTRAP_TOKEN=dev-bootstrap-token
cd server
python main.py
```

2. Cadastrar/editar policy via web-console (`/v1/policies*`) ou endpoint legado `/v1/dev/policies`.

3. Rodar agente:
```bash
cd realtime_agent
python main.py --config config.json
```

4. Subir painel:
```bash
cd web-console
python -m http.server 5500
```

5. Abrir painel:
- `http://127.0.0.1:5500/index.html`

## Sobre recomendações

- Regras heurísticas e explicáveis.
- Não geram autoações.
- Servem de apoio à decisão humana.

## Limites desta fase

- Sem login/autenticação forte do painel.
- Sem ações remotas perigosas.
- Sem mTLS.

## Fluxo de gestão de policies (fase atual)

- Criar: `POST /v1/policies`
- Editar: `PUT /v1/policies/{policy_id}`
- Desativar: `POST /v1/policies/{policy_id}/disable`
- Visualizar efetiva:
  - `GET /v1/policies/effective/{agent_id}`
  - `GET /v1/policies/effective/device/{device_id}`
- Verificar auditoria: `GET /v1/policies/audit`

> Provisório de desenvolvimento: sem login complexo; agente preserva fallback local quando necessário.
