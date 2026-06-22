# MÓDULO COMERCIAL — Especificação e Estado Atual

> Documento vivo — atualizado a cada sprint.
> **Última atualização:** 2026-06-10 (5 análises complementares implementadas e testadas)
> Espelha a estrutura de `MODULO_FINANCEIRO.md`.

---

## Status geral

**Concluído — 2º módulo do roadmap (Fase 2).**
Base de dados validada via introspecção direta no Firebird (campos reais, não conceituais).
`core/domain/comercial.py` e `pages/02_Comercial.py` implementados, testados contra o banco
real (somente leitura) e validados via `AppTest` (carregamento completo sem exceções).

---

## Fontes de dados validadas

| Indicador do cliente | Tabela base | Campos-chave confirmados |
|---|---|---|
| Faturamento | `PEDIDOC` (FATURADO='S') | `TOTALPEDIDO, DATAFATURA, CODCLIENTE, CODVENDEDOR, CODEMPRESA, TIPOPEDIDO` |
| Itens do pedido (drill-down) | `PEDIDOI` | `CODPROD, QUANTIDADE, PRECOUNIT, DESCONTOVLR, TOTALITEM, TOTALRATEADO` |
| Forma de pagamento | `ENCEFAT` | `VLRDINHEIRO, VLRCARTAO, VLRCHEQUE, VLRCONVENIO, VLRBANCO, VLRTICKET, VLRRECEBER` |
| Meta de faturamento | `METAFATURAMENTOMENSAL` | `CODEMPRESA, MESANO, VALORFATURAMENTO` — **tabela vazia no banco atual** |
| Custo p/ lucro bruto | `COMPPROD` | `PRECOCUSTO` (custo atual — mesma limitação do Financeiro) |
| Cadastros (filtros) | `CLIENTE, VENDEND, PRODUTO, GRUPROD, CADFABR` | já usados em `cadastros.py` |

### Por que `PEDIDOC` e não `ENCEFAT`/`NFSAIDC` como base de faturamento

Testado nas 3 fontes candidatas (amostra jan–jun/2026):

| Tabela | Registros | Observação |
|---|---|---|
| `NFSAIDC` | 197 | Só NF-e emitidas — não cobre toda venda (cupom, pré-venda…) |
| `ENCEFAT` | 3.055 | "Fechamento" do pedido — granular, mas sem total único por venda |
| `PEDIDOC` (FATURADO='S') | 3.053 | **Escolhida** — `TOTALPEDIDO` já é o valor final faturado, 1:1 com ENCEFAT |

`PEDIDOC.FATURADO` tem 3 estados: `S` (faturado — usar), `N` (não faturado — ignorar),
`X` (cancelado/outro — ignorar). Total faturado no período de teste: ~R$ 928 mil
(3.053 pedidos, 6 vendedores, 392 clientes).

---

## Decisões técnicas e limitações conhecidas

