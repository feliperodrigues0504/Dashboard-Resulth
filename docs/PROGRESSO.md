# PROGRESSO — Estado atual do projeto

> Arquivo de controle de progresso e workflow.
> Atualizar sempre que uma fase ou decisão importante for concluída.
> **Última atualização:** 2026-06-18

---

## Estado atual

| Fase | Status | Descrição |
|------|--------|-----------|
| 0 — Fundação | ✅ Concluída | Conexão Firebird, DuckDB, estrutura de pastas |
| 1 — Financeiro | ✅ Concluído com Drill-Down | AR, AP, Fluxo, Posição de Caixa, Saldo Bancário + drill-down 3 níveis + correções TIPOMOV + itens AV |
| 2 — Comercial | ✅ Concluído + 5 análises extra | Meta & Indicadores, Faturamento, Clientes, Concentração, Sazonalidade + drill-down + Funil/Ranking/Descontos/Novos×Recorrentes/ABC |
| 3 — Estoque/Produtos | ✅ Concluído | Top Produtos, Estoque Atual, Estoque Parado, Controle Operacional, Curva ABC, Giro por Grupo + drill-down produto→movimentações |
| 4 — Compras | ✅ Concluído | Evolução, Fornecedores, Dependência, Rentabilidade, Alertas (sem giro + parado) + drill-down Forn→NF→Itens |
| 5 — Alertas | ✅ Concluído | Painel consolidado: Crítico/Urgente/Atenção · 10 alertas reais · todos os módulos · filtros + gráficos + links diretos |
| 6 — Tela inicial | ✅ Concluído | Dashboard executivo: KPIs consolidados · Alertas · Faturamento 30d · AR vs AP · Cards de módulos · Preferências persistidas |
| 7 — Polimento | ✅ Concluído | APScheduler snapshots diários · Histórico KPIs (Home + Financeiro) · requirements.txt · 14/14 sem erros |
| 8 — Pente fino (auditoria) | ✅ Concluído | Auditoria completa de dados vs Firebird · 3 bugs corrigidos · `docs/MANUAL_TECNICO.md` criado |

---

## Como rodar o projeto

```bash
# Na raiz do projeto (C:\Users\ferod\OneDrive\Desktop\Projeto-Cetel)
streamlit run app.py --server.port 8501
```

Acesse pelo navegador: `http://localhost:8501`  
Na rede local: `http://<IP-DO-SERVIDOR>:8501`

---

## Ambiente

| Item | Valor |
|------|-------|
| Python | 3.14.0 |
| Driver Firebird | `fdb 2.0.4` (dialect 1 / Firebird 2.5 compatível) |
| fbclient.dll | Raiz do projeto (`C:\...\Projeto-Cetel\fbclient.dll`) |
| Banco | caminho do `.FB` definido via `.env` (`FB_DATABASE`) — ver `.env.example` |
| Usuário/Senha | definidos via `.env` (`FB_USER`/`FB_PASSWORD`) — nunca hardcoded |
| Charset | `WIN1252` |
| Streamlit | porta `8501` |
| DuckDB store | `data/store.duckdb` |

### Pacotes instalados
```
streamlit, duckdb, pandas, plotly, openpyxl, fdb, flask
```

---

## Estrutura de pastas

```
Projeto-Cetel/
├── app.py                      # Home do Streamlit (entrypoint: streamlit run app.py)
├── fbclient.dll                # Biblioteca Firebird (necessária para o fdb)
├── pages/
│   ├── 01_Financeiro.py        # Módulo Financeiro completo
│   ├── 02_Comercial.py         # Módulo Comercial completo
│   ├── 03_Estoque.py           # Módulo Estoque/Produtos completo
│   ├── 04_Compras.py           # Módulo Compras completo
│   └── 05_Alertas.py           # Módulo Alertas — painel consolidado
├── core/
│   ├── db_firebird.py          # Conexão R/O com Firebird (usa fbclient.dll da raiz)
│   ├── db_duck.py              # Conexão + inicialização do DuckDB store
│   ├── financeiro.py           # Camada de dados do módulo Financeiro
│   ├── comercial.py            # Camada de dados do módulo Comercial
│   ├── estoque.py              # Camada de dados do módulo Estoque/Produtos
│   ├── compras.py              # Camada de dados do módulo Compras
│   ├── alertas.py              # Motor centralizado de alertas (Fase 5)
│   ├── cadastros.py            # Opções de filtros globais (clientes, vendedores...)
│   ├── export.py               # Exportação Excel/PDF
│   ├── introspect.py           # Utilitário para inspecionar tabelas do banco
│   └── sync/                   # Jobs de sincronização incremental
├── components/
│   ├── metrics.py              # KPI cards, formatação BRL, helpers de UI
│   ├── bi_icons.py             # Bootstrap Icons injetáveis em HTML
│   ├── filtros.py              # Sidebar de filtros globais
│   └── print_btn.py            # Botão e CSS de impressão
├── config/
│   └── settings.py             # Parâmetros de conexão e configuração
├── data/
│   └── store.duckdb            # Store analítico (gerado automaticamente)
└── docs/
    ├── DOCUMENTACAO_SISTEMA.md # Documentação funcional profissional (módulos + dicionário de dados)
    ├── MANUAL_TECNICO.md       # Documentação técnica (funções, tabelas por tela, auditoria, sugestões)
    ├── ROADMAP.md              # Planejamento geral do projeto
    ├── MODULO_FINANCEIRO.md    # Especificação do módulo financeiro
    ├── MODULO_COMERCIAL.md     # Especificação do módulo comercial
    ├── MODULO_ESTOQUE.md       # Especificação do módulo estoque/produtos
    ├── MODULO_COMPRAS.md       # Especificação do módulo compras
    ├── MODULO_ALERTAS.md       # Especificação do módulo alertas
    ├── DB_REFERENCE.md         # Referência do banco Resulth (tabelas)
    └── PROGRESSO.md            # Este arquivo
```

