# Plano de Testes Manuais — Dashboard Executivo Cetel

> **Versão:** 1.0 · **Data:** 2026-06-18
> **Como usar:** rode `streamlit run app.py`, abra `http://localhost:8501` e siga os passos.
> Para a "query de referência", use `python -c "..."` com `core.data.firebird.fb_query`
> (Firebird, somente leitura) ou `core.data.duckdb_store.duck_query` (DuckDB).

## Observação importante sobre o tipo de teste

Este sistema é **majoritariamente somente-leitura** (lê o ERP Resulth, nunca escreve nele).
Por isso, a maioria dos testes abaixo usa **"Query de referência"** em vez do par
clássico pré-check/pós-check: como não há mudança de estado no Firebird, a validação
correta é "o número na tela bate com a consulta direta?", não "o banco mudou depois
da ação?". Os poucos recursos que **escrevem** dados (comentários, metas, thresholds
de alerta, preferências) usam o par pré-check/pós-check completo, porque ali sim há
uma mudança de estado real — no DuckDB local, nunca no Firebird.

---

## Bloco A — Correções desta sessão (prioridade alta)

### TEST: Alerta de AP — "já vencidos" separado de "vencendo em 48h"
- **Steps:**
  1. Abra `Financeiro` → observe os cards de alerta no topo da página (antes das abas).
  2. Verifique se aparecem **dois** cards distintos: um crítico ("X título(s) AP já vencidos e em aberto") e um urgente ("Y título(s) AP vence(m) em 48h") — não um único card somando os dois.
- **Query de referência:**
  ```python
  from core.data.firebird import fb_query
  ja_venc = fb_query("SELECT COUNT(*) AS N, SUM(VALORDOCTO-COALESCE(VALORPAGO,0)) AS V FROM DOCUPAG WHERE SITUACAO='1' AND DT_VENCIMENTO < CAST('NOW' AS TIMESTAMP)")
  prox_48h = fb_query("SELECT COUNT(*) AS N, SUM(VALORDOCTO-COALESCE(VALORPAGO,0)) AS V FROM DOCUPAG WHERE SITUACAO='1' AND DT_VENCIMENTO >= CAST('NOW' AS TIMESTAMP) AND DT_VENCIMENTO <= CAST('NOW' AS TIMESTAMP) + 2")
  print(ja_venc, prox_48h)
  ```
- **Resultado esperado:** o card crítico mostra exatamente `ja_venc.N` títulos e `ja_venc.V` em R$; o card urgente mostra exatamente `prox_48h.N` e `prox_48h.V`.
- **Indicador de falha:** um único card somando os dois grupos (bug original — já corrigido), ou números que não batem com a query.

### TEST: Estoque — "Nunca venderam" distinto de "Parado"
- **Steps:**
  1. Abra `Estoque` → aba **Estoque Parado**.
  2. Observe os 5 cards de métrica: deve haver um card extra "Nunca venderam" além de "SKUs parados".
  3. Confirme que o valor de "Nunca venderam" é **menor** que "SKUs parados" (nunca vendidos é subconjunto de parados).
- **Query de referência:**
  ```python
  from core.domain.estoque import get_estoque_geral, get_ultima_venda, get_estoque_parado, get_produtos_sem_venda
  df_est = get_estoque_geral(); df_uv = get_ultima_venda()
  print("Parados >90d:", len(get_estoque_parado(90, df_est, df_uv)))
  print("Nunca venderam:", len(get_produtos_sem_venda(df_est, df_uv)))
  ```
- **Resultado esperado:** os dois números da tela coincidem exatamente com a query, e "Nunca venderam" ≤ "Parados".
- **Indicador de falha:** os dois números são idênticos (bug original) ou "Nunca venderam" > "Parados" (logicamente impossível).

### TEST: Estoque — Valor de venda não é mais zero
- **Steps:**
  1. Abra `Estoque` → aba **Estoque Atual**, filtro "Com estoque".
  2. Observe a coluna "Venda unit." — deve mostrar valores em R$ (não "—" para todos os produtos).
  3. No rodapé "Informações do Módulo", confira "Valor de venda total" — deve ser maior que "Valor custo total".
- **Query de referência:**
  ```python
  from core.domain.estoque import get_estoque_geral, get_kpis_estoque
  df = get_estoque_geral(); k = get_kpis_estoque(df)
  print(f"Custo: {k['valor_custo']:,.2f}  Venda: {k['valor_venda']:,.2f}")
  ```
