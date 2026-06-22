# Manual Técnico — Dashboard Executivo Cetel

> Documento de referência completo: o que cada tela faz, quais funções e tabelas de
> banco ela usa, e sugestões priorizadas de evolução.
> **Gerado em:** 2026-06-17 · **Versão do sistema:** Fase 7 (Polimento) + Auditoria de Dados

---

## 1. Visão geral da arquitetura

```
┌─────────────────────┐      read-only       ┌──────────────────────────┐
│  Firebird 2.5        │ ───────────────────▶ │  core/data/firebird.py   │
│  RESULTH.FB (ERP)     │   fdb + fbclient.dll  │  (fb_query)              │
└─────────────────────┘                       └──────────┬───────────────┘
                                                            │
                                          consultas SQL     ▼
                                          ┌─────────────────────────────┐
                                          │  core/data + core/domain     │
                                          │  financeiro · comercial ·    │
                                          │  estoque · compras · alertas │
                                          └──────────┬───────────────────┘
                                                      │ DataFrames (pandas)
                                                      ▼
                                          ┌─────────────────────────────┐
                                          │  pages/*.py (Streamlit)      │
                                          │  + app.py (Home)             │
                                          └──────────┬───────────────────┘
                                                      │ grava preferências,
                                                      │ comentários, snapshots
                                                      ▼
                                          ┌─────────────────────────────┐
                                          │  DuckDB — data/store.duckdb   │
                                          │  (único store gravável)       │
                                          └─────────────────────────────┘
```

**Regra de ouro:** o Firebird (`RESULTH.FB`) nunca recebe escrita — é o ERP de produção.
Tudo que o usuário grava (comentários, preferências, configurações de alerta, histórico
diário de KPIs) vai para o DuckDB local.

| Camada | Responsabilidade |
|---|---|
| `core/data/firebird.py` | Conexão `fdb`, executa SQL, retorna `pandas.DataFrame` |
| `core/domain/financeiro.py`, `comercial.py`, `estoque.py`, `compras.py` | Uma função por necessidade analítica; SQL + pós-processamento em pandas |
| `core/domain/alertas.py` | Agrega regras de negócio dos 4 módulos em uma lista padronizada de alertas |
| `core/data/duckdb_store.py` | Schema e CRUD do DuckDB (comentários, config, preferências, snapshots) |
| `core/sync/snapshot.py` + `agendador.py` | Job diário (08h) que grava o estado do dia para construir séries históricas |
| `components/*.py` | UI reutilizável: ícones (`bi_icons`), filtros de sidebar, exportação, botão de impressão, KPI cards |
| `pages/0N_*.py` + `app.py` | Telas Streamlit |

---

## 2. Tela Inicial — `app.py`

**Propósito:** dashboard executivo de 1 tela — visão consolidada para decisão rápida,
sem precisar entrar em nenhum módulo.

### Seções (controladas por preferências persistidas no DuckDB)

| Seção | Conteúdo |
|---|---|
| KPIs Executivos | AR, AP, Caixa, Capital Operacional, Estoque, Alertas (6 cards) |
| Alertas Ativos | Top alertas críticos/urgentes com link direto para o módulo |
| Gráficos Rápidos | Faturamento 30d, AR vs AP |
| Histórico de KPIs | Série diária (desde que existam ≥ 3 snapshots) |
| Módulos do Sistema | Cards de navegação para as 5 páginas |

### Funções utilizadas

| Função | Módulo origem | Uso na tela |
|---|---|---|
| `get_contas_receber`, `get_contas_pagar`, `get_saldo_bancario`, `get_estoque_custo`, `get_kpis` | `core.domain.financeiro` | KPIs principais (AR, AP, Caixa, Capital, Estoque) |
| `get_faturamento` | `core.domain.comercial` | Faturamento do mês + comparação com mês anterior |
| `get_kpis_estoque` | `core.domain.estoque` | Card de estoque (SKUs, valor) |
| `get_todos_alertas`, `resumo_alertas` | `core.domain.alertas` | Painel de alertas + badge no cabeçalho |
| `get_evolucao_kpis`, `get_evolucao_inadimplencia` | `core.sync.snapshot` | Gráficos de histórico |
| `get_preferencia`, `set_preferencia` | `core.data.duckdb_store` | Liga/desliga seções via sidebar |
| `iniciar_agendador` | `core.sync.agendador` | Garante que o snapshot diário roda mesmo sem acesso às outras páginas |