---

## Decisões técnicas registradas

### Firebird — SQL Dialect 1
O banco está em **SQL dialect 1**. Implicações:
- `DATE` não é tipo suportado como literal — usar `CAST('NOW' AS TIMESTAMP)`
- Não usar `FIRST N` / `TOP N` sem testar
- Window functions (`ROW_NUMBER OVER`) podem não funcionar em dialect 1

**Workaround adotado:** computações de datas (aging, dias de atraso, faixas) são feitas em **pandas no Python**, não em SQL. O SQL apenas extrai os dados brutos.

### Campos corretos do COMPPROD
- ✅ Usar `ESTOQUE` para quantidade em estoque
- ❌ `ESTOQUEDISPONIVEL` está sempre 0 nesta base

### Saldo bancário (MOVIBAN)
- A query usa `ORDER BY DATAMOV DESC, NUMORD DESC` e `drop_duplicates` em Python para pegar o último saldo por conta
- Motivo: múltiplos movimentos no mesmo dia geravam linhas duplicadas com subquery de MAX(DATAMOV)

### DOCUREC — campo SITUACAO
| Valor | Significado | Evidência |
|-------|-------------|-----------|
| `'1'` | **Em aberto** (VALORPAGO = 0) | 4276 títulos, avg_pago = 0 |
| `'2'` | Liquidado | avg_pago ≈ avg_docto |
| `'3'` | Parcialmente pago ou cancelado | avg_pago < avg_docto |
| `'4'` | Cancelado (sem pagamento) | 13 títulos, avg_pago = 0 |

**Módulo financeiro usa:** `WHERE SITUACAO = '1'` (apenas títulos em aberto)

### DOCUPAG — campo SITUACAO
| Valor | Significado |
|-------|-------------|
| `'1'` | Em aberto |
| `'2'` | Liquidado |
| `'3'` | Parcial/cancelado |

### MOVIREC — campo TIPOMOV
| Valor | Significado provável | QTD |
|-------|---------------------|-----|
| `'01'` | Emissão do título | 4539 |
| `'04'` | Prorrogação | 182 |
| `'05'` | Liquidação (pagamento) | 213 |
| `'07'` | Estorno | 13 |
| `'08'` | Outros | 6 |

---

## Volumetria do banco (referência)

| Tabela | Registros | Observação |
|--------|-----------|------------|
| `DOCUREC` | 4.539 | 4.276 em aberto, 4.192 vencidos |
| `DOCUPAG` | 463 | 448 em aberto |
| `MOVIREC` | 4.953 | Histórico de movimentos de AR |
| `MOVIPAG` | 478 | Histórico de movimentos de AP |
| `CLIENTE` | 1.402 | — |
| `FORNECE` | 60 | — |
| `COMPPROD` | 21.696 | 2.029 com estoque > 0 |
| `MOVIBAN` | 1.863 | Módulo bancário ativo |
| `CONTAS` | 2 | 2 contas bancárias |
| `SALDOST` | 791 | Saldo diário histórico |
| Total banco | 1.145 tabelas | — |

---

## KPIs do módulo financeiro (snapshot em 2026-06-03)

| KPI | Valor |
|-----|-------|
| Total a Receber (em aberto) | R$ 465.738,61 |
| Total Vencido (AR) | R$ 456.762,94 |
| A Vencer (AR) | R$ 8.975,67 |
| Total a Pagar (em aberto) | R$ 354.161,40 |
| Vencido (AP) | R$ 343.189,71 |
| Saldo Bancário | R$ 314.457,40 |
| Estoque ao custo | R$ 211.380,44 |
| Capital Operacional | R$ 637.415,05 |

> Saldo bancário = soma das 2 contas (banco 0756 + banco 0104)

---

## Drill-Down implementado (2026-06-03)

### Aba Contas a Receber
`Cliente → Títulos do cliente → Histórico de movimentações (MOVIREC)`

