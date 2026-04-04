# Agente de Monitoramento Inteligente em Tempo Real (Windows)

## Objetivo
Criar um agente local (com opção de console web) para **verificar, medir, prevenir e auto-corrigir** falhas críticas do Windows: tela azul (BSOD), travamentos, gargalos de desempenho e degradação progressiva.

> **Nota de pesquisa:** não existe um ranking oficial único dos “20 maiores problemas” publicado pela Microsoft para todas as máquinas. A lista abaixo prioriza os incidentes mais recorrentes em suporte técnico corporativo e doméstico, com base em códigos de bugcheck, WER/Event Viewer e padrões clássicos de degradação de performance.

---

## 1) Os 20 maiores problemas para monitorar e auto-resolver

## A. Tela azul (BSOD) e falhas críticas de kernel

1. **0x9F DRIVER_POWER_STATE_FAILURE**  
   - Causa típica: driver que não conclui IRP de energia (suspender/retomar/desligar).  
   - Coleta: Event ID 1001 + dump + mudanças de energia/driver.  
   - Auto-ação: atualizar/rollback driver problemático; bloquear suspensão híbrida em perfis instáveis.

2. **0x133 DPC_WATCHDOG_VIOLATION**  
   - Causa típica: latência DPC/ISR alta (storage, rede, chipset, firmware).  
   - Coleta: ETW de DPC/ISR, fila de I/O, driver stack.  
   - Auto-ação: atualização de driver/firmware de NVMe/chipset/rede; ajuste de plano de energia.

3. **0x7E SYSTEM_THREAD_EXCEPTION_NOT_HANDLED**  
   - Causa típica: exceção em thread de sistema (driver ou memória).  
   - Coleta: stack do dump + módulo culpado.  
   - Auto-ação: quarentena de driver recém-instalado; ponto de restauração.

4. **0x3B SYSTEM_SERVICE_EXCEPTION**  
   - Causa típica: exceção na transição user→kernel.  
   - Coleta: dump + histórico de updates + integridade de arquivos.  
   - Auto-ação: DISM/SFC, rollback de patch/driver recente.

5. **0x1A MEMORY_MANAGEMENT**  
   - Causa típica: corrupção de memória, RAM instável, pagefile/CRC.  
   - Coleta: padrões de erro de memória, ECC (quando houver), WHEA.  
   - Auto-ação: agenda de diagnóstico de memória + reduzir overclock/XMP agressivo.

6. **0x50 PAGE_FAULT_IN_NONPAGED_AREA**  
   - Causa típica: referência inválida em memória não paginada (driver/RAM).  
   - Coleta: call stack + módulo + frequência por uptime.  
   - Auto-ação: rollback do driver + teste de RAM.

7. **0x124 WHEA_UNCORRECTABLE_ERROR**  
   - Causa típica: erro de hardware (CPU, VRM, RAM, PCIe, térmico).  
   - Coleta: WHEA-Logger, sensores térmicos/energia, firmware BIOS/UEFI.  
   - Auto-ação: desabilitar OC, aplicar BIOS estável, limite térmico preventivo.

8. **0xEF CRITICAL_PROCESS_DIED**  
   - Causa típica: processo crítico do sistema terminado/corrompido.  
   - Coleta: dumps + integridade do SO + disco.  
   - Auto-ação: SFC/DISM, checagem de disco e restauração controlada.

9. **0x7A KERNEL_DATA_INPAGE_ERROR**  
   - Causa típica: falha de leitura de página (disco/controladora/cabo).  
   - Coleta: SMART, erros de disco, tempo de resposta de storage.  
   - Auto-ação: migração preventiva de dados + troca de caminho/driver de storage.

10. **0x7B INACCESSIBLE_BOOT_DEVICE**  
    - Causa típica: driver/controladora de boot incorreta, corrupção de boot.  
    - Coleta: eventos de boot, BCD, alterações de storage.  
    - Auto-ação: recuperação automática de boot e validação de driver de controladora.

## B. Travamentos, congelamentos e reinícios inesperados

11. **Kernel-Power Event ID 41 (reinício abrupto)**  
    - Causa típica: energia, superaquecimento, PSU, watchdog de hardware.  
    - Coleta: correlação com temperatura, carga e tensão.  
    - Auto-ação: perfil de proteção térmica + alerta de energia instável.

12. **Application Hang (Event ID 1002)**  
    - Causa típica: app sem resposta por lock, deadlock, I/O lento.  
    - Coleta: tempo de resposta por processo, thread wait chain.  
    - Auto-ação: reinício controlado de processo + coleta de diagnóstico pré-kill.

13. **LiveKernelEvent (ex.: GPU TDR 141/117)**  
    - Causa típica: timeout de GPU/driver gráfico.  
    - Coleta: WER + telemetria de GPU (clock, temperatura, driver).  
    - Auto-ação: fallback de driver conhecido estável, limitar boost agressivo.

14. **Congelamento por disco a 100% ativo**  
    - Causa típica: fila de I/O alta, latência excessiva, paginação pesada.  
    - Coleta: Avg. Disk sec/Read/Write, queue length, hard faults/sec.  
    - Auto-ação: ajuste de paginação, poda de serviços de background e checagem SMART.

15. **Travamento por driver de terceiros pós-update**  
    - Causa típica: incompatibilidade versão de driver x build do Windows.  
    - Coleta: baseline de drivers + janela de mudanças.  
    - Auto-ação: rollback automático do último driver alterado.

## C. Perda de desempenho contínua

