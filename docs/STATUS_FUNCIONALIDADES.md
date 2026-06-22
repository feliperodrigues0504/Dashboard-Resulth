# STATUS DE FUNCIONALIDADES — Dashboards Resulth / Cetel

> Documento de rastreamento: compara tudo que o cliente pediu no protótipo
> com o que foi implementado. Atualizar a cada sessão de desenvolvimento.
> **Última atualização:** 2026-06-10

---

## Legenda
| Símbolo | Significado |
|---------|-------------|
| ✅ | Implementado e funcional |
| 🔧 | Em implementação (sprint atual) |
| ⏳ | Planejado — próxima sprint |
| ❌ | Não iniciado |
| 🔴 | Bloqueado / depende de dado externo |
| 💡 | Sugestão própria (não estava no protótipo) |

---

## REQUISITOS GERAIS (aplicam-se a todos os módulos)

| Funcionalidade | Status | Onde | Observação |
|----------------|--------|------|------------|
| Exportação Excel (.xlsx) | ✅ | Todos os módulos | Botão 📥 em cada aba |
| Exportação PDF | ✅ | Todos os módulos | Botão 📄 em cada aba |
| Botão de impressão | ✅ | Todos os módulos | Botão 🖨️ no topo |
| Impressão com data de emissão | ✅ | CSS media print | Incluído no cabeçalho do PDF |
| Impressão com período analisado | ✅ | CSS media print | Incluído no cabeçalho do PDF |
| Drill-down progressivo | ✅ | Todos os módulos | Modal (@st.dialog) com níveis |
| Filtro — Período | ✅ | Sidebar centralizado | components/sidebar_filtros.py (UI) + core/domain/filtros.py (lógica) |
| Filtro — Empresa | ✅ | Sidebar centralizado | components/sidebar_filtros.py (UI) + core/domain/filtros.py (lógica) |
| Filtro — Vendedor | ✅ | Sidebar centralizado | core/data/repositories/cadastros_repo.py → VENDEND |
| Filtro — Cliente | ✅ | Sidebar centralizado | core/data/repositories/cadastros_repo.py → CLIENTE |
| Filtro — Fornecedor | ✅ | Sidebar centralizado | core/data/repositories/cadastros_repo.py → FORNECE |
| Filtro — Grupo de Produto | ✅ | Sidebar centralizado | core/data/repositories/cadastros_repo.py → GRUPROD |
| Filtro — Marca | ✅ | Sidebar centralizado | core/data/repositories/cadastros_repo.py → CADFABR |
| Comparativo: mês atual x mês anterior | ✅ | Aba Comparativos | Via MOVIREC/MOVIPAG |
| Comparativo: mês atual x mesmo mês ano ant. | ✅ | Aba Comparativos | Via MOVIREC/MOVIPAG |
| Comparativo: acumulado do ano | ✅ | Aba Comparativos | Ano atual vs ano anterior |
| Comentários gerenciais | ✅ | Todos os módulos | DuckDB — aparece no PDF/Excel |
| Performance / consultas otimizadas | ✅ | — | Cache 15min, dados sob demanda |

---

## TELA INICIAL

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Tela inicial com módulos disponíveis | ✅ | app.py — cards por módulo |
| Status de cada módulo (disponível/dev) | ✅ | Badge colorido |
| Data/hora da última atualização | ❌ | Mostrar timestamp do último cache |
| Sistema de Favoritos | ❌ | Fase 6 do ROADMAP |
| Adicionar/remover dashboards | ❌ | Fase 6 do ROADMAP |
| Reorganizar dashboards | ❌ | Fase 6 do ROADMAP |
| Redimensionar dashboards | ❌ | Fase 6 — avaliar viabilidade Streamlit |
| Salvar preferências do usuário | ❌ | Fase 6 do ROADMAP |

---

## MÓDULO FINANCEIRO

### Saldo Bancário
| Funcionalidade | Status | Tabelas | Observação |
|----------------|--------|---------|------------|
| Saldo individual por conta | ✅ | MOVIBAN | Aba Posição de Caixa |
| Saldo consolidado | ✅ | MOVIBAN | KPI no topo |
| Evolução dos últimos 30 dias | ✅ | SALDOST | Gráfico de área |

### Fluxo de Caixa
| Funcionalidade | Status | Tabelas | Observação |
|----------------|--------|---------|------------|
| Recebimentos previstos | ✅ | DOCUREC | Aba Fluxo |
| Pagamentos previstos | ✅ | DOCUPAG | Aba Fluxo |
| Projeção 7 dias | ✅ | DOCUREC+DOCUPAG | Tabela e gráfico |
| Projeção 15 dias | ✅ | DOCUREC+DOCUPAG | Tabela e gráfico |
| Projeção 30 dias | ✅ | DOCUREC+DOCUPAG | Tabela e gráfico |
| Projeção 60 dias | ✅ | DOCUREC+DOCUPAG | Tabela e gráfico |
| Projeção 90 dias | ✅ | DOCUREC+DOCUPAG | Tabela e gráfico |
| Drill-down: Fluxo → Dia | ✅ | — | Modal |
| Drill-down: Dia → Recebimentos/Pagamentos | ✅ | — | Modal lado a lado |
| Drill-down: Recebimentos/Pagamentos → Documento | ✅ | — | Modal |
| Drill-down: Documento → Título (histórico) | ✅ | MOVIREC/MOVIPAG | Modal |
| **💡 Projeção de caixa acumulada (running balance)** | 🔧 | DOCUREC+DOCUPAG+MOVIBAN | Em implementação |