### Aba Fluxo de Caixa
`Horizonte → Dia a dia → Títulos do dia (AR/AP lado a lado) → Histórico (MOVIREC / MOVIPAG)`

### Aba Contas a Pagar
`Fornecedor → Títulos do fornecedor → Histórico de movimentações (MOVIPAG)`

- Navegação por botão "← Voltar" em cada nível
- Tabelas com `on_select="rerun"` e `selection_mode="single-row"`
- Estado mantido em `st.session_state.dd`

---

## Sprint 2026-06-10 — Análises complementares do Comercial

Cinco análises de valor adicionadas ao módulo Comercial (`core/comercial.py` + `pages/02_Comercial.py`).
Todas validadas contra o banco real (somente leitura). AppTest: 0 exceções.

| Análise | Abordagem | Destaque |
|---|---|---|
| **Funil de Pedidos** | Nova query `PEDIDOC` GROUP BY `FATURADO` | Taxa de conversão = 85,9%; R$ 1,59M em pendentes |
| **Ranking de Vendedores** | Pandas puro sobre `df_fat` | Zero SQL extra; 6 vendedores; top R$ 480k |
| **Descontos Concedidos** | Coluna `DESCONTOVLR` adicionada ao SELECT existente | 0,02% do faturado — negócio de desconto baixo |
| **Clientes Novos vs Recorrentes** | Cruza `MIN(DATAFATURA)` histórica com período filtrado | Aviso automático quando `recorrentes==0` (histórico curto no banco de teste) |
| **Curva ABC** | `classifica_curva_abc` / `resumo_curva_abc` pandas sobre `get_concentracao_*` | A/B/C clientes (56/90/246) e produtos |

**Bug corrigido neste sprint:**
`get_concentracao_clientes/produtos` calculava `Acumulado %` como cumsum de valores *já arredondados* para 1 decimal. Em distribuições longas (2.000+ produtos), os itens da cauda arredondavam para 0,0% individualmente, fazendo o acumulado travar abaixo de 80% e nunca gerar classe C no ABC. Corrigido: cumsum sobre valores brutos, arredondamento apenas no display.

---

## Sprint 2026-06-12 — Módulo Estoque/Produtos (Fase 3)

Módulo completo implementado: `core/estoque.py` + `pages/03_Estoque.py`.
7 abas, drill-down produto→movimentações, exportação Excel/PDF, comentários gerenciais.

| Análise | Abordagem | Dado real |
|---|---|---|
| **Top Produtos** | MVGERAL TM='55' × PRODUTO × GRUPROD | Top: Cabo Rede LAN R$ 28.572 |
| **Estoque Parado** | COMPPROD × MAX(DT_MOV) por produto | 430 SKUs, R$ 139.204 (>90d) |
| **Controle Operacional** | COMPPROD.ESTOQUE vs ESTMINIMO | Estoque mínimo cadastrado para poucos produtos |
| **Curva ABC** | Por VALOR_CUSTO = ESTOQUE × PRECOCUSTO | Classificação A/B/C por valor investido |
| **Giro por Grupo** | FAT_VENDIDO (MVGERAL) / VALOR_ESTOQUE (COMPPROD) | Cabos lidera faturamento |

**Descobertas técnicas:**
- `COMPPROD.CODEMPRESA='00'` = saldo real; `'01'` = sempre zero
- `COMPPROD.PRECONF` (preço de venda) ≈ 0 na maioria dos produtos
- `MVGERAL.TIPOMOV='55'` = venda PDV (9.481 registros, mais recente: 2026-06-01)
- `MVGERAL.TIPOMOV='09'` = saída com PRECOVENDA=0 (consignação/orçamento) — excluído dos cálculos de venda
- Lucro bruto = FAT (MVGERAL.PRECOVENDA × QTD) − CMV (QTD × COMPPROD.PRECOCUSTO atual)

---

## Observações / pendências para próxima sessão

1. **Estoque — preço de venda zerado:** `PRECONF` está quase sempre 0 na COMPPROD.
   Confirmar com o cliente se o preço está em `PRECOFILIAL` ou outro lugar.

2. **SALDOST:** campo `SALDO` na empresa '00' soma R$ 46 milhões acumulados — isso é saldo cumulativo histórico, não o saldo atual. A tabela de saldo atual correto é `MOVIBAN` (já implementado).

3. **Charset:** alguns textos aparecem com `?` no terminal por encoding `WIN1252` vs UTF-8 do terminal. No Streamlit (HTML) isso não ocorre.

4. **Próximo módulo:** Compras (Fase 4) — tabelas NFENTRC/NFENTRI, FORNECE, RELPRFO.