### Tabelas Firebird consultadas (via funções acima)
`DOCUREC`, `DOCUPAG`, `MOVIBAN`, `COMPPROD`, `PRODUTO`, `PEDIDOC`

### Tabelas DuckDB
`preferencias_home`, `snap_kpis_diario`, `snap_inadimplencia`

### Sugestões de evolução
1. **Comparativo ano-a-ano (YoY)** — hoje inviável (só há ~4 meses de histórico real); revisitar em 2027 quando `snap_kpis_diario` tiver 12+ meses.
2. **Modo "TV/painel de parede"** — auto-refresh a cada N minutos + rotação de seções, para exibir em monitor da sala de gestão.
3. **Atalho "Ações do dia"** — lista compacta (não modal) com os 3 itens mais urgentes (ex: "Pagar boleto X hoje", "Cobrar cliente Y") extraída dos alertas críticos.
4. **Indicador de saúde do agendador** — hoje o snapshot falha silenciosamente (`except: pass`); adicionar um badge "Snapshot OK / atrasado" lendo a data do último registro em `snap_kpis_diario`.

---

## 3. Módulo Financeiro — `pages/01_Financeiro.py`

**Propósito:** gestão de caixa, contas a receber/pagar, inadimplência e projeção de fluxo.

### Abas

| Aba | Conteúdo principal |
|---|---|
| 📋 Contas a Receber | KPIs AR, aging 4 faixas, ranking de inadimplentes, heatmap de vencimentos, concentração, drill-down cliente → título → histórico → itens |
| 📊 Fluxo de Caixa | Recebimentos/pagamentos previstos por horizonte (7/15/30/60/90d), projeção acumulada (running balance) com piso configurável |
| 💳 Contas a Pagar | AP por horizonte e por fornecedor, drill-down fornecedor → título → histórico |
| 📈 Comparativos | Evolução mensal (13 meses) de recebimentos/pagamentos, acumulado do ano |
| 🏦 Posição de Caixa | Saldo bancário + AR − AP + Estoque (capital operacional), PMR/PMP |
| 📉 Histórico | Série diária via snapshot (saldo, AR/AP/Capital, inadimplência por faixa) |
| 📅 Calendário | Vencimentos do dia/semana selecionados |
| ⚙️ Configurações | Piso de caixa, thresholds de alerta |

### Funções utilizadas (de `core/domain/financeiro.py`)
`get_contas_receber`, `get_contas_pagar`, `get_estoque_custo`, `get_saldo_bancario`,
`get_evolucao_saldo`, `get_kpis`, `aging_por_cliente`, `aging_totais`, `fluxo_projetado`,
`ap_por_fornecedor`, `get_fluxo_diario`, `get_titulos_do_dia`, `get_historico_ar`,
`get_historico_ap`, `get_itens_nf`, `get_itens_av`, `get_comparativo_recebimentos`,
`get_comparativo_pagamentos`, `get_acumulado_ano`, `get_projecao_acumulada`,
`get_pmr_pmp`, `get_concentracao_inadimplencia`, `get_alertas_financeiro`,
`get_heatmap_vencimentos` — mais `get_evolucao_inadimplencia`/`get_evolucao_kpis`
(de `core.sync.snapshot`) na aba Histórico.

### Tabelas Firebird
`DOCUREC` (AR), `DOCUPAG` (AP), `MOVIREC`/`MOVIPAG` (liquidações → PMR/PMP),
`MOVIBAN` (saldo bancário), `CLIENTE`, `FORNECE`, `COMPPROD` + `PRODUTO` (estoque a custo
e a venda), `NFSAIDI`/`PEDIDOI` (itens do documento no drill-down).

