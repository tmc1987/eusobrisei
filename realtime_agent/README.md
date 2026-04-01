# Realtime Monitoring Agent (Windows MVP)

Projeto executável em Python para monitoramento em tempo real com análise, regras e auto-ações seguras/reversíveis.

## O que já está implementado no MVP

- Coleta real de:
  - uso de CPU
  - uso de RAM
  - uso de disco
  - temperatura (quando disponível via `psutil`)
  - processos e processos travados no Windows (`Responding = false` via PowerShell)
- Geração de alertas em log (`logs/agent.log`)
- Motor de regras com decisões automáticas
- Ações automáticas seguras:
  - redução temporária de prioridade do processo mais pesado (com rollback automático)
  - mitigação térmica básica (Windows: `powercfg /SETACTIVE SCHEME_BALANCED`)
  - reinício de processo (somente quando explicitamente mapeado em `config.json`)

## Stubs documentados

- Em sistemas não-Windows, detecção de processo travado retorna vazio (stub seguro).
- Nem todo hardware expõe sensores de temperatura via `psutil`; quando indisponível, o valor é `null`.
- Reinício automático de processos depende de mapeamento explícito em `processes.restart_commands`.

## Estrutura

```
realtime_agent/
  main.py
  config.json
  requirements.txt
  README.md
  agent/
    __init__.py
    config.py
    logger.py
    collector.py
    analyzer.py
    rules.py
    actions.py
  tests/
    test_analyzer.py
    test_rules.py
```

## Execução

```bash
cd realtime_agent
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
python main.py --config config.json
```

Rodar apenas 1 ciclo:

```bash
python main.py --config config.json --once
```

## Testes mínimos

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## Segurança operacional

- Processos críticos listados em `critical_names` **não** são reiniciados automaticamente.
- A principal auto-ação do MVP é reversível (rollback automático de prioridade).
- Falhas de coleta/análise/ação são capturadas e logadas sem derrubar o loop principal.