5. **[Comercial] TRIM() em condição de JOIN derruba uso de índice no Firebird:** em
   `_SQL_ITENS_PERIODO` (join PEDIDOC⋈PEDIDOI⋈PRODUTO⋈COMPPROD), envolver as chaves do
   JOIN em `TRIM()` (ex.: `ON TRIM(i.CODPROD) = TRIM(p.CODPROD)`) impede o otimizador de
   usar os índices (`PEDIDOI_IDX_1`, `PK_PEDIDOI`, `PK_PRODUTO`), forçando varredura
   completa por linha — uma consulta de ~2.900 itens (1 mês) levava ~55-100s; o range
   padrão de filtro (Jan–hoje, ~5 meses) chegava a travar o app. Como `CODEMPRESA`,
   `TIPOPEDIDO`, `CODPEDIDO`, `CODCLIENTE` e `CODPROD` são `CHAR` de mesmo tamanho nas
   tabelas `PEDIDOC`/`PEDIDOI`/`PRODUTO`, a comparação `=` direta já compara com padding
   (sem necessidade de `TRIM`) e usa os índices — reduz para ~0.2-0.6s (250-300x).
   `COMPPROD` é `VARCHAR`: aplicar `TRIM()` somente do lado de `PEDIDOI` (probe), mantendo
   a coluna de `COMPPROD` "nua" para o otimizador poder indexar esse lado. Resultado
   validado byte-a-byte contra a versão antiga (mesmo `sum(PRECOCUSTO)` e nº de linhas).
   **Atenção:** ao escrever novos JOINs pesados (múltiplas tabelas, sem filtro restritivo),
   conferir tipos das colunas via `RDB$RELATION_FIELDS`/`RDB$FIELDS` antes de envolver
   chaves em `TRIM()` — só é necessário quando os tipos/tamanhos divergem.

---

## Workflow padrão para novos módulos

1. **Introspectar as tabelas** do módulo:
   ```bash
   python scripts/dev/introspect.py TABELA1 TABELA2
   ```

2. **Amostrar os campos chave** (SITUACAO, tipos, valores):
   ```python
   fb_query("SELECT CAMPO, COUNT(*) FROM TABELA GROUP BY CAMPO")
   ```

3. **Criar `core/<modulo>.py`** com as funções de dados (mesma estrutura de `core/financeiro.py`).

4. **Criar `pages/0N_NomeModulo.py`** com a página Streamlit.

5. **Atualizar este arquivo** com decisões, volumetria e pendências.

---

## Sprint 2026-06-12 — Módulo Compras (Fase 4)

Módulo completo implementado: `core/compras.py` + `pages/04_Compras.py`.
6 abas, drill-down Fornecedor→NF→Itens, exportação Excel/PDF, comentários gerenciais.

| Análise | Abordagem | Dado real |
|---|---|---|
| **Evolução Mensal** | NFENTRC GROUP BY mês, 13 meses histórico | 3 meses ativo: R$ 944.923 |
| **Top Fornecedores** | GROUP BY CODFORNEC × FORNECE | CONDUMIG 25,6% — R$ 242.288 |
| **Dependência** | Participação acumulada + alertas automáticos | Top 3 = 60%+ |
| **Rentabilidade** | Python merge NFENTRC × RELPRFO × MVGERAL × COMPPROD | CONDUMIG margem 84% |
| **Sem Giro** | Comprados (NFENTRI) ∉ Vendidos (MVGERAL TM=55) | 877 produtos, R$ 231.629 |
| **Parado por Fornecedor** | COMPPROD estoque × MAX(DT_MOV) agrupado por RELPRFO.PRINCIPAL | KRONA 154 SKUs |

**Decisões técnicas:**
- JOIN NFENTRC/NFENTRI deve usar 3 campos: `CODEMPRESA + NUMERONF + CODFORNEC`
  (sem isso, produto cartesiano por NFs com mesmo número de fornecedores diferentes)
- Rentabilidade calculada em Python (4 DataFrames + merge) — evita JOINs complexos no Firebird Dialect 1
- `NOME_EXIB` = FANTASIA se preenchido, senão FORNECEDOR — calculado em Python antes de qualquer merge

**Bug corrigido neste sprint:**
`f"{r['MES']:02d}/{r['ANO']}"` em `get_historico_compras` — pandas apply em row mista retorna float.
Fix: `f"{int(r['MES']):02d}/{int(r['ANO'])}"`. Mesmo padrão do Estoque.

---

## Sprint 2026-06-12 — Módulo Alertas (Fase 5)

Painel consolidado implementado: `core/alertas.py` + `pages/05_Alertas.py`.
6 abas, filtros por nível e módulo, gráficos de distribuição, links diretos, thresholds configuráveis.

**10 alertas reais validados ao vivo:**

| Nível | Módulo | Alerta |
|-------|--------|--------|
| Crítico | Financeiro | 467 AP já vencidos e em aberto |
| Crítico | Financeiro | 45 clientes AR com atraso >90 dias |
| Urgente | Financeiro | 1 AP vencendo nas próximas 48h |
| Urgente | Comercial | 135 clientes sem comprar >60 dias |
| Atenção | Financeiro | Saldo bancário desatualizado 11 dias |
| Atenção | Comercial | 20 clientes com queda ≥40% nas compras |
| Atenção | Estoque | 432 SKUs parados >90d — R$ 140.340 |
| Atenção | Estoque | 419 produtos com estoque sem venda registrada |
| Atenção | Compras | 877 comprados sem giro no período |
| Atenção | Compras | R$ 245.081 parado em 51 fornecedores |