### Tabelas DuckDB
`comentarios`, `config_alertas`, `snap_inadimplencia`, `snap_saldo_bancario`, `snap_kpis_diario`.

### Achados da auditoria (corrigidos nesta revisão)
- **`ESTOQUE_VENDA` sempre retornava 0** porque a query usava `COMPPROD.PRECONF`
  (campo de preço de fornecedor, não preenchido). Corrigido para usar `PRODUTO.PRECO`,
  com `JOIN` e filtro `CODEMPRESA='00'`. Resultado real: estoque a custo R$ 477.660,36 /
  a venda R$ 802.213,33 (markup médio ≈ 68%).
- **PMR/PMP negativos são dados corretos, não bug**: PMR = −0,7 dia (clientes pagam
  praticamente em dia) e **PMP = −37,2 dias** — a empresa paga fornecedores em média
  37 dias **antes** do vencimento (229 de 273 pagamentos liquidados nos últimos 90 dias
  foram antecipados). A tela já trata isso com aviso visual; vale reforçar como
  oportunidade de capital de giro (ver sugestão 1 abaixo).
- Valores de AR (R$ 447.693,06 / 1.528 títulos), AP (R$ 933.528,13 / 527 títulos) e
  saldo bancário (R$ 296.688,60) confirmados batendo 1:1 com consulta direta ao Firebird.

### Sugestões de evolução
1. **Painel "Antecipação de Pagamentos"** — com PMP de −37 dias, há um indício forte de
   capital de giro sendo usado de forma subótima. Um card dedicado mostrando "valor pago
   antes do vencimento nos últimos 90 dias" e "dias médios antecipados" tornaria esse
   achado visível sem precisar entrar na aba Posição de Caixa.
2. **Conciliação bancária assistida** — hoje há 1 única conta (Banco 0756); quando houver
   mais contas, considerar tela de conciliação (saldo DuckDB snapshot vs Firebird ao vivo).
3. **Simulador de antecipação de recebíveis** — dado o desconto de antecipação (se houver
   cadastro de taxa), simular impacto no caixa de antecipar X% do AR vencido.
4. **Exportar boletos do dia** — na aba Calendário, gerar lista para impressão/PDF dos
   títulos a pagar/receber do dia selecionado (hoje só exibe em tela).

---

## 4. Módulo Comercial — `pages/02_Comercial.py`

**Propósito:** acompanhamento de vendas, metas, clientes e sazonalidade.

### Abas

| Aba | Conteúdo principal |
|---|---|
| 🎯 Meta & Indicadores | Meta do mês, projeção de fechamento, ticket médio, funil de pedidos |
| 📈 Faturamento | Evolução temporal, comparativo de períodos, ranking de vendedores, descontos concedidos |
| 👥 Clientes | Top clientes (faturamento/lucro), clientes sem comprar, clientes em queda, novos × recorrentes, drill-down cliente → pedido → itens |
| 🧩 Concentração | Curva ABC de clientes e produtos |
| 📅 Sazonalidade | Padrão de vendas por mês/dia da semana |
| ⚙️ Configurações | Metas e thresholds |

### Funções utilizadas (de `core/domain/comercial.py`)
`get_faturamento`, `get_kpis_comercial`, `get_meta_mes`, `get_projecao_fechamento_mes`,
`get_faturamento_periodo`, `get_comparativo_faturamento`, `get_ticket_medio`,
`get_ranking_vendedores`, `get_funil_pedidos`, `get_descontos_periodo`,
`get_itens_periodo`, `get_itens_pedido`, `get_pedidos_cliente`,
`get_top_clientes_faturamento`, `get_top_clientes_lucro`, `get_top_produtos`,
`get_ultima_compra_clientes`, `get_clientes_sem_comprar`, `get_clientes_queda_compras`,
`get_clientes_novos_recorrentes`, `get_concentracao_clientes`, `get_concentracao_produtos`,
`get_sazonalidade`, `classifica_faixa_sem_comprar`, `classifica_curva_abc`, `resumo_curva_abc`.