- **Resultado esperado:** `valor_venda` > 0 e > `valor_custo` (markup positivo).
- **Indicador de falha:** `valor_venda` = 0,00 (bug original — usava `COMPPROD.PRECONF`).

### TEST: Filtros globais — Empresa / Grupo de Produto / Marca populados
- **Steps:**
  1. Abra qualquer módulo (ex.: `Estoque`) → painel lateral de filtros.
  2. Abra o dropdown "Empresa" — deve mostrar "Matriz (00)" e "Filial (01)" além de "Todas".
  3. Abra "Grupo de Produto" — deve listar ~22 grupos (Cabos e Conexões, Iluminação, etc.).
  4. Abra "Marca" — deve listar ~618 fabricantes.
- **Query de referência:**
  ```python
  from core.data.repositories.cadastros_repo import fetch_opcoes_filtros
  o = fetch_opcoes_filtros()
  print(len(o["empresas"]), len(o["grupos"]), len(o["marcas"]))  # esperado: 2 22 618 (aprox.)
  ```
- **Resultado esperado:** os 3 dropdowns têm opções reais (não vazios).
- **Indicador de falha:** qualquer um dos 3 dropdowns mostra só "Todas/Todos" sem mais opções (bug original).

---

## Bloco B — Tela Inicial

### TEST: KPIs executivos da Home batem com Financeiro/Estoque
- **Steps:**
  1. Abra a Home (`/`). Anote os valores de "A Receber", "A Pagar", "Caixa", "Estoque Custo".
  2. Abra `Financeiro` e compare "A Receber"/"A Pagar"/"Saldo Bancário" no cabeçalho.
  3. Abra `Estoque` e compare "Valor Custo".
- **Query de referência:** nenhuma necessária — é um teste de consistência entre 2 telas que devem usar a mesma fonte (`core.domain.financeiro.get_kpis`).
- **Resultado esperado:** valores idênticos entre Home e os módulos (mesmo cache de 10 min, podem diferir por minutos se uma tela atualizou e a outra não — re-clique "Atualizar dados" em ambas antes de comparar).
- **Indicador de falha:** valores divergentes mesmo após atualizar ambas as telas.

### TEST: Preferências da Home persistem
- **Steps:**
  1. Na Home, desmarque "Histórico de KPIs" na barra lateral.
  2. Recarregue a página (F5) ou navegue para outro módulo e volte.
  3. Confirme que a seção "Histórico de KPIs" permanece oculta.
- **Pre-check (DuckDB):**
  ```python
  from core.data.duckdb_store import duck_query
  print(duck_query("SELECT * FROM preferencias_home WHERE chave='home_historico'"))
  ```
- **Post-check:** repita a mesma query após desmarcar — `valor` deve ter virado `'false'`.
- **Resultado esperado:** preferência persiste entre reloads (gravada no DuckDB, não em `session_state` apenas).
- **Indicador de falha:** seção reaparece após F5 (preferência não foi persistida).

---

## Bloco C — Financeiro

### TEST: Aging de Contas a Receber por faixa
- **Steps:**
  1. `Financeiro` → aba **Contas a Receber**. Observe o gráfico/tabela de aging por faixa (1-30, 31-60, 61-90, +90 dias).
  2. Clique em um cliente da tabela "Maiores inadimplentes" para abrir o drill-down.
  3. No modal, clique em um título para ver o histórico de movimentações.
- **Query de referência:**
  ```python
  from core.domain.financeiro import get_contas_receber, aging_totais
  print(aging_totais(get_contas_receber()))
  ```
- **Resultado esperado:** soma das 4 faixas na tela == soma da query; drill-down abre sem erro e mostra histórico real (MOVIREC) do título selecionado.
- **Indicador de falha:** faixas não somam ao total exibido, ou modal de drill-down vem vazio para um título que tem histórico de pagamento.

### TEST: Comentário gerencial — gravação e exclusão (escrita real)
- **Steps:**
  1. Em qualquer aba do Financeiro, abra o widget de comentário, digite um texto de teste e salve.
  2. Recarregue a página — o comentário deve continuar visível na lista.
  3. Exclua o comentário pelo botão de lixeira.
- **Pre-check (DuckDB):**
  ```python
  from core.data.duckdb_store import duck_query
  print(duck_query("SELECT COUNT(*) AS n FROM comentarios"))
  ```
- **Post-check (após salvar):** repita a query — `n` deve ter incrementado em 1.
- **Post-check (após excluir):** repita novamente — `n` deve voltar ao valor original.
- **Resultado esperado:** contagem sobe e desce exatamente como esperado; nunca toca o Firebird.
- **Indicador de falha:** comentário desaparece ao recarregar (não foi persistido) ou `n` não muda (escrita silenciosamente falhou).