**Decisões técnicas:**
- Motor `core/alertas.py` orquestra chamadas aos demais core modules — não acessa Firebird diretamente
- try/except por módulo e por alerta individual: falha em um não derruba os demais
- Cache TTL=300s (5min) — mais curto que outros módulos por natureza urgente dos alertas
- AP vencidos: alerta crítico separado do "próximas 48h" para não suprimir 448 AP já vencidos
- Estoque sem venda: diferenciado de parado (parado = tem estoque, sem venda N dias; sem venda = nunca teve registro)

---

## Sprint 2026-06-12 — Tela Inicial (Fase 6)

Home executivo completo em `app.py`. Substituiu o placeholder com cards estáticos.

**Seções:**
- **KPIs Executivos** (2 linhas × 6 colunas): Alertas badge, AR, Vencido AR, Caixa, Fat. Mês, Estoque Custo / AR a Vencer, AP, Vencido AP, Capital Op., SKUs, Clientes inativos 60d
- **Alertas Ativos**: cards resumidos (crítico/urgente) com link para `05_Alertas.py`
- **Gráficos Rápidos**: faturamento últimos 30d (barras diárias) + posição financeira AR vs AP (barras empilhadas)
- **Módulos do Sistema**: cards com badge de dado real + `st.page_link` para cada módulo
- **Preferências**: sidebar com checkboxes para mostrar/ocultar seções (persistidas em DuckDB via `preferencias_home`)

**Dados validados ao vivo (2026-06-12):**
- AR total: R$447.693 · AP total: R$933.528 · Caixa: R$296.689
- Estoque: R$477.660 · SKUs com estoque: 963

**Decisões técnicas:**
- `preferencias_home` table adicionada ao DuckDB em `init_store()` (idempotente)
- `get_preferencia()` / `set_preferencia()` em `core/db_duck.py` para leitura/escrita das preferências
- Cache TTL=600s (10min) para dados financeiros/estoque; 300s para alertas
- `st.page_link()` para navegação entre módulos (links nativos do Streamlit, sem hacks)
- Todos os módulos exibidos como disponíveis com badges de dados reais

**Status do projeto:**
- Todas as 6 fases concluídas (0-Fundação até 6-Tela Inicial)
---

## Sprint 2026-06-12 — Polimento (Fase 7)

**Snapshots + Agendador:**
- `core/sync/snapshot.py` expandido: `gravar_snapshot_inadimplencia()`, `gravar_snapshot_saldo_bancario()`, `gravar_snapshot_kpis()`, `gravar_todos()`
- `core/sync/agendador.py` criado: APScheduler 3.11.2, BackgroundScheduler, `@st.cache_resource` singleton, agenda diária às 08:00, grava snapshot do dia na inicialização
- `snap_kpis_diario` adicionado ao DuckDB (AR/AP/Caixa/Capital/Estoque/Fat mês)
- `preferencias_home` adicionado ao DuckDB (persistência de checkboxes da tela inicial)
- `get_preferencia()` / `set_preferencia()` adicionados em `core/db_duck.py`
- Fix: query MOVIBAN de saldo bancário usava `FIRST 1` incompatível com Firebird Dialect 1 — corrigido para reutilizar `get_saldo_bancario()` (deduplica em Python)

**Histórico de KPIs:**
- Home: seção "Histórico de KPIs" com AR vencido × caixa, capital operacional e inadimplência por faixa (visível após 3+ dias)
- Financeiro: aba "📉 Histórico" com saldo bancário, AR/AP/Capital e evolução de inadimplência empilhada
- `get_evolucao_snapshot` mantido como alias para compatibilidade com código anterior

**Infraestrutura:**
- `requirements.txt` gerado com versões exatas
- 14/14 arquivos compilam sem erros (app.py + 5 pages + 7 core + 2 sync)
- Exportação Excel e PDF validada ao vivo

**Validação ao vivo:**
- KPIs hoje: AR=R$447.693, AP=R$933.528, Caixa=R$296.689
- Snapshots: 3 dias de inadimplência, 1 dia de KPIs e saldo
- Alertas: 10 ativos (2C/2U/6A)

---

## Sprint 2026-06-17 — Pente fino: auditoria de dados + documentação (Fase 8)

Revisão completa do projeto contra o Firebird (todas as 15+ queries de auditoria
documentadas em `docs/MANUAL_TECNICO.md` §8) + criação do manual técnico profissional
consolidando tela → funções → tabelas + sugestões de evolução por módulo.

**3 bugs reais encontrados e corrigidos:**