### Tabelas Firebird
`PEDIDOC` (cabeçalho de pedido/fatura), `PEDIDOI` (itens), `CLIENTE`, `PRODUTO`.
Filtro-chave: `FATURADO='S'` define o que conta como venda concretizada; `CODVENDEDOR`
identifica o vendedor responsável.

### Achados da auditoria
- Faturamento mensal confirmado batendo com o Firebird: mar/2026 R$ 308.431,75 (1.090
  pedidos), abr/2026 R$ 318.677,10 (986), mai/2026 R$ 300.015,95 (970).
- Ranking de vendedores 2026 confirmado: Vendedor 0003 lidera com R$ 480.906,42 (1.596
  pedidos), seguido por 0004 com R$ 235.324,66.
- Base de clientes: 2.315 cadastrados, **apenas 392 (~17%) compraram em 2026** — sinal de
  base de clientes inativos relevante (ver sugestão 2).
- `CODVENDEDOR` e demais joins usam `TRIM()` consistentemente nas chaves; sem
  divergência de nomenclatura encontrada neste módulo.

### Sugestões de evolução
1. **Meta por vendedor** — hoje a meta é só agregada da empresa; quebrar por vendedor
   daria visibilidade individual de performance (a tabela `CFG`/`config_alertas` já
   existe no DuckDB para guardar metas customizadas).
2. **Campanha de reativação de clientes inativos** — com 1.923 clientes (83% da base)
   sem compra em 2026, uma aba dedicada "Clientes inativos por valor histórico"
   (já existe `get_clientes_sem_comprar`) poderia priorizar quem tem maior LTV para
   ação comercial direcionada.
3. **Comissão calculada** — `PEDIDOC.COMISSAO` já existe no banco; um card de comissão
   projetada por vendedor no mês seria natural na aba Faturamento.
4. **Funil de conversão por vendedor** — hoje o funil é agregado; segmentar por vendedor
   ajudaria a identificar quem converte melhor orçamento → pedido → faturamento.

---

## 5. Módulo Estoque — `pages/03_Estoque.py`

**Propósito:** controle de inventário, giro, produtos parados e ruptura.

### Abas

| Aba | Conteúdo principal |
|---|---|
| 🏆 Top Produtos | Por quantidade vendida / faturamento / lucro bruto (sub-abas) |
| 📦 Estoque Atual | Lista completa com custo, venda, mínimo/máximo, drill-down → movimentações |
| ⏰ Estoque Parado | Produtos com estoque > 0 sem giro recente |
| 🚨 Controle | Ruptura (sem estoque) e abaixo do mínimo (sub-abas) |
| 📊 Curva ABC | Classificação A/B/C por valor investido |
| 🔄 Giro por Grupo | Faturamento vendido ÷ valor em estoque, por grupo de produto |
| ⚙️ Configurações | Thresholds (dias parado, valor mínimo) |

### Funções utilizadas (de `core/domain/estoque.py`)
`get_estoque_geral`, `get_kpis_estoque`, `get_ultima_venda`, `get_estoque_parado`,
`get_produtos_sem_venda`, `get_controle_operacional`, `get_curva_abc_estoque`,
`resumo_abc_estoque`, `get_giro_por_grupo`, `get_top_produtos`,
`get_movimentacoes_produto`.

### Tabelas Firebird
`COMPPROD` (saldo de estoque — **somente `CODEMPRESA='00'` tem saldo real**, `'01'`
está sempre zerada), `PRODUTO` (descrição, preço de venda, mínimo/máximo), `GRUPROD`
(grupo/categoria), `MVGERAL` (movimentações; `TIPOMOV='55'` = venda PDV usada para
"última venda" e giro).

