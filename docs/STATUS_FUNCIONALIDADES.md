# STATUS DE FUNCIONALIDADES — Dashboards Resulth / Cetel

> Documento de rastreamento: compara tudo que o cliente pediu no protótipo
> (`docs/PROTOTIPO_SOLICATAÇÕES_CETEL.md`) com o que está implementado.
> **Última atualização:** 2026-06-25 — reescrito após auditoria completa de
> código (não apenas registro manual); os módulos Estoque/Compras/Alertas
> estavam marcados ❌ desde 2026-06-10, mas já foram implementados por
> completo há várias sessões — este documento estava desatualizado.

---

## Legenda
| Símbolo | Significado |
|---------|-------------|
| ✅ | Implementado e funcional (verificado no código) |
| ⚠️ | Parcialmente implementado / implementado com ressalva |
| ❌ | Não implementado |

---

## REQUISITOS GERAIS (aplicam-se a todos os módulos)

| Funcionalidade | Status | Onde | Observação |
|----------------|--------|------|------------|
| Exportação Excel (.xlsx) | ✅ | `components/widgets/exportacao.py` | `core/export.py::gerar_excel` |
| Exportação PDF | ✅ | `components/widgets/exportacao.py` | `core/export.py::gerar_pdf` |
| Botão de impressão | ✅ | `components/print_btn.py` | CSS `@media print` |
| Impressão com data de emissão | ✅ | `core/export.py::_PDF.header` | |
| Impressão com período analisado | ✅ | `core/export.py::_PDF.header` | |
| Drill-down progressivo | ✅ | Todos os módulos | `@st.dialog`, ver seção por módulo |
| Filtro — Período/Empresa/Vendedor/Cliente/Fornecedor/Grupo/Marca (7) | ✅ | `components/sidebar_filtros.py` | `_TODOS` lista os 7 |
| Comparativo: mês atual x mês anterior | ✅ | Financeiro e Comercial | |
| Comparativo: mês atual x mesmo mês ano anterior | ✅ | Financeiro e Comercial | |
| Comparativo: acumulado do ano | ✅ | `core/domain/financeiro.py::get_acumulado_ano` | |
| Comentários gerenciais | ✅ | `components/widgets/comentarios.py` | DuckDB, entra no PDF/Excel |
| Performance / consultas otimizadas | ✅ | — | Cache 5–30min, `FIRST N`, índices preservados (ver `MANUAL_TECNICO.md`) |

---

## TELA INICIAL

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Tela inicial com módulos disponíveis | ✅ | `app.py` — widget de navegação `ger_modulos_nav` + Busca Global |
| Data/hora da última atualização | ✅ | `components/freshness.py` — mostra o horário real do último fetch (cache miss), não a hora de renderização da página |
| Sistema de Favoritos / Adicionar/remover dashboards | ✅ | Painel de indicadores: escolha quais widgets (de ~65 disponíveis, de todos os módulos) aparecem na Home, com checkbox — `app.py` + `core/dashboard/registry.py` |
| Reorganizar dashboards | ✅ | Grid arrastável (`streamlit-elements` / `dashboard.Grid`) — arraste pelo cabeçalho do card |
| Redimensionar dashboards | ✅ | Mesmo grid — redimensiona pelo canto do card |
| Salvar preferências do usuário | ✅ | Seleção de widgets e layout (x/y/w/h) salvos em `preferencias_home` (DuckDB) |

**Nota:** indicadores dentro do grid usam Nivo/MUI em vez de Plotly/AgGrid (única forma de ter conteúdo de verdade dentro de um card arrastável nesta lib) — visual ligeiramente diferente do resto do app nessa área específica. Busca Global e Relatório Executivo continuam como seções fixas (não arrastáveis) por usarem `st.selectbox`/`st.download_button` nativos, que não funcionam dentro do grid.

---