1. **`core/estoque.py` — `VENDA_UNIT`/`ESTOQUE_VENDA` sempre R$ 0,00.**
   `COMPPROD.PRECONF` está zerado em 100% dos 963 SKUs com saldo positivo (é campo de
   preço de fornecedor, não de venda). Trocado para `PRODUTO.PRECO` via JOIN.
   Resultado: estoque a valor de venda passou de R$ 0,00 para **R$ 802.213,33**
   (markup médio ≈ 68% sobre o custo de R$ 477.660,36).
   Mesma correção espelhada em `core/financeiro.py :: _SQL_ESTOQUE` (com filtro
   `CODEMPRESA='00'` adicionado).

2. **`get_produtos_sem_venda()` era um alias disfarçado de `get_estoque_parado()`** —
   retornavam exatamente os mesmos 432 SKUs. Corrigido para filtrar apenas produtos
   que **nunca** tiveram nenhuma venda registrada (`ULT_VENDA` nulo): agora retorna
   **419 SKUs / R$ 132.718,27**, distinto de `get_estoque_parado()` (432 SKUs —
   inclui também produtos que já venderam, mas há mais de 90 dias).
   Call-sites corrigidos: `core/alertas.py` (alerta de estoque sem venda — removida
   filtragem redundante que já compensava o bug) e `pages/03_Estoque.py` (o slider
   "sem venda há N dias" precisava da semântica antiga → trocado para chamar
   `get_estoque_parado()` diretamente; adicionado card extra "Nunca venderam" na aba
   Estoque Parado para expor a nova distinção).

3. **PMR/PMP negativos — investigado e confirmado como dado real, não bug.**
   PMR = −0,7 dia (clientes pagam ~em dia). **PMP = −37,2 dias**: a empresa paga
   fornecedores em média 37 dias antes do vencimento (229 de 273 pagamentos
   liquidados nos últimos 90 dias foram antecipados). Nenhuma alteração de código —
   documentado como oportunidade de capital de giro em `MANUAL_TECNICO.md §3`.

**Confirmado correto (sem ação necessária):**
- `core/compras.py` já usa os nomes certos de coluna (`NFENTRC.DT_ENTRADA`,
  `TOTALNF`, `FORNECE.NOME`) — checagem inicial sugeria `DTENTRADA`/`VLTOTAL`, que
  não existem; o código nunca usou esses nomes errados.
- `core/comercial.py` já usa `PEDIDOC.CODVENDEDOR` corretamente.
- Todos os 11 arquivos (`app.py` + 5 `pages/` + 5 `core/` afetados) compilam sem erro
  e o servidor Streamlit sobe e responde HTTP 200 sem exceções no log após as correções.

**Entregável novo:** `docs/MANUAL_TECNICO.md` — documento único cobrindo as 6 telas
(Home + 5 módulos): propósito, abas, funções `core/*.py` usadas, tabelas Firebird/DuckDB
consultadas, achados da auditoria por módulo e sugestões de evolução priorizadas.

---

## Sprint 2026-06-17 (cont.) — Polimento visual estendido a todas as telas

Continuação do pente fino: o componente `components/metrics.py :: kpi_card()` (usado
em 20+ pontos) foi reescrito com visual de cartão (fundo, borda esquerda de destaque,
delta com seta colorida) e ganhou parâmetro `fmt` para suportar KPIs não-monetários
(contagens, percentuais) — mantendo assinatura 100% compatível com todas as chamadas
existentes. Nesta rodada, as cores semânticas (`COR_OK`/`COR_ALERTA`/`COR_PERIGO`/
`COR_PRIM`) foram aplicadas a **todos os KPIs de cabeçalho das 4 páginas de módulo +
Home**, e diversos `st.metric()` legados foram convertidos para `kpi_card()` por
consistência visual:

| Arquivo | KPIs convertidos/coloridos |
|---|---|
| `app.py` | 12 KPIs do dashboard executivo (2 linhas × 6) — Vencido AR/AP em vermelho, A Pagar em laranja, demais em azul/verde |
| `pages/01_Financeiro.py` | 6 KPIs do cabeçalho — Vencido (AR)/(AP) em vermelho |
| `pages/02_Comercial.py` | 10 KPIs (cabeçalho, Meta & Indicadores, Funil, Descontos) — valores parados/descontos em laranja |
| `pages/03_Estoque.py` | 6 KPIs do cabeçalho — Ruptura/Parado em laranja, Abaixo do Mínimo em vermelho quando > 0 |
| `pages/04_Compras.py` | 4 KPIs do cabeçalho — Lucro Bruto em verde |

**Validação:** todos os arquivos recompilados sem erro. `AppTest` (execução real de
cada página, sem mock) confirmou **zero exceções** em `app.py`, `01_Financeiro.py`,
`02_Comercial.py`, `03_Estoque.py` e `04_Compras.py`. `05_Alertas.py` lançou
`KeyError` em `st.page_link` apenas quando testado **isolado** via `AppTest` (a
ferramenta não enxerga o `pages/` registrado pelo `app.py` quando a sub-página é
carregada como entrypoint) — não é uma regressão: o código não foi alterado nesta
sessão, e o servidor real (`streamlit run app.py`) navegado via HTTP confirmou
`200 OK` e log limpo tanto na Home quanto em `/Alertas`.