### TEST: Configuração de piso de caixa altera o alerta
- **Steps:**
  1. `Financeiro` → aba **Configurações** → altere "Piso de caixa" para um valor bem alto (ex.: R$ 10.000.000).
  2. Volte para o topo da página — deve aparecer (ou intensificar) o alerta de "Caixa abaixo do piso mínimo".
  3. Restaure o valor original.
- **Pre-check:** `from core.data.duckdb_store import get_config; print(get_config("piso_caixa"))`
- **Post-check:** repita após salvar — deve refletir o novo valor.
- **Resultado esperado:** alerta reage à configuração persistida, não a um valor fixo no código.
- **Indicador de falha:** alerta não muda independentemente do piso configurado (valor hardcoded em vez de lido do DuckDB).

---

## Bloco D — Comercial

### TEST: Funil de pedidos (Faturado / Pendente / Cancelado)
- **Steps:**
  1. `Comercial` → aba **Meta & Indicadores** → observe o funil e a taxa de conversão.
- **Query de referência:**
  ```python
  from core.domain.comercial import get_funil_pedidos
  f = get_funil_pedidos('2026-01-01', '2026-07-01')
  print(f['total_pedidos'], f['taxa_conversao'], f['dados'])
  ```
- **Resultado esperado:** quantidade e valor por situação na tela == `f['dados']`; taxa de conversão == `faturados/total*100`.
- **Indicador de falha:** soma das 3 situações ≠ total de pedidos criados no período.

### TEST: Meta de faturamento mensal (configuração manual — escrita real)
- **Steps:**
  1. `Comercial` → aba **Configurações** → defina uma meta mensal (ex.: R$ 500.000).
  2. Volte para **Meta & Indicadores** — o "% da meta atingida" deve recalcular com o novo valor.
- **Pre-check:** `from core.data.duckdb_store import get_config; print(get_config("meta_faturamento_mensal"))`
- **Post-check:** repita após salvar — valor deve ter sido atualizado.
- **Resultado esperado:** `% atingido = faturado_ate_hoje / meta_configurada * 100`, recalculado dinamicamente.
- **Indicador de falha:** percentual não muda após alterar a meta (cache não invalidado, ou leitura de valor fixo).

### TEST: Ranking de vendedores soma ao faturamento total
- **Steps:**
  1. `Comercial` → aba **Faturamento** → role até "Ranking de Vendedores".
  2. Some manualmente a coluna "Faturamento" de todos os vendedores listados.
- **Query de referência:**
  ```python
  from core.domain.comercial import get_faturamento, get_ranking_vendedores
  df = get_faturamento(meses_historico=6)
  print(df['TOTALPEDIDO'].sum(), get_ranking_vendedores(df)['Faturamento'].sum())
  ```
- **Resultado esperado:** soma do ranking == soma total do faturamento do período (todo pedido faturado tem vendedor, nenhum se perde).
- **Indicador de falha:** soma do ranking < total (pedidos sem `CODVENDEDOR` sendo descartados silenciosamente).

---

## Bloco E — Estoque

### TEST: Curva ABC soma 100% do valor investido
- **Steps:**
  1. `Estoque` → aba **Curva ABC** → observe o resumo por classe (A/B/C).
- **Query de referência:**
  ```python
  from core.domain.estoque import get_estoque_geral, get_curva_abc_estoque, resumo_abc_estoque
  abc = get_curva_abc_estoque(get_estoque_geral())
  print(resumo_abc_estoque(abc))
  ```
- **Resultado esperado:** soma de `% do Valor` das classes A+B+C = 100,0%; soma de `SKUS` = total de produtos com `QTD>0` e `VALOR_CUSTO>0`.
- **Indicador de falha:** percentuais não somam 100% (erro de acumulado — já corrigido em sprint anterior, mas vale reconfirmar).

### TEST: Controle Operacional — Ruptura vs Abaixo do Mínimo
- **Steps:**
  1. `Estoque` → aba **Controle** → sub-aba "Ruptura" e sub-aba "Abaixo do Mínimo".
- **Query de referência:**
  ```python
  from core.domain.estoque import get_estoque_geral, get_controle_operacional
  c = get_controle_operacional(get_estoque_geral())
  print(len(c['ruptura']), len(c['abaixo_minimo']))
  ```