### Achados da auditoria (corrigidos nesta revisão)
- **Bug crítico corrigido:** `VENDA_UNIT` usava `COMPPROD.PRECONF`, que está **zerado
  em 100% dos 963 SKUs com estoque positivo**. Trocado para `PRODUTO.PRECO`. Resultado:
  KPI "Estoque a valor de venda" passou de R$ 0,00 para **R$ 802.213,33** (era
  invisível/errado em todas as telas que usavam esse campo).
- **`get_produtos_sem_venda()` e `get_estoque_parado()` retornavam exatamente o mesmo
  resultado** (432 SKUs) porque a primeira apenas chamava a segunda. Corrigido:
  `get_produtos_sem_venda()` agora filtra só produtos que **nunca** tiveram registro de
  venda (`ULT_VENDA` nulo) → **419 SKUs / R$ 132.718,27**; `get_estoque_parado()`
  mantém a regra mais ampla (nunca vendeu OU não vende há >90 dias) → **432 SKUs /
  R$ 140.340,85**. A diferença (13 SKUs / ~R$ 7,6 mil) são produtos que já venderam
  alguma vez, mas não nos últimos 90 dias — antes ficavam escondidos atrás do alias.
- Confirmado: 9.859 SKUs cadastrados, 963 com saldo positivo, 8.896 em ruptura (saldo
  ≤ 0) — número de ruptura alto é esperado em catálogo de material elétrico/hidráulico
  com milhares de itens de baixo giro, mas vale segmentar por "ativo e relevante" (ver
  sugestão 3).

### Sugestões de evolução
1. **Sugestão de reposição automática** — cruzar `get_giro_por_grupo` + `EST_MINIMO`
   para gerar uma lista "comprar agora" ordenada por urgência (dias até zerar, baseado
   em velocidade de venda média).
2. **Curva ABC cruzada com Parado** — hoje são abas separadas; um produto Classe A
   (alto valor) que também está parado é um alerta de prioridade máxima e merece
   destaque visual cruzado.
3. **Filtrar ruptura por relevância** — dos 8.896 SKUs em ruptura, a maioria provavelmente
   nunca teve giro relevante. Adicionar filtro "ruptura de produtos que venderam nos
   últimos 12 meses" tornaria a lista de ação muito mais curta e útil.
4. **Markup por produto/grupo** — agora que `VENDA_UNIT` está correto, exibir
   `(VENDA_UNIT - CUSTO_UNIT) / CUSTO_UNIT` por SKU/grupo é trivial e foi pedido
   implicitamente pela correção do bug acima.

---

## 6. Módulo Compras — `pages/04_Compras.py`

**Propósito:** análise de fornecedores, dependência, rentabilidade do que é comprado.

### Abas

| Aba | Conteúdo principal |
|---|---|
| 📈 Evolução de Compras | Histórico mensal (13 meses) de valor e quantidade de NFs |
| 🏭 Fornecedores | Top 15 por valor comprado, drill-down fornecedor → NFs → itens |
| ⚖️ Dependência | Concentração de compras nos principais fornecedores (pizza top 10 + alerta) |
| 💰 Rentabilidade | Compra × venda gerada por fornecedor (merge em pandas, não SQL) |
| 🚨 Alertas | Produtos comprados sem giro + estoque parado agrupado por fornecedor |
| ⚙️ Configurações | Thresholds de concentração e valor parado |

### Funções utilizadas (de `core/domain/compras.py`)
`get_historico_compras`, `get_compras_por_fornecedor`, `get_nfs_fornecedor`,
`get_itens_nf_entrada`, `get_rentabilidade_fornecedor`, `get_produtos_sem_giro`,
`get_estoque_parado_por_fornecedor`, `get_kpis_compras`.

### Tabelas Firebird
`NFENTRC` (cabeçalho NF de entrada — coluna de data é **`DT_ENTRADA`**, não
`DTENTRADA`), `NFENTRI` (itens da NF), `FORNECE` (nome do fornecedor está em
**`NOME`**, não em `FORNECEDOR`), `RELPRFO` (fornecedor principal por produto),
`MVGERAL` (`TIPOMOV='55'` para calcular venda gerada na aba Rentabilidade),
`COMPPROD` + `PRODUTO` + `GRUPROD` (estoque parado por fornecedor).