## MÓDULO FINANCEIRO — `pages/01_Financeiro.py` + `core/domain/financeiro.py`

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Saldo individual por conta | ✅ | `get_saldo_bancario()` |
| Saldo consolidado | ✅ | `get_kpis()["saldo_bco"]` |
| Evolução últimos 30 dias | ✅ | **Bug corrigido nesta auditoria**: `_SQL_EVOLUCAO_SALDO` filtrava `CODEMPRESA='01'` (0 linhas) em vez de `'00'` (92 linhas reais) — o gráfico nunca aparecia. Corrigido em `core/data/repositories/financeiro_repo.py` |
| Recebimentos/Pagamentos previstos + projeção 7/15/30/60/90d | ✅ | `fluxo_projetado()` |
| Drill-down Fluxo → Dia → Recebimentos/Pagamentos → Documento → Título | ✅ | `dialog_fluxo()` |
| AR: valor vencido, qtd títulos, ranking inadimplentes, faixas 1-30/31-60/61-90/90+ | ✅ | `aging_por_cliente()`, `_classifica_faixa_ar()` |
| AP: vencimentos 7/15/30/60/90d, separação por fornecedor | ✅ | `ap_por_fornecedor()` |
| Inadimplência: valor vencido + evolução | ✅ | `get_evolucao_inadimplencia()` |
| Posição de Caixa + Capital Operacional (Caixa+Receber+Estoque−Pagar) | ✅ | `get_kpis()["capital_op"]` — fórmula exata do requisito |
| **Extras não pedidos:** PMR/PMP, projeção acumulada (running balance), concentração de inadimplência, mapa de calor de vencimentos, alertas inteligentes | ✅ | Todos implementados e em uso |

---

## MÓDULO COMERCIAL — `pages/02_Comercial.py` + `core/domain/comercial.py`

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Meta do mês + indicadores (total faturado, % meta, projeção fechamento) | ✅ | `get_meta_mes()`, `get_projecao_fechamento_mes()` |
| **Filtro/relatório por forma de pagamento (Dinheiro/PIX/Débito/Crédito+parcelas)** | ✅ | Aba "💳 Forma de Pagamento" em Comercial — `get_faturamento_por_forma_pgto()`. Liga `PEDIDOC` a `MOVIREC.CODFORMAPGTO` via `NFSAIDC`/`DOCUREC.NUMDOCORIG` (decodificado), com **rateio proporcional** quando um pedido foi liquidado em mais de uma forma. Cobertura ~52% do faturamento (o resto é convênio/título em aberto, fora do rateio por não ter pedido associado de forma direta). Códigos do ERP (`03`, `07`, `CK`...) são mapeados para nomes pelo usuário, salvos no DuckDB. |
| Faturamento por dia/semana/quinzena/mês + comparativos | ✅ | `get_faturamento_periodo()` |
| Ticket médio geral e por vendedor | ✅ | `get_ticket_medio()` |
| Top 10 clientes por faturamento e por lucro bruto | ✅ | `get_top_clientes_faturamento/lucro()` |
| Clientes sem comprar 30/60/90/180 dias | ✅ | `get_clientes_sem_comprar()` |
| Top 10 clientes com queda de compras (média 6m, últimos 30d, % queda, valor perdido) | ✅ | `get_clientes_queda_compras()` — todas as 4 colunas pedidas presentes |
| Concentração de faturamento — clientes (top 10) e produtos (top 20) | ✅ | `get_concentracao_clientes/produtos()` |
| **Sazonalidade 24 meses: Faturamento + Compras + Margem Bruta** | ⚠️ | **Só Faturamento implementado.** `get_sazonalidade()` tem comentário explícito no código dizendo que Compras/Margem ficariam "para quando o módulo Compras existir" — mas o módulo Compras já existe há várias sessões e isso nunca foi revisitado. Gap real, fechável com dados já disponíveis em `core.domain.compras`. |
| Drill-down Faturamento → Cliente → Pedido → Itens | ✅ | `dialog_cliente()` |
| **Extras não pedidos:** funil de pedidos, ranking de vendedores, descontos concedidos, clientes novos×recorrentes, curva ABC formal | ✅ | Todos implementados |

---

## MÓDULO PRODUTOS — incorporado em `pages/02_Comercial.py` (Top Clientes/Produtos) e `pages/03_Estoque.py` (Top Produtos)

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Top 10 por quantidade vendida | ✅ | `core/domain/estoque.py::get_top_produtos()` |
| Top 10 por faturamento | ✅ | idem |
| Top 10 por lucro bruto (Venda − CMV) | ✅ | idem |
| Produtos sem venda — filtros 30/60/90/180/365 dias, top por valor parado | ✅ | `get_estoque_parado()` + `get_produtos_sem_venda()` |

---

