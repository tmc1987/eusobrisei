# web-console (Painel Técnico read-only + gestão de policies dev)

Painel técnico simplificado e profissional, em tema solicitado:
- fundo preto
- tipografia em azul
- visual focado em operação
- sem ações remotas perigosas
- linguagem simples e objetiva para clientes não técnicos

## O que aparece no painel

- cards de visão rápida com termos comerciais claros
- problemas detectados agrupados por recorrência (menos ruído)
- problema traduzido para linguagem simples
- recomendação objetiva de ação por tipo de problema e recorrência
- autoações com resultado, eficácia e próximo passo

## Endpoints usados

- `/v1/overview`
- `/v1/devices`
- `/v1/alerts/active`
- `/v1/audit/actions`

## Rodar localmente

```bash
cd web-console
python -m http.server 5500
```

Abra: `http://127.0.0.1:5500/index.html`

Configuração local esperada:
- API em `http://127.0.0.1:8080` (default via `localStorage.api_base` quando definido).
- Painel servido em `http://127.0.0.1:5500`.