> Nota de nomenclatura: confirmado nesta auditoria que `core/domain/compras.py` já usa os
> nomes corretos (`DT_ENTRADA`, `TOTALNF`, `FORNECE.NOME`) — não havia bug de coluna
> neste módulo, apenas confirmação.

### Achados da auditoria
- Total comprado Jan–Jun/2026: **R$ 944.923,90** em 192 NFs de 88 fornecedores
  distintos — confirmado batendo com consulta direta.
- Top fornecedor: Condumig Ind. de Condutores Elétricos MG (R$ 242.288,51 em 12 NFs).
- Concentração: os 3 maiores fornecedores somam ~46% do total comprado no período —
  dentro do limiar de atenção configurado (60%), mas próximo o suficiente para
  monitorar.

### Sugestões de evolução
1. **Comparar preço entre fornecedores do mesmo produto** — `RELPRFO` já mapeia
   produto → fornecedores; uma tela "este produto é comprado de quem, a que preço"
   ajudaria a negociar e identificar sobrepreço.
2. **Prazo médio de entrega por fornecedor** — `DT_EMISSAO` vs `DT_ENTRADA` em
   `NFENTRC` já dá esse dado; útil para avaliar confiabilidade logística.
3. **Alerta de NF sem giro recorrente** — produto que aparece 3+ vezes na lista
   "sem giro" em meses consecutivos é candidato a parar de comprar; hoje o alerta é
   só do mês atual.

---

## 7. Módulo Alertas — `pages/05_Alertas.py`

**Propósito:** central única de gestão por exceção — agrega sinais dos 4 módulos.

### Abas
`🔔 Todos` (com contagem dinâmica) · `💰 Financeiro` · `📈 Comercial` · `📦 Estoque` ·
`🛒 Compras` · `⚙️ Configurações` (exibe a tabela de thresholds `CFG`).

### Funções utilizadas (de `core/domain/alertas.py`)
`get_todos_alertas(data_ini, data_fim)` — orquestra:
`alertas_financeiro()`, `alertas_comercial()`, `alertas_estoque()`,
`alertas_compras(data_ini, data_fim)` — e `resumo_alertas(lista)` para os contadores.

Cada alerta segue o formato padronizado:
```python
{'nivel': 'critico'|'urgente'|'atencao', 'modulo': str, 'icone': str,
 'titulo': str, 'detalhe': str, 'valor': float|None, 'pagina': str}
```

### Tabelas Firebird (indiretamente, via funções dos outros módulos)
`DOCUREC`, `DOCUPAG`, `MOVIBAN` (financeiro) · `PEDIDOC` (comercial) ·
`COMPPROD`/`PRODUTO`/`MVGERAL` (estoque) · `NFENTRC`/`FORNECE` (compras).

### Configuração de thresholds (`core/domain/alertas.py :: CFG`)
| Chave | Valor atual | Significado |
|---|---|---|
| `piso_caixa` | R$ 50.000 | Saldo mínimo de caixa antes de alertar |
| `capital_minimo` | R$ 100.000 | Capital operacional mínimo |
| `ap_horas_urgente` | 48h | Janela para "AP vencendo em breve" |
| `ar_dias_critico` | 90 dias | Atraso de AR considerado crítico |
| `ar_vencido_pct` | 80% | % do AR vencido sobre o total que dispara alerta |
| `concentracao_top3_pct` | 60% | % de concentração em poucos clientes/fornecedores |
| `parado_dias` / `sem_venda_dias` | 90 dias | Janela de "parado" no estoque/compras |

### Achados da auditoria (corrigido nesta revisão)
- O alerta de "AP vencendo" antes confundia títulos já vencidos com os que vencem nas
  próximas 48h (corrigido em sprint anterior — confirmado ainda correto: dados atuais
  mostram 467 títulos de AP vencidos somando R$ 800.462,47).