## MÓDULO ESTOQUE — `pages/03_Estoque.py` + `core/domain/estoque.py`

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Qtd. de SKUs, qtd. física, valor de custo, valor de venda | ✅ | `get_kpis_estoque()` |
| Estoque parado — faixas 30/60/90/180/365 — SKUs/qtd física/custo/**venda** | ✅ | **Coluna "Valor de venda" estava ausente do KPI e da tabela de detalhamento — corrigido nesta auditoria** (`pages/03_Estoque.py`) |
| Produtos abaixo do mínimo / sem estoque (ruptura) | ✅ | `get_controle_operacional()` |
| Curva ABC de estoque (A/B/C, SKUs, valor investido, % do total) | ✅ | `get_curva_abc_estoque()` + `core/domain/classificacao.py` (regra compartilhada com Comercial) |
| Giro de estoque por grupo (grupo, valor médio, valor vendido, giro) | ✅ | `get_giro_por_grupo()` |
| Drill-down Estoque Parado → Grupo → Produto → Movimentações | ✅ | `dialog_movimentacoes()` |

---

## MÓDULO COMPRAS — `pages/04_Compras.py` + `core/domain/compras.py`

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Compras do mês + evolução (12 meses) | ✅ | `get_historico_compras(13)` — busca 13 meses para garantir 12 meses fechados completos (mês corrente é parcial) |
| Top fornecedores: compras, vendas geradas, lucro bruto, estoque, parado, participação | ✅ | `get_rentabilidade_fornecedor()` — as 6 métricas pedidas |
| Dependência de fornecedores (participação individual + top 10) | ✅ | `get_compras_por_fornecedor()` |
| Rentabilidade por fornecedor (compras/vendas/lucro/margem%) | ✅ | idem |
| Top 10 fornecedores por lucro bruto gerado | ✅ | ordenação por `LUCRO_BRUTO` em `get_rentabilidade_fornecedor()` |
| Alertas: produtos sem giro, estoque parado por fornecedor | ✅ | `get_produtos_sem_giro()`, `get_estoque_parado_por_fornecedor()` |
| Drill-down Fornecedor → NF de entrada → Itens | ✅ | `dialog_fornecedor()` (a especificação cita "Pedido de Compra"; o ERP não tem pedido de compra formal — usa-se a NF de entrada, documento real disponível) |

---

## MÓDULO ALERTAS — `pages/05_Alertas.py` + `core/domain/alertas.py`

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Produtos sem venda > 180 dias | ✅ | `_alerta_produtos_nunca_vendidos()` |
| Produtos abaixo do mínimo / sem estoque | ✅ | `_alerta_abaixo_minimo()`, `_alerta_ruptura()` |
| Clientes com atraso > 90 dias | ✅ | regra central financeira (`get_alertas_financeiro`) |
| Clientes com queda de compras | ✅ | `_alerta_clientes_queda_compras()` |
| Produtos comprados sem giro | ✅ | `_alerta_produtos_sem_giro()` |
| Estoque parado por fornecedor | ✅ | `_alerta_estoque_parado_fornecedor()` |
| Drill-down direto a partir de cada alerta | ⚠️ | Os links levam à **página** do módulo certo (`st.page_link`), mas não pulam direto para a aba/registro específico do alerta — o usuário ainda precisa navegar manualmente até o item exato |
| **Extra não pedido:** alerta de saúde do próprio sistema (snapshot diário atrasado) | ✅ | `_alerta_sistema` — adicionado nesta sessão |

---

## Resumo por módulo (recontado nesta auditoria)

| Módulo | Itens do pedido original | ✅ | ⚠️ | ❌ |
|--------|---------------------------|----|----|----|
| Requisitos Gerais | 13 | 13 | 0 | 0 |
| Tela Inicial | 6 | 6 | 0 | 0 |
| Financeiro | ~30 | 30 | 0 | 0 |
| Comercial | ~18 | 17 | 1 | 0 |
| Produtos | 4 | 4 | 0 | 0 |
| Estoque | 7 | 7 | 0 | 0 |
| Compras | 7 | 7 | 0 | 0 |
| Alertas | 8 | 7 | 1 | 0 |
| **Total** | **~93** | **91** | **2** | **0** |

A versão de 2026-06-10 registrava 64% de conclusão porque 4 módulos inteiros (Estoque, Compras, Produtos, Alertas) ainda não existiam naquela data. A Tela Inicial passou de "home fixa configurável" para um painel de widgets arrastável/redimensionável (`app.py` + `core/dashboard/registry.py`, ~65 indicadores disponíveis de todos os módulos), e o filtro por forma de pagamento foi implementado com rateio proporcional. Resta apenas a Sazonalidade de Compras/Margem Bruta (⚠️) como gap conhecido.