- **Resultado esperado:** contagens na tela == valores da query.
- **Indicador de falha:** "Abaixo do Mínimo" sempre mostra 0 mesmo havendo produtos com `EST_MINIMO>0` e `QTD` abaixo dele (verificar se o ERP tem mínimos cadastrados antes de considerar isso bug — hoje é esperado ser baixo, ver `MANUAL_TECNICO.md`).

---

## Bloco F — Compras

### TEST: Dependência de fornecedores — alerta de concentração
- **Steps:**
  1. `Compras` → aba **Dependência** → observe o % dos 3 maiores fornecedores.
- **Query de referência:**
  ```python
  from core.domain.compras import get_compras_por_fornecedor
  df = get_compras_por_fornecedor('2026-01-01', '2026-07-01').sort_values('TOTAL_COMPRADO', ascending=False)
  top3 = df['TOTAL_COMPRADO'].head(3).sum() / df['TOTAL_COMPRADO'].sum() * 100
  print(f"{top3:.1f}%")
  ```
- **Resultado esperado:** % exibido na tela == `top3` calculado; alerta visual aparece se ≥ 60% (threshold configurado em Alertas).
- **Indicador de falha:** percentual não bate, ou alerta não aparece mesmo com concentração acima do limiar.

### TEST: Rentabilidade por fornecedor — drill-down até item de NF
- **Steps:**
  1. `Compras` → aba **Fornecedores** → clique no maior fornecedor da lista.
  2. No modal, clique em uma NF → deve abrir os itens daquela nota.
- **Query de referência:**
  ```python
  from core.domain.compras import get_nfs_fornecedor, get_itens_nf_entrada
  nfs = get_nfs_fornecedor('000097', '2026-01-01', '2026-07-01')  # CONDUMIG
  print(nfs.head())
  print(get_itens_nf_entrada('000097', nfs['NUMERONF'].iloc[0]))
  ```
- **Resultado esperado:** drill-down de 2 níveis funciona sem erro (Fornecedor → NFs → Itens).
- **Indicador de falha:** modal vem vazio para um fornecedor que claramente tem NFs no período.

---

## Bloco G — Alertas

### TEST: Painel consolidado reflete os 4 módulos
- **Steps:**
  1. Abra `Alertas` → aba **Todos** → confira a contagem por módulo no cabeçalho das abas (ex.: "💰 Financeiro (3)").
  2. Clique em "Ir para o módulo Financeiro" em um alerta — deve navegar para a página correta.
- **Query de referência:**
  ```python
  from core.domain.alertas import get_todos_alertas, resumo_alertas
  a = get_todos_alertas('2026-03-01', '2026-06-18')
  print(resumo_alertas(a))
  ```
- **Resultado esperado:** contadores nas abas == `por_modulo` da query; total == soma de C+U+A.
- **Indicador de falha:** contadores nas abas não batem com a função, ou o link de navegação não funciona.

### TEST: Threshold de alerta configurável (escrita real)
- **Steps:**
  1. `Alertas` → aba **Configurações** → veja a tabela de thresholds atuais.
  2. Em `Financeiro` → Configurações, altere "Dias de atraso crítico" de 90 para 30.
  3. Volte em `Alertas` → o alerta de "clientes com atraso crítico" deve mudar de contagem (mais clientes entram no crítico com limiar mais baixo).
- **Resultado esperado:** contagem de clientes críticos aumenta ao baixar o threshold (30d captura mais clientes do que 90d).
- **Indicador de falha:** contagem não muda após alterar o threshold (valor hardcoded em vez de lido via `get_config`).

---

## Bloco H — Exportação (Excel/PDF)

### TEST: Exportar Excel de qualquer aba
- **Steps:**
  1. Em qualquer aba com toolbar de exportação, clique "Exportar Excel".
  2. Abra o arquivo gerado — deve ter aba "Capa" + uma aba por seção de dados.
- **Resultado esperado:** arquivo abre sem erro no Excel/LibreOffice, dados conferem com a tela.
- **Indicador de falha:** arquivo corrompido, ou dados truncados/diferentes da tela.

### TEST: Exportar PDF de qualquer aba
- **Steps:**
  1. Mesmo contexto, clique "Exportar PDF".
  2. Abra o PDF — cabeçalho com título/período, KPIs, tabelas.
- **Resultado esperado:** caracteres acentuados (ç, ã, é) aparecem corretos ou substituídos de forma legível (c, a, e) — nunca como símbolo quebrado.
- **Indicador de falha:** caracteres corrompidos no PDF, ou erro ao gerar (`UnicodeEncodeError`).