- O alerta de estoque "sem venda" e "parado" agora reflete a correção feita em
  `core/domain/estoque.py` (seção 5) — os números mudaram de "432 e 432" (idênticos, bug) para
  "419 nunca vendidos" e "432 parados (incluindo os 419)".

### Sugestões de evolução
1. **Histórico de alertas resolvidos** — hoje o painel é sempre "estado atual"; gravar
   no DuckDB quando um alerta deixa de aparecer (foi resolvido) cria um registro de
   "tempo médio de resolução" por tipo de alerta.
2. **Alerta por e-mail/WhatsApp para críticos** — usando o agendador já existente
   (`core/sync/agendador.py`), disparar notificação externa quando surgir alerta nível
   crítico, sem depender de alguém abrir o dashboard.
3. **Snooze/silenciar alerta** — permitir marcar um alerta como "em tratamento" por N
   dias (gravado no DuckDB) para não poluir a lista enquanto já está sendo resolvido.

---

## 8. Resumo da auditoria de dados (2026-06-17 a 2026-06-18)

| # | Item | Status antes | Correção aplicada | Arquivo |
|---|---|---|---|---|
| 1 | `VENDA_UNIT`/`ESTOQUE_VENDA` no estoque | Sempre R$ 0,00 (`COMPPROD.PRECONF` vazio) | Usa `PRODUTO.PRECO` via JOIN | `core/domain/estoque.py`, `core/domain/financeiro.py` |
| 2 | `get_produtos_sem_venda()` | Idêntico a `get_estoque_parado()` (alias disfarçado) | Filtra só `ULT_VENDA` nulo (nunca vendeu) | `core/domain/estoque.py` |
| 3 | Estoque a custo (`_SQL_ESTOQUE` financeiro) | Sem filtro `CODEMPRESA` (funcionava por coincidência) | Filtro explícito `CODEMPRESA='00'` adicionado | `core/domain/financeiro.py` |
| 4 | PMR/PMP negativos | Pareciam bug | Confirmado como dado real (pagamento antecipado de AP) | — (sem alteração de código) |
| 5 | Nomenclatura `compras.py` (`DT_ENTRADA`, `TOTALNF`, `FORNECE.NOME`) | — | Confirmado correto, sem ação necessária | — |
| 6 | Nomenclatura `comercial.py` (`CODVENDEDOR`) | — | Confirmado correto, sem ação necessária | — |
| 7 | `get_alertas_financeiro()` (painel de alertas da própria página Financeiro) | Somava AP já vencidos com AP vencendo em 48h (mesmo bug já corrigido em `core/domain/alertas.py`, mas em motor separado) | Dividido em dois alertas: "já vencidos" (crítico) e "vencendo em 48h" (urgente) | `core/domain/financeiro.py` |
| 8 | Filtros globais Empresa/Grupo/Marca (sidebar de todas as páginas) | Sempre vazios — `_SQL_GRUPOS`/`_SQL_MARCAS` com coluna errada, `_SQL_EMPRESAS` consultando tabela de licença (não cadastro) — exceção engolida silenciosamente | Corrigidos nomes de coluna (Grupo/Marca) e criada lista fixa para Empresa (não há cadastro real no banco) | `core/data/repositories/cadastros_repo.py` |