### Contas a Receber
| Funcionalidade | Status | Tabelas | Observação |
|----------------|--------|---------|------------|
| Valor total vencido | ✅ | DOCUREC | KPI + Aba AR |
| Quantidade de títulos vencidos | ✅ | DOCUREC | KPI |
| Ranking de clientes inadimplentes | ✅ | DOCUREC+CLIENTE | Tabela clicável |
| Faixa 1-30 dias | ✅ | DOCUREC | Aging |
| Faixa 31-60 dias | ✅ | DOCUREC | Aging |
| Faixa 61-90 dias | ✅ | DOCUREC | Aging |
| Acima de 90 dias | ✅ | DOCUREC | Aging |
| Drill-down: Cliente → Títulos | ✅ | DOCUREC | Modal |
| Drill-down: Título → Histórico | ✅ | MOVIREC | Modal |
| Drill-down: Título NF → Itens produto | ✅ | NFSAIDI | Modal (só TIPODOCTO=NF) |
| **💡 Concentração de inadimplência (top N = X%)** | 🔧 | DOCUREC | Em implementação |
| **💡 PMR — Prazo Médio de Recebimento** | 🔧 | MOVIREC | Em implementação |
| **💡 % Inadimplência / Faturamento** | ⏳ | DOCUREC+MOVIREC | Aguarda módulo Comercial |

### Contas a Pagar
| Funcionalidade | Status | Tabelas | Observação |
|----------------|--------|---------|------------|
| Vencimentos em 7 dias | ✅ | DOCUPAG | Aba AP |
| Vencimentos em 15 dias | ✅ | DOCUPAG | Aba AP |
| Vencimentos em 30 dias | ✅ | DOCUPAG | Aba AP |
| Vencimentos em 60 dias | ✅ | DOCUPAG | Aba AP |
| Vencimentos em 90 dias | ✅ | DOCUPAG | Aba AP |
| Separação por fornecedor | ✅ | DOCUPAG+FORNECE | Gráfico + tabela |
| Drill-down: Fornecedor → Títulos | ✅ | DOCUPAG | Modal |
| Drill-down: Título → Histórico | ✅ | MOVIPAG | Modal |
| **💡 PMP — Prazo Médio de Pagamento** | 🔧 | MOVIPAG | Em implementação |

### Inadimplência
| Funcionalidade | Status | Tabelas | Observação |
|----------------|--------|---------|------------|
| Valor vencido | ✅ | DOCUREC | KPI + Aba AR |
| Evolução da inadimplência | ✅ | DuckDB snap | Snapshot diário — acumula com tempo |
| **💡 Alertas de inadimplência crítica** | 🔧 | DOCUREC | Em implementação |

### Posição de Caixa
| Funcionalidade | Status | Tabelas | Observação |
|----------------|--------|---------|------------|
| Saldo Bancário Consolidado | ✅ | MOVIBAN | Aba Posição de Caixa |
| Contas a Receber em Aberto | ✅ | DOCUREC | Aba Posição de Caixa |
| Estoque ao Custo | ✅ | COMPPROD | Aba Posição de Caixa |
| Contas a Pagar em Aberto | ✅ | DOCUPAG | Aba Posição de Caixa |
| Capital Operacional (Caixa+Receber+Estoque−Pagar) | ✅ | — | Waterfall chart |
| **💡 Índice de Liquidez Corrente** | ⏳ | — | (AR+Caixa)/AP |

### Comparativos Históricos
| Funcionalidade | Status | Fonte | Observação |
|----------------|--------|-------|------------|
| Recebimentos por mês (13 meses) | ✅ | MOVIREC | Gráfico de barras |
| Pagamentos por mês (13 meses) | ✅ | MOVIPAG | Gráfico de barras |
| Acumulado do ano vs ano anterior | ✅ | MOVIREC+MOVIPAG | Cards com delta |
| Evolução da inadimplência (gráfico) | ✅ | DuckDB snap | Acumula dia a dia |
| Inadimplência aberta por mês de vencimento | ✅ | DOCUREC | Títulos ainda abertos |

### Funcionalidades Extra (💡 sugestão — não pedidas pelo cliente)
| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| **Alertas Inteligentes (painel visual)** | 🔧 | Caixa negativo 7d · AP amanhã · +90 dias |
| **Projeção de caixa acumulada** | 🔧 | Saldo projetado dia a dia com piso configurável |
| **PMR / PMP** | 🔧 | KPIs de prazo médio de recebimento e pagamento |
| **Concentração de inadimplência** | 🔧 | Top N clientes = X% do total vencido |
| **Mapa de calor de vencimentos** | 🔧 | Calendário com intensidade de vencimentos |
| **Limites/Metas configuráveis** | 🔧 | Piso de caixa, alerta de inadimplência |
| Timeline de relacionamento do cliente | ⏳ | Histórico de pagamentos por cliente |
| % Inadimplência / Faturamento | ⏳ | Aguarda módulo Comercial |
| Índice de Liquidez Corrente | ⏳ | (AR+Caixa)/AP |
| Eficiência de cobrança (% liquidados) | ⏳ | % dos vencidos que foram pagos no período |