| Decisão / Limitação | Detalhe | Como tratar na UI |
|---|---|---|
| **Faturamento = `SUM(PEDIDOC.TOTALPEDIDO)` onde `FATURADO='S'`** | Validado contra ENCEFAT (valores batem) | Filtrar por `DATAFATURA` no período |
| **Forma de pagamento não tem PIX/Boleto dedicados** | `ENCEFAT` só tem `VLRDINHEIRO/CARTAO/CHEQUE/CONVENIO/BANCO/TICKET/RECEBER`. PIX provavelmente cai em `CONVENIO` ou `RECEBER` — `VLRCARTAO`/`VLRBANCO` somam **zero** no período testado | Exibir a quebra pelos campos **que existem** com nota explicativa; não inventar PIX/Boleto separados sem confirmação do cliente |
| **`METAFATURAMENTOMENSAL` está vazia** | O cliente não usa essa funcionalidade do ERP | Meta configurável no DuckDB (`config`, mesmo padrão de `piso_caixa`) |
| **Lucro Bruto usa `COMPPROD.PRECOCUSTO` (custo atual)** | `PEDIDOI` não guarda custo histórico do item vendido | Rotular como "Lucro Bruto estimado (custo atual)" |
| **`CADFABR` como filtro "Marca"** | Mesma suposição já usada em `cadastros.py` (herdada do Financeiro) | Mantido — sem evidência de tabela `MARCA` dedicada |
| **`TRIM()` em condição de `JOIN` derruba uso de índice** | `_SQL_ITENS_PERIODO` com `TRIM()` em todas as chaves impede o otimizador do Firebird de usar os índices — ~55-100s para 1 mês. `CHAR` de mesmo tamanho → comparação `=` direta usa índice; `COMPPROD` é `VARCHAR` → `TRIM()` só do lado probe | ~250-300x mais rápido (0.2-0.6s). Ao escrever novos JOINs pesados, conferir tipos via `RDB$RELATION_FIELDS` antes de envolver chaves em `TRIM()` |
| **Histórico de faturamento curto no banco de teste** | `PEDIDOC` (FATURADO='S') só tem registros a partir de ~mar/2026 — 25 meses solicitados retornam apenas ~4 meses de dados | Avisos `st.caption` em comparativo YoY e sazonalidade; idem no indicador Novos vs Recorrentes |
| **`Acumulado %` em concentração calculado de valores arredondados (bug corrigido 2026-06-10)** | A versão original arredondava `Participação %` para 1 decimal *antes* do cumsum — com cauda longa (milhares de produtos cada contribuindo <0.05%), o acumulado "travava" abaixo de 80% e nunca gerava classe C no ABC | Corrigido: cumsum calculado sobre valores brutos, arredondamento apenas no display. ABC agora classifica corretamente A/B/C mesmo com distribuição longa |

---

## Mapeamento — requisito do cliente → implementação

| Bloco do prototótipo | Como será calculado | Aba/seção |
|---|---|---|
| **Meta Comercial** | `VALORFATURAMENTO` (config DuckDB) vs faturado real, quebra por forma de pgto (campos ENCEFAT existentes) | Aba "Meta & Indicadores" |
| **Indicadores** | Total faturado, % da meta, projeção linear de fechamento do mês | Aba "Meta & Indicadores" |
| **Faturamento** (dia/semana/quinzena/mês + comparativos) | `GROUP BY` em `DATAFATURA` truncada por granularidade; comparativo mês ant. e mesmo mês ano ant. | Aba "Faturamento" |
| **Ticket Médio** (geral / por vendedor) | `SUM(TOTALPEDIDO) / COUNT(pedidos)` | Aba "Faturamento" |
| **Top Clientes** (faturamento e lucro bruto) | `GROUP BY CODCLIENTE`; lucro bruto = `Σ(TOTALITEM − QUANTIDADE×PRECOCUSTO)` | Aba "Clientes" |
| **Clientes sem comprar** (30/60/90/180d) | `MAX(DATAFATURA)` por cliente vs hoje | Aba "Clientes" |
| **Clientes com queda de compras** (Top 10) | Média 6 meses vs últimos 30 dias | Aba "Clientes" |
| **Concentração de Faturamento** (clientes Top 10 / produtos Top 20) | % acumulado sobre o total do período | Aba "Concentração" |
| **Sazonalidade** (24 meses — faturamento, compras, margem) | Série mensal; "compras" depende do módulo Compras (zerado por ora) | Aba "Sazonalidade" |
| **Drill-down** Faturamento → Cliente → Pedido → Itens | Modal (`st.dialog`) — mesmo padrão do Financeiro | Todas as abas com tabela de pedidos |
| Filtros globais | Período (DATAFATURA), Empresa, Vendedor, Cliente, Grupo, Marca | Sidebar (componente já existe) |
| Exportação / Impressão / Comentários | Reaproveita `core/export.py`, `print_btn.py`, `_widget_comentario` | Todas as abas |

---

## Checklist de implementação

### Funcionalidades originais (requisito do cliente)

- [x] `core/domain/comercial.py` — camada de dados
  - [x] `get_faturamento(data_ini, data_fim)` — pedidos faturados + KPIs
  - [x] `get_meta_mes()` / config DuckDB de meta
  - [x] `get_faturamento_periodo(df, granularidade)` — dia/semana/quinzena/mês
  - [x] `get_ticket_medio(df)` — geral e por vendedor
  - [x] `get_top_clientes(df, criterio)` — faturamento / lucro bruto
  - [x] `get_clientes_sem_comprar(dias)`
  - [x] `get_clientes_queda_compras()`
  - [x] `get_concentracao(df, dimensao)` — clientes / produtos
  - [x] `get_sazonalidade(meses=24)`
  - [x] `get_pedidos_cliente(codcliente, ...)`, `get_itens_pedido(...)` — drill-down