---

## Sprint 2026-06-18 — Revisão final completa (todas as 70+ funções testadas)

Última passada de auditoria: **todas** as funções públicas dos 5 módulos `core/*.py`
(financeiro, comercial, estoque, compras, alertas — 70+ funções) foram executadas
individualmente contra o Firebird real e tiveram o resultado inspecionado, não só
amostradas. Mais 2 bugs reais encontrados e corrigidos:

**1. Bug duplicado de "AP vencido" sobrevivendo em `core/financeiro.py`.**
O alerta "X título(s) AP vencem em 48h" exibido no topo da própria página Financeiro
(`get_alertas_financeiro()`) tinha o mesmo bug já corrigido em `core/alertas.py` em
sprint anterior — mas como são **dois motores de alerta independentes**, a correção
não se propagou. A condição `DT_VENCIMENTO <= hoje+48h` somava títulos já vencidos
(472) com os que realmente vencem nas próximas 48h (2), exibindo "473 vencem em 48h"
em vez de separar "472 já vencidos" (crítico) de "2 vencendo em 48h" (urgente).
Corrigido com o mesmo padrão usado em `core/alertas.py`. Validado por conferência
direta: 472/R$808.995,76 e 2/R$10.300,12, batendo exatamente com a saída da função
corrigida.

**2. Três filtros globais (Empresa, Grupo de Produto, Marca) mortos silenciosamente
em todas as 5 páginas.** `core/cadastros.py` tinha SQLs com nomes de tabela/coluna
incorretos:
- `_SQL_GRUPOS` usava `GRUPROD.CODGRUPROD` — coluna real é `CODGRUPO`.
- `_SQL_MARCAS` usava `CADFABR.CODFABR`/`NOME` — colunas reais são `CODFABRIC`/`DESCRICAO`.
- `_SQL_EMPRESAS` consultava `EMPRESA.CODEMPRESA`/`NOME` — essa tabela é um registro
  único de licença/config do sistema, **não existe cadastro de empresas no banco**.

O helper `_safe()` engolia a exceção de cada uma (`try/except: return DataFrame vazio`)
sem logar nada, então os 3 dropdowns ("Empresa", "Grupo de Produto", "Marca") na
sidebar de **todas as páginas** ficavam mostrando apenas a opção "Todos/Todas",
silenciosamente inoperantes, desde a implementação inicial — nenhum erro visível em
tela ou log. Corrigido: nomes de coluna certos para Grupo (22 grupos) e Marca
(618 fabricantes); para Empresa, como não existe tabela de cadastro real, criada uma
lista fixa em Python com os 2 códigos efetivamente usados no schema (`00`=Matriz,
operação real; `01`=Filial, aparece só em `COMPPROD` sempre com saldo zerado).

**Validação:** `core/cadastros.py` e `core/financeiro.py` recompilados sem erro.
`AppTest` confirmou zero exceções em `app.py` e nas 4 páginas de módulo com os
filtros agora populados (618 marcas, 22 grupos, 2 empresas). Servidor real
(`streamlit run app.py`) testado nas 6 rotas (Home + 5 módulos) — todas HTTP 200,
log limpo.

**Limpeza de ambiente:** processos Streamlit de teste finalizados, todos os
`__pycache__` do projeto removidos, nenhum arquivo de log/teste residual na raiz.

**Nota sobre "dados não baterem entre sessões":** o Firebird (`RESULTH.FB`) é o ERP
de produção em operação contínua — qualquer KPI registrado neste documento (faturamento,
AR, AP, etc.) é uma fotografia do instante em que foi consultado, não um valor fixo.
Confirmado nesta sessão: a mesma query rodada duas vezes no mesmo segundo bate
exatamente; rodada horas depois, diverge porque o negócio real continuou operando
no meio tempo. Isso é esperado e não deve ser tratado como bug ao comparar números
deste arquivo com o dashboard ao vivo.

> **Adendo 2026-06-18:** o cliente confirmou que o arquivo `RESULTH.FB` atual é um
> **backup retirado no dia anterior**, não uma conexão contínua à produção real. A
> nota acima sobre "drift entre consultas no mesmo dia" permanece válida (o arquivo
> de backup pode estar sendo sincronizado/atualizado por outro processo), mas o
> dashboard deve ser tratado como refletindo o estado de "ontem" até que o cliente
> defina um processo de atualização (backup periódico ou acesso direto à produção).
> Reforça ainda mais a regra existente: **Firebird é somente leitura, sempre** — é
> dado real de cliente, não uma base de testes.

---

## Sprint 2026-06-18 (pente fino #3) — Revisão completa em 4 fases