16. **CPU persistentemente alta (>85% sustentado)**  
    - Causa típica: processo runaway, serviço mal comportado, loop.  
    - Coleta: % Processor Time por processo + duração.  
    - Auto-ação: limitação de prioridade + restart seguro de serviço.

17. **Pressão de memória (commit alto + hard faults)**  
    - Causa típica: memory leak, pouca RAM, paginação excessiva.  
    - Coleta: Available MBytes, Commit Limit, Hard Faults/sec.  
    - Auto-ação: reciclagem de processo vazando memória e recomendação de upgrade.

18. **Throttle térmico (CPU/GPU)**  
    - Causa típica: refrigeração insuficiente, pasta térmica, poeira.  
    - Coleta: temperatura, frequência efetiva, power limits.  
    - Auto-ação: perfil “cool-down” temporário e alerta de manutenção física.

19. **Latência de rede e perda de pacotes anormal**  
    - Causa típica: driver NIC, congestionamento local, DNS/roteador.  
    - Coleta: RTT/p95, retransmissões TCP, throughput real.  
    - Auto-ação: reset de pilha de rede e troca para DNS fallback.

20. **Startup degradado e serviços excessivos**  
    - Causa típica: inicialização pesada com apps/serviços desnecessários.  
    - Coleta: tempo de boot, tempo até desktop “responsivo”, impacto de startup.  
    - Auto-ação: política de inicialização inteligente por perfil de uso.

---

## 2) Arquitetura recomendada do agente (tempo real + inteligência)

1. **Coletor de Telemetria (1-5s):**  
   - Perf counters (CPU, RAM, disk, rede), Event Logs (System/Application), WER, sensores térmicos.
2. **Motor de Correlação:**  
   - Junta eventos por janela temporal (ex.: 15 min) e identifica causalidade provável (driver, hardware, software).
3. **Motor de Regras (determinístico):**  
   - Runbooks automáticos seguros (rollback, restart, DISM/SFC, limpeza, ajustes de energia).
4. **Camada de IA (classificação + anomalia):**  
   - Modelo de risco por equipamento (normalização por hardware/uso).  
   - Score de severidade (0–100) e probabilidade de recorrência.
5. **Orquestrador de Auto-Remediação:**  
   - Executa ações por nível de confiança (baixo = sugerir; médio = pedir confirmação; alto = auto-corrigir).
6. **Console e Auditoria:**  
   - Timeline de incidentes, causa raiz provável, ação aplicada, resultado e rollback disponível.

---

## 3) Estratégia de “segurança + desempenho + auto solução”

### Níveis de decisão
- **Nível 0 (observação):** só mede e aprende baseline (7-14 dias).
- **Nível 1 (assistido):** recomenda correções com 1 clique.
- **Nível 2 (automático seguro):** corrige sem intervenção em runbooks de baixo risco.
- **Nível 3 (automático crítico):** executa mitigação urgente (ex.: proteção térmica).

### Guardrails obrigatórios
- Snapshot/restore point antes de ações invasivas.
- Rollback automático se KPI piorar após correção.
- Lista de exclusão para apps críticos do cliente.
- Assinatura de scripts e trilha de auditoria completa.

---

## 4) Fontes técnicas prioritárias (base para implementação)

- Microsoft Learn – Bug Check Code Reference (catálogo de stop codes):  
  https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/bug-check-code-reference2
- Microsoft Learn – BugCheck 0x9F: DRIVER_POWER_STATE_FAILURE:  
  https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/bug-check-0x9f--driver-power-state-failure
- Microsoft Learn – BugCheck 0x133: DPC_WATCHDOG_VIOLATION:  
  https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/bug-check-0x133-dpc-watchdog-violation
- Microsoft Learn – BugCheck 0x7E: SYSTEM_THREAD_EXCEPTION_NOT_HANDLED:  
  https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/bug-check-0x7e--system-thread-exception-not-handled
- Microsoft Learn – BugCheck 0x3B: SYSTEM_SERVICE_EXCEPTION:  
  https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/bug-check-0x3b--system-service-exception
- Microsoft Learn – BugCheck 0x1A: MEMORY_MANAGEMENT:  
  https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/bug-check-0x1a--memory-management
- Microsoft Learn – BugCheck 0x124: WHEA_UNCORRECTABLE_ERROR:  
  https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/bug-check-0x124---whea-uncorrectable-error
- Microsoft Learn – Troubleshoot blue screen errors:  
  https://support.microsoft.com/windows/troubleshoot-blue-screen-errors

---

## 5) MVP em 30 dias

- **Semana 1:** coletor + baseline + inventário de hardware/driver.
- **Semana 2:** detecção dos 20 problemas + dashboard de risco.
- **Semana 3:** auto-remediação segura (10 runbooks iniciais).
- **Semana 4:** score de IA, auditoria, rollback e hardening.

### KPIs de sucesso
- Redução de BSOD (meta: -40% em 60 dias).
- Redução de tickets por lentidão/travamento (meta: -35%).
- MTTR (tempo médio para corrigir) abaixo de 15 min para incidentes básicos.

---

## 6) Próximo passo sugerido

Implementar um **PoC em agente Windows service** (Go, Rust ou .NET) com:
- coleta local,
- API local protegida,
- políticas remotas,
- e runbooks versionados.

Se quiser, na próxima etapa eu desenho o **projeto técnico completo (arquitetura + banco de eventos + esquema de regras + pseudo-código do motor de auto-correção)** pronto para desenvolvimento.
