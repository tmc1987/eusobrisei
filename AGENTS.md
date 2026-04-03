# AGENTS.md

Diretrizes obrigatórias para contribuições neste repositório:

1. `contracts/` é a **fonte de verdade** para comunicação entre agente e servidor.
2. Preservar o `realtime_agent` atual enquanto a migração acontece de forma incremental.
3. Priorizar **fatias verticais executáveis** antes de expandir escopo.
4. Sempre manter os testes passando.
5. Toda integração nova deve ter documentação de execução local.
6. Toda funcionalidade temporária de desenvolvimento deve ser marcada claramente como **provisória**.
7. Não implementar ações remotas perigosas.
8. Priorizar segurança operacional, auditoria, resiliência offline e isolamento por tenant.