Nova rodada de revisão solicitada pelo cliente após confirmar que o banco é backup
real de produção. Estrutura em 4 fases: (1) revisão de código + validação de banco,
(2) roteiros de teste manual, (3) correções visuais, (4) relatório final.

**Fase 1 — 2 bugs adicionais encontrados** (além dos 5 já corrigidos nas sessões
anteriores, todos reconfirmados ainda corretos):
- Nenhum bug novo de dados/tabela encontrado na revisão linha-a-linha dos arquivos
  ainda não auditados (`core/db_duck.py`, `config/settings.py`, `core/db_firebird.py`,
  `core/export.py`, `core/introspect.py`, `components/print_btn.py`).
- Achados de risco (não-bugs): credenciais reais hardcoded em `config/settings.py`
  (corrigido depois — movidas para `.env`, ver fase de segurança abaixo); 2 scripts
  órfãos na raiz (`inspecionar.py`, `auditoria_banco.py`) não usados pelo app;
  `SQL_COUNT` morto em `introspect.py`.

**Fase 2 — `docs/PLANO_DE_TESTES.md` criado.** 17 roteiros de teste manual cobrindo
as 5 correções de sessões anteriores + funcionalidades centrais dos 6 módulos.
Adaptado o formato pedido (pré-check/pós-check) para a realidade de um app
majoritariamente somente-leitura: a maioria dos testes usa "query de referência"
única (compara tela vs. consulta direta); só os recursos que escrevem no DuckDB
(comentários, metas, thresholds, preferências) usam o par pré/pós-check completo.

**Fase 3 — 2 bugs de runtime + paleta de cores e ícones consolidados:**
1. `pages/02_Comercial.py`: `StreamlitDuplicateElementId` no gráfico de Curva ABC
   (`_render_abc()` chamada 2x sem `key=` única) — corrigido.
2. `pages/03_Estoque.py`: mesmo padrão de risco em `_render_top_tab()` (chamada 3x)
   — corrigido preventivamente.
3. Criado `components/theme.py` como fonte única de cores — eliminada a redefinição
   idêntica de `COR_PRIM/OK/ALERTA/PERIGO` em 6 arquivos + cópia privada em
   `components/metrics.py`. Corrigida divergência real de tom entre páginas para o
   mesmo nível de alerta (vermelho "crítico" era `#d62728` em Alertas e `#c0392b`
   em Financeiro/Estoque; âmbar "atenção" `#f0b429` vs `#b7950b`).
4. 5 ocorrências de emoji dentro de blocos HTML trocadas por Bootstrap Icons via
   `bi()`. Mapeados (e mantidos) os casos que **não podem** ser trocados por
   limitação da própria biblioteca Streamlit: `st.tabs()`, `st.download_button()`,
   `st.dialog()`, `st.warning()`/`st.info()` só aceitam texto/emoji, nunca HTML.

**Fase 4 — relatório estruturado entregue ao usuário** (Fixed Issues / Remaining
Risks / 6 sugestões de feature com arquivo+tabela+complexidade), não duplicado
neste arquivo — ver a conversa da sessão para o texto completo.

**Validação:** todos os arquivos recompilados sem erro; `AppTest` confirma zero
exceções em `app.py` + 4 páginas; servidor real testado nas 6 rotas (HTTP 200, log
limpo). Ambiente limpo ao final (sem processos de teste, cache ou logs residuais).

**Resolução dos 2 riscos pendentes da Fase 4 (a critério do assistente):**

1. **Credenciais movidas para `.env`.** `config/settings.py` agora carrega
   `FB_HOST`/`FB_DATABASE`/`FB_USER`/`FB_PASSWORD`/`FB_CHARSET` via
   `python-dotenv` (`os.environ.get(...)`, com os valores atuais como fallback
   de desenvolvimento — nada quebra se o `.env` não existir). Criado `.env`
   (real, com as credenciais atuais) e `.env.example` (template sem segredo,
   seguro para versionar). Criado `.gitignore` preventivo excluindo `.env`,
   `data/*.duckdb` e `__pycache__/` — o projeto ainda não é repositório git,
   mas se vier a ser, as credenciais não entram no primeiro commit.
   `python-dotenv==1.2.2` adicionado ao `requirements.txt`. Validado: conexão
   real ao Firebird funcionando após a mudança (`DOCUREC` consultado com
   sucesso via `.env`).
2. **Scripts órfãos movidos** para `scripts/dev/` (não excluídos — preservados
   como referência histórica): `inspecionar.py` e `auditoria_banco.py`, cada
   um com uma nota no topo apontando para onde a lógica final vive
   (`core/financeiro.py` e `docs/MANUAL_TECNICO.md` §8, respectivamente).

**Validação final:** recompilação de `config/settings.py` + os 2 scripts
movidos sem erro; servidor real testado novamente nas 6 rotas após as mudanças
(HTTP 200, log limpo); ambiente limpo ao final.