---

## MÓDULO COMERCIAL
| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Meta comercial do mês | ✅ | |
| Filtro por forma de pagamento (Dinheiro/PIX/Cartão/Boleto) | ✅ | |
| Total faturado | ✅ | |
| Percentual da meta atingido | ✅ | |
| Projeção de fechamento do mês | ✅ | |
| Faturamento por dia/semana/quinzena/mês | ✅ | |
| Comparativo mês anterior | ✅ | |
| Comparativo mesmo mês ano anterior | ✅ | |
| Ticket médio geral | ✅ | |
| Ticket médio por vendedor | ✅ | |
| Top 10 clientes por faturamento | ✅ | |
| Top 10 clientes por lucro bruto | ✅ | |
| Clientes sem comprar 30/60/90/180 dias | ✅ | |
| Top 10 clientes com queda de compras | ✅ | |
| Concentração de faturamento por clientes | ✅ | |
| Concentração de faturamento por produtos | ✅ | |
| Sazonalidade 24 meses (faturamento/compras/margem) | ✅ | |
| Drill-down: Faturamento → Cliente → Pedido → Itens | ✅ | |
| **💡 Funil de Pedidos (taxa de conversão)** | ✅ | Aba Meta & Indicadores — `PEDIDOC` por status FATURADO |
| **💡 Ranking de Vendedores** | ✅ | Aba Faturamento — pandas sobre `df_fat`, zero SQL extra |
| **💡 Descontos Concedidos** | ✅ | Aba Faturamento — `PEDIDOI.DESCONTOVLR` por vendedor/cliente |
| **💡 Clientes Novos vs Recorrentes** | ✅ | Aba Clientes — cruza `MIN(DATAFATURA)` histórica com período |
| **💡 Curva ABC (Pareto formal)** | ✅ | Aba Concentração — classes A/B/C sobre concentração existente |

## MÓDULO PRODUTOS
| Funcionalidade | Status |
|----------------|--------|
| Top 10 por quantidade vendida | ❌ |
| Top 10 por faturamento | ❌ |
| Top 10 por lucro bruto | ❌ |
| Produtos sem venda 30/60/90/180/365 dias | ❌ |

## MÓDULO ESTOQUE
| Funcionalidade | Status |
|----------------|--------|
| Qtd. de SKUs | ❌ |
| Qtd. física em estoque | ❌ |
| Valor de custo | ❌ |
| Valor de venda | ❌ |
| Estoque parado (faixas 30/60/90/180/365 dias) | ❌ |
| Produtos abaixo do estoque mínimo | ❌ |
| Produtos sem estoque (ruptura) | ❌ |
| Curva ABC de estoque (A/B/C) | ❌ |
| Giro de estoque por grupo de produtos | ❌ |
| Drill-down: Estoque parado → Grupo → Produto → Movimentações | ❌ |

## MÓDULO COMPRAS
| Funcionalidade | Status |
|----------------|--------|
| Compras do mês | ❌ |
| Evolução das compras (12 meses) | ❌ |
| Top fornecedores por relevância | ❌ |
| Dependência de fornecedores | ❌ |
| Rentabilidade por fornecedor | ❌ |
| Top 10 fornecedores por lucro bruto gerado | ❌ |
| Alertas de compras (sem giro, estoque parado) | ❌ |
| Drill-down: Fornecedor → Pedido de Compra → Itens | ❌ |

## MÓDULO ALERTAS
| Funcionalidade | Status |
|----------------|--------|
| Produtos sem venda acima de 180 dias | ❌ |
| Produtos abaixo do estoque mínimo | ❌ |
| Produtos sem estoque | ❌ |
| Clientes com atraso superior a 90 dias | ❌ |
| Clientes com queda de compras | ❌ |
| Produtos comprados sem giro | ❌ |
| Estoque parado por fornecedor | ❌ |
| Drill-down direto a partir de cada alerta | ❌ |

---

## Resumo por módulo

| Módulo | Pedido | Implementado | Extra 💡 | % (pedido) |
|--------|--------|--------------|----------|------------|
| Req. Gerais | 16 | 16 | — | 100% |
| Tela Inicial | 8 | 2 | — | 25% |
| Financeiro (cliente) | 28 | 28 | — | 100% |
| Financeiro (extra 💡) | — | — | 5 em impl. | — |
| Comercial (cliente) | 19 | 19 | — | 100% |
| Comercial (extra 💡) | — | — | 5 | — |
| Produtos | 4 | 0 | — | 0% |
| Estoque | 10 | 0 | — | 0% |
| Compras | 8 | 0 | — | 0% |
| Alertas | 8 | 0 | — | 0% |
| **Total cliente** | **101** | **65** | **10+** | **64%** |
