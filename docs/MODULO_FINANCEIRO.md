# MÓDULO FINANCEIRO — Especificação e Estado Atual

> Documento vivo — atualizado a cada sprint.
> Para rastreamento completo ver `STATUS_FUNCIONALIDADES.md`.
> **Última atualização:** 2026-06-05

---

## Status geral

**100% dos requisitos do cliente implementados.**
Sprint atual: implementando 5 melhorias extras (sugestões de UX/análise).

---

## O que está implementado (requisitos do cliente)

| Bloco | Funcionalidades | Abas |
|-------|----------------|------|
| Saldo Bancário | Individual, consolidado, evolução 30d | Posição de Caixa |
| Fluxo de Caixa | Receber/Pagar previsto, projeção 7/15/30/60/90d | Fluxo de Caixa |
| Contas a Receber | KPIs, aging 4 faixas, ranking inadimplentes | Contas a Receber |
| Contas a Pagar | Por horizonte, por fornecedor | Contas a Pagar |
| Inadimplência | Valor vencido, evolução (snapshot diário) | AR + Comparativos |
| Posição de Caixa | Saldo + AR + Estoque − AP, waterfall | Posição de Caixa |
| Comparativos | Mensal (13 meses), acumulado do ano, YoY | Comparativos |
| Drill-down | Modal 3 níveis em AR, AP e Fluxo → até itens NF | Todas as abas |
| Filtros | Período, Empresa, Vendedor, Cliente, Fornecedor | Sidebar |
| Exportação | Excel (.xlsx), PDF formatado | Todas as abas |
| Impressão | Botão + CSS media print | Topo da página |
| Comentários | Campo por indicador/período, salvo no DuckDB | Todas as abas |

---

## Sprint atual — Melhorias de usabilidade e análise

### 1. Projeção de Caixa Acumulada (Running Balance)
**O quê:** Saldo projetado dia a dia (não só por horizonte).
**Fórmula:** `Saldo[d] = Saldo[d-1] + ΣAR_vence[d] - ΣAP_vence[d]`
**Visual:** Gráfico de linha com o saldo projetado + linha de piso mínimo (configurável).
**Alerta:** Área vermelha quando o saldo projetado cai abaixo do piso.
**Tabelas:** DOCUREC, DOCUPAG, MOVIBAN (saldo inicial)
**Onde na UI:** Nova seção na aba "Fluxo de Caixa", abaixo do gráfico atual.

### 2. Alertas Inteligentes
**O quê:** Painel de avisos automáticos no topo da página, antes dos KPIs.
**Tipos:**
- 🔴 Caixa projeta negativo em ≤ 7 dias
- 🟠 Títulos AP vencem em ≤ 24h (com valor total)
- 🔴 Clientes com atraso > 90 dias (qtd + valor)
- 🟡 Capital operacional abaixo do piso configurado
**Comportamento:** Cada alerta é clicável e navega para a aba/seção relevante.
**Dependência:** Piso configurável salvo na tabela `config_alertas` no DuckDB.

### 3. PMR e PMP (Prazos Médios)
**O quê:** KPIs de dias médios de recebimento e pagamento.
- **PMR:** Média dos dias entre `DT_VENCIMENTO` e `DT_MOVIMENTO (liquidação)` em MOVIREC
- **PMP:** Idem em MOVIPAG
**Janela:** Últimos 90 dias de liquidações.
**Visual:** 2 cards no topo da aba, com delta vs mês anterior.
**Interpretação:** PMR alto = clientes pagando tarde. PMP alto = empresa pagando tarde (ou negociando bem).

### 4. Concentração de Inadimplência
**O quê:** Quanto % do total vencido está concentrado nos top 3/5 clientes.
**Visual:** Gauge ou treemap + texto "Os 3 maiores concentram X% do total vencido".
**Risco:** Alta concentração = risco alto (depende de poucos clientes).
**Onde na UI:** Seção na aba "Contas a Receber", ao lado do gráfico de aging.

### 5. Mapa de Calor de Vencimentos
**O quê:** Calendário visual dos próximos 35 dias (5 semanas).
**Visual:** Grid 7×5 (dia da semana × semana), cor = total de vencimentos naquele dia.
- Verde/amarelo/vermelho: intensidade do vencimento
- Hover: valor de AR e AP no dia
**Onde na UI:** Nova aba "📅 Calendário" ou seção no Fluxo de Caixa.

---

## Configurações salvas no DuckDB

| Tabela | Campos | Uso |
|--------|--------|-----|
| `snap_inadimplencia` | data, valor_vencido, qtd, faixas | Evolução histórica — alimentada pelo snapshot diário |
| `comentarios` | modulo, indicador, periodo, texto | Comentários gerenciais por seção |
| `config_alertas` | chave, valor, descricao | Piso de caixa, limites de alerta (configurável pelo gestor) |

---

## Snapshot diário

**Tarefa agendada:** `Cetel_Snapshot_Inadimplencia` (Task Scheduler do Windows)
**Horário:** 08:00 diariamente
**Script:** `C:\Users\ferod\OneDrive\Desktop\Projeto-Cetel\snapshot_diario.bat`
**Log:** `logs/snapshot.log`
**Primeiro registro:** 2026-06-05 — R$ 291.791,16 vencidos

---

## Decisões técnicas registradas

| Decisão | Motivo |
|---------|--------|
| Dialect 1 do Firebird | Banco do cliente — sem `DATE` literal, sem window functions. Cálculos de datas feitos em pandas. |
| SITUACAO='1' em DOCUREC/DOCUPAG | Apenas títulos em aberto. Testado e confirmado. |
| MOVIBAN para saldo bancário | SALDOST tem saldo cumulativo histórico (não o atual). MOVIBAN + dedup por conta = saldo correto. |
| Snapshots no DuckDB | ERP não guarda histórico de inadimplência. Snapshot diário constrói a série temporal. |
| AgGrid para tabelas | Permite clique na linha para abrir o drill-down modal (st.dialog). |
| st.dialog para drill-down | Abre "telinha" sobre a página — UX mais limpo que expandir abaixo. |
| Filtros em session_state | Persistem entre páginas — usuário seta uma vez, todos os módulos respeitam. |

---

## Próximas melhorias planejadas (pós-sprint atual)

- **Timeline de relacionamento do cliente** — histórico de pontualidade nos últimos 12 meses
- **% Inadimplência / Faturamento** — aguarda módulo Comercial (precisamos do faturamento)
- **Índice de Liquidez Corrente** — (AR + Caixa) / AP
- **Eficiência de cobrança** — % dos vencidos que foram pagos no período