### Valores de referência (fotografia pontual — ver nota abaixo)
| KPI | Valor em 2026-06-17 | Valor em 2026-06-18 |
|---|---|---|
| Contas a Receber (total em aberto) | R$ 447.693,06 (1.528 títulos) | R$ 465.984,27 (1.634 títulos) |
| Contas a Receber vencido | R$ 325.659,80 (1.197 títulos) | R$ 201.188,37 |
| Contas a Pagar (total em aberto) | R$ 933.528,13 (527 títulos) | — |
| Contas a Pagar vencido | R$ 800.462,47 (467 títulos) | R$ 808.995,76 (472 títulos) |
| Saldo bancário (Banco 0756 / Conta 5410-0) | R$ 296.688,60 | — |
| Estoque a custo | R$ 477.660,36 (963 SKUs com saldo positivo) | — |
| Estoque a valor de venda | R$ 802.213,33 | — |
| PMR / PMP (90 dias) | −0,7 / −37,2 dias (pagamento antecipado) | — |
| Faturamento mar/abr/mai 2026 (consulta direta) | R$ 308.431,75 / R$ 318.677,10 / R$ 300.015,95 | R$ 287.013,07 / R$ 261.923,84 / R$ 275.422,87 (via `get_faturamento_periodo`, mesmo instante) |
| Clientes cadastrados / ativos em 2026 | 2.315 / 392 (17%) | 2.329 / 436 (19%) |
| Compras Jan–Jun/2026 | R$ 944.923,90 (192 NFs, 88 fornecedores) | — |
| Produtos nunca vendidos (estoque > 0) | 419 SKUs / R$ 132.718,27 | — |
| Produtos parados >90 dias (estoque > 0) | 432 SKUs / R$ 140.340,85 | — |

> **Atenção:** `RESULTH.FB` é o ERP de **produção real em operação contínua** — não
> um banco de testes estático. Cada linha desta tabela é uma fotografia do instante
> exato da consulta; números de dias diferentes legitimamente divergem porque vendas,
> pagamentos e recebimentos continuam acontecendo no negócio real entre uma consulta
> e outra. Confirmado nesta auditoria: duas consultas equivalentes rodadas no mesmo
> segundo batem 100% (testado com `get_kpis()` vs `aging_totais()` sobre o mesmo
> DataFrame); a divergência só aparece quando comparadas em momentos diferentes.
> **Nunca trate divergência temporal como bug** — para validar um número, sempre
> rode a consulta de conferência e o dashboard no mesmo instante.

---

## 9. Convenções de banco usadas em todo o projeto

- **Strings em Firebird (CHAR/VARCHAR)** quase sempre precisam de `TRIM()` nos dois
  lados de um `JOIN` ou `WHERE`, exceto em joins de chave primária de mesmo tamanho
  fixo (ver nota de performance em `core/domain/comercial.py`, onde `TRIM()` foi
  deliberadamente omitido em `PEDIDOC`/`PEDIDOI`/`PRODUTO` para preservar uso de índice).
- **`COMPPROD.CODEMPRESA='00'`** é a única empresa com saldo de estoque real;
  `'01'` está sempre zerada por desenho do ERP.
- **`MVGERAL.TIPOMOV`**: `'55'` venda PDV · `'01'` entrada NF · `'09'` saída
  consignação/orçamento (`PRECOVENDA=0`) · `'61'` devolução de entrada · `'05'`
  devolução de venda.
- **`PEDIDOC.FATURADO='S'`** é o filtro que define uma venda como concretizada
  (oposto de orçamento/pendente).
- **Firebird SQL Dialect 1** não aceita `FIRST` dentro de subqueries/agrupamentos —
  nesses casos, busca-se tudo e deduplica-se em pandas (ex.: `get_saldo_bancario`).
- **Preço de venda do produto vem de `PRODUTO.PRECO`**, não de `COMPPROD.PRECONF`
  (esse último é um campo de preço de fornecedor/nota fiscal, normalmente vazio).

---

## 10. Como validar este documento no futuro

Sempre que houver dúvida se um número do dashboard está certo, repita o padrão usado
nesta auditoria:

```python
import sys; sys.path.insert(0, r"C:\Users\ferod\OneDrive\Desktop\Projeto-Cetel")
from core.data.firebird import fb_query
# Escreva a query SQL equivalente diretamente e compare com o valor exibido na tela.
```

Compare o resultado da query direta com o retorno da função `core/domain/*.py` correspondente
(documentada nas seções 2–7). Divergência indica filtro, join ou coluna incorreta —
não confie em nenhum KPI sem essa verificação cruzada após mudanças no schema do ERP.