- [x] `pages/02_Comercial.py` — UI
  - [x] Sidebar com filtros (período, empresa, vendedor, cliente, grupo, marca)
  - [x] Aba Meta & Indicadores
  - [x] Aba Faturamento (granularidade + comparativos + ticket médio)
  - [x] Aba Clientes (top, sem comprar, queda)
  - [x] Aba Concentração (clientes/produtos)
  - [x] Aba Sazonalidade
  - [x] Drill-down modal: Cliente → Pedido → Itens
  - [x] Exportação Excel/PDF + impressão + comentários (reuso)
  - [x] Bootstrap Icons em toda a página (reuso `components/bi_icons.py`)
- [x] Configuração de meta no DuckDB (`get_config`/`set_config`, chave `meta_faturamento_mensal`)

### Análises complementares (sprint 2026-06-10)

Cinco análises de valor adicionadas sem novas queries pesadas — reutilizam `df_fat` e `df_itens` já carregados em cache:

| Análise | Função | Localização na UI |
|---|---|---|
| **Ranking de Vendedores** | `get_ranking_vendedores(df_fat)` — pandas puro | Aba Faturamento |
| **Funil de Pedidos** (taxa de conversão) | `get_funil_pedidos(data_ini, data_fim)` — nova query `PEDIDOC` por `FATURADO` | Aba Meta & Indicadores |
| **Descontos Concedidos** | `get_descontos_periodo(df_itens, df_fat)` — usa `PEDIDOI.DESCONTOVLR` já no SELECT | Aba Faturamento |
| **Clientes Novos vs Recorrentes** | `get_clientes_novos_recorrentes(df_fat, df_ultima, data_ini)` — cruza `MIN(DATAFATURA)` histórica com o período filtrado | Aba Clientes |
| **Curva ABC (Pareto formal)** | `classifica_curva_abc(df_conc)` + `resumo_curva_abc(df_abc)` — pandas puro sobre `get_concentracao_*` | Aba Concentração |

**Campos adicionados ao SELECT de `_SQL_ITENS_PERIODO`** (sem joins novos):
- `TRIM(p.CODVENDEDOR) AS CODVENDEDOR` — necessário para `get_descontos_periodo`
- `COALESCE(i.DESCONTOVLR, 0) AS DESCONTO` — valor bruto do desconto por item

**Campos adicionados ao SELECT de `_SQL_ULTIMA_COMPRA`**:
- `MIN(p.DATAFATURA) AS PRIMEIRA_COMPRA` — necessário para `get_clientes_novos_recorrentes`

**Validação contra o banco real (2026-06-10):**
- Ranking: 6 vendedores; top = R$ 480.906 / 1596 pedidos / 279 clientes / ticket R$ 301
- Funil (jan–jun/2026): 3.554 pedidos criados, 3.053 faturados, taxa = **85,9%**, R$ 1,59M parado em pendentes
- Descontos: total R$ 210,88 (0,02% sobre faturado) — empresa de desconto baixo
- Novos vs Recorrentes: 392 novos / 0 recorrentes — reflexo do **histórico curto no banco de teste** (dados só de ~mar/2026), não de captação real; UI exibe aviso explicativo quando `recorrentes == 0`
- ABC Clientes: A=56 (79,8%) / B=90 (14,8%) / C=246 (5,4%)
- ABC Produtos: A=293 (77,4%) / B=1.900 (22,6%) / C=0 → C aparecia zerado na versão com bug de cumsum (corrigido)

---

## Próximos módulos (contexto)

Conforme `ROADMAP.md`: após Comercial vêm Produtos+Estoque (Fase 3, compartilham `COMPPROD`/`MVGERAL`),
Compras (Fase 4) e Alertas (Fase 5, transversal — agrega sinais dos módulos anteriores).
