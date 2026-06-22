# DB_REFERENCE — Banco Resulth (Firebird)

> Referência de consulta para desenvolvimento dos dashboards. Pensada para ser usada
> como contexto pelo Claude integrado no VSCode.
> Fonte: dicionário de tabelas do Resulth (1075 tabelas).

## Como usar esta referência (leia primeiro)

Esta referência é **curada**: em vez de repetir as 1075 tabelas (a maioria é de
fiscal/NFe/SPED/CTe/MDFe/OS/Posto/Materiais/Ecommerce/CallCenter e **não** entra nos
dashboards), ela mapeia só as tabelas que importam para o BI, **agrupadas por domínio**,
com os relacionamentos inferidos. Esse mapa é o que realmente agrega valor — porque o
"quais tabelas e como elas se ligam" é conhecimento de negócio que **não** está no schema.

### ⚠️ Limitação importante: só temos o nível de TABELA, não de COLUNA

O dicionário diz *o que cada tabela guarda*, mas não os nomes dos campos. Para escrever
SQL de verdade, você precisa das colunas. Duas formas de obter:

1. **Introspecção direta no Firebird** (recomendado — sempre reflete a base real):

   ```sql
   -- Colunas de uma tabela:
   SELECT TRIM(rf.RDB$FIELD_NAME)       AS campo,
          TRIM(f.RDB$FIELD_TYPE)        AS tipo,
          f.RDB$FIELD_LENGTH            AS tamanho,
          rf.RDB$NULL_FLAG              AS nao_nulo
   FROM   RDB$RELATION_FIELDS rf
   JOIN   RDB$FIELDS f ON f.RDB$FIELD_NAME = rf.RDB$FIELD_SOURCE
   WHERE  rf.RDB$RELATION_NAME = 'DOCUREC'
   ORDER  BY rf.RDB$FIELD_POSITION;

   -- Chaves primárias / estrangeiras:
   SELECT TRIM(rc.RDB$CONSTRAINT_NAME), rc.RDB$CONSTRAINT_TYPE,
          TRIM(rc.RDB$RELATION_NAME)
   FROM   RDB$RELATION_CONSTRAINTS rc
   WHERE  rc.RDB$RELATION_NAME = 'DOCUREC';
   ```

2. Dicionário de dados do fornecedor do Resulth, se houver acesso.

> **Próximo passo sugerido:** rodar a query de colunas nas ~30 tabelas centrais (listadas
> aqui) e me mandar o resultado. Aí eu enriqueço esta referência com os campos reais e a
> gente sai do "conceitual" para SQL pronto.

---

## 1. Cadastros-base (alimentam os filtros globais)

| Tabela | Guarda | Uso no BI |
|--------|--------|-----------|
| `EMPRESA` | Dados da empresa | Filtro **Empresa** |
| `FILIAIS` | Cadastro das filiais | Filtro **Empresa/Filial** (multiempresa) |
| `CLIENTE` | Cadastro de clientes | Filtro **Cliente**; dimensão em vários módulos |
| `FORNECE` | Cadastro de fornecedores | Filtro **Fornecedor** |
| `VENDEND` | Cadastro de vendedores | Filtro **Vendedor** |
| `PRODUTO` | Cadastro de produtos | Dimensão produto |
| `GRUPROD` | Grupos de produtos | Filtro **Grupo de Produto** |
| `SUBGRUP` | Subgrupos de produtos | Detalhe de grupo |
| `FAMILIA` | Famílias dos produtos | Possível dimensão |
| `CADFABR` | Fabricantes | ⚠️ candidato ao filtro **Marca** (confirmar) |
| `TIPODOC` | Tipos de documento (AV, BO, CF, CO, CT, DX, FT, NF, PZ) | Classificar lançamentos |
| `FORPGTO` | Formas de pagamento | Quebra por forma de pgto (meta comercial) |
| `CONDPAG` | Prazos de pagamento | Condições |
| `CENTROCUSTO` | Centros de custo | Rateios / análise |

> ⚠️ **Filtro "Marca":** não há tabela `MARCA` explícita. Provavelmente é um campo no
> `PRODUTO` ou está mapeado em `CADFABR` (fabricante). Confirmar via colunas do `PRODUTO`.

---

## 2. Financeiro

### Contas e bancos
| Tabela | Guarda |
|--------|--------|
| `CONTAS` | Cadastro das **contas bancárias** |
| `BANCOS` | Cadastro dos bancos |
| `AGENCIA` | Cadastro das agências |
| `PCONTAS` | Cadastro de **contas caixa** |
| `SALDOST` | Inicialização de saldo de caixa **+ registros de saldo diários** ⭐ |
| `SALDOSC`, `SALDOSCB` | Saldos (confirmar conteúdo) |
| `MOVIBAN` | **Movimentações bancárias** — fonte do extrato bancário ⭐ |
| `MOVIMEN` | Movimentações em dinheiro — fonte do livro caixa |
| `TIPOLAN` | Tipos de lançamentos bancários |

### Contas a Receber (AR)
| Tabela | Guarda |
|--------|--------|
| `DOCUREC` | **Documentos do contas a receber** (títulos) ⭐ |
| `MOVIREC` | Movimentações dos títulos a receber (entrada, liquidação, estorno…) ⭐ |
| `MOVIREC2` | Movimentações complementares |
| `DOCURECFATURA` | Documentos a receber agrupados (fatura) |
| `DOCAGRUPADOS` | Documentos do receber agrupados |
| `ENCELIQ` | Liquidações de documentos a receber |
| `LIQLOTERECEBER` | Liquidação de receber em lote |
| `PERICXA` | Período a receber de lançamentos do caixa |

### Contas a Pagar (AP)
| Tabela | Guarda |
|--------|--------|
| `DOCUPAG` | **Contas a Pagar** (manual + automático de entradas) ⭐ |
| `MOVIPAG` | Movimentações dos títulos a pagar ⭐ |
| `DOCUPAGFATURA` | Documentos a pagar agrupados |
| `LIQLOTEPAGAR`, `LIQLOTEPAGARPORTIPO` | Liquidação de pagar em lote |
| `RATDOCUPAG` | Rateio de documentos a pagar |

### Fluxo de caixa / previsões
| Tabela | Guarda |
|--------|--------|
| `FLUXOCX` | Fluxo de caixa |
| `FLUXOCX_REALIZADO` | Fluxo de caixa realizado |
| `PREVISAOFLUXO` | Previsão de fluxo |
| `PREVISAOFORNECEDOR` | Previsão por fornecedor |
| `CADPREVPAG`, `CADPREVPAGCC` | Previsões de pagamento |
| `OCPREVPAGTO` | Previsão de pagamento |

### Caixa / fechamento
| Tabela | Guarda |
|--------|--------|
| `ABERTURACAIXA` | Abertura de caixa |
| `FECHACXAC` / `FECHACXAI` | Fechamento de caixa financeiro (cabeçalho / formas) |
| `SANGRIA`, `MVSANGSUPR` | Sangria e suprimento |
| `MVLANCDESP`, `MVLANCREC` | Lançamentos de despesa / receita |
| `LANCAMENTOS_AVULSOS` | Lançamentos avulsos |

---

## 3. Comercial / Vendas

| Tabela | Guarda |
|--------|--------|
| `ENCEFAT` | **Faturamento das vendas** (NFe, PDV, NFC-e, Pré-Venda) ⭐ |
| `ENCCARTAO` | Vendas no cartão |
| `CONVENCEFAT` | Detalhe de convênio das vendas cartão/convênio |
| `NFSAIDC` / `NFSAIDI` | Cabeçalho / itens de NF, Cupom, NFC-e emitidos ⭐ |
| `PEDIDOC` / `PEDIDOI` | Cabeçalho / itens dos pedidos (relaciona por `CODPEDIDO`) ⭐ |
| `PEDIDOIDEVOLUCAO` | Itens de devolução |
| `METAFATURAMENTOMENSAL` | **Metas de faturamento mensal** ⭐ |
| `META`, `METAVENDEDOR`, `METACOMISSAO`, `METAPORVALOR` | Metas por vendedor/comissão |
| `METAGRPPROD`, `METAGRPPROD_GRUPO_ITEM`, `METAGRPPROD_PROD_ITEM` | Metas por grupo/produto |
| `VENDAPERDIDA` | Venda perdida |

> Drill-down Faturamento: `ENCEFAT`/`NFSAIDC` → `CLIENTE` → `PEDIDOC` → `PEDIDOI`.

---

## 4. Produtos / Estoque

| Tabela | Guarda |
|--------|--------|
| `COMPPROD` | **Estoque, custos, preço médio, preço de entrada** (1 registro por produto) ⭐⭐ |
| `MVGERAL` | **Movimentações de entrada/saída de produtos** (movimento de estoque) ⭐ |
| `MVGERAL2` | Movimentações complementares |
| `MVENTSAI` | Entrada/saída (faturamento) |
| `ESTOQUEMENSAL`, `ITEMESTOQUEMENSAL` | Posição de estoque mensal |
| `ESTOQUELOCAL`, `MOVESTOQUELOCAL` | Estoque por local |
| `INVENTA` | Itens de inventário |
| `CURVAABC`, `CURVAABCGRADE` | Curva ABC (já calculada pelo ERP — verificar) |
| `PRECOFILIAL` | Preço, lucro e markup por filial |
| `PRECOCUSTOVENDACALCULADO` | Custo/venda calculado |
| `LOGPRECOSPRODUTO` | Histórico de alteração de preços |

> ⭐⭐ `COMPPROD` é central: dela saem **estoque atual, valor ao custo e à venda, e o custo
> usado no cálculo de lucro bruto/CMV**.

---

## 5. Compras

| Tabela | Guarda |
|--------|--------|
| `NFENTRC` / `NFENTRI` | **Cabeçalho / itens da NF de entrada** (entrada de produtos) ⭐ |
| `NFENTRCMAT` | NF de notas diversas |
| `SOLICITACAOCOMPRAC` / `SOLICITACAOCOMPRAI` | Solicitação de compra (cab/itens) |
| `COTACAOC` / `COTACAOI` | Cotações (cab/itens) |
| `RELPRFO` | Relação produto × fornecedor (inclui fornecedor principal) ⭐ |
| `PREVISAOFORNECEDOR` | Previsão por fornecedor |
| `CONFERENCIAOC`, `CONFERENCIAOC_ITENS` | Conferência de ordem de compra |

> Drill-down Compras: `FORNECE` → `NFENTRC` (pedido/entrada) → `NFENTRI` (itens).

---

## 6. Comentários gerenciais (a criar — não existe no ERP)

Os "comentários gerenciais" e os snapshots históricos **não têm tabela no Resulth**.
Devem ser criados no **store analítico (DuckDB)**, nunca no Firebird do ERP:

- `comentarios(indicador, periodo, texto, autor, criado_em)`
- `snap_inadimplencia(data, valor_vencido, qtd_titulos, …)`
- `snap_saldo_bancario(data, conta, saldo)` (se não for reconstruível de `SALDOST`/`MOVIBAN`)

---

## 7. Mapa de relacionamentos inferidos (confirmar via colunas)

```
CLIENTE  ──< DOCUREC  ──< MOVIREC          (cliente → títulos a receber → histórico)
FORNECE  ──< DOCUPAG  ──< MOVIPAG          (fornecedor → títulos a pagar → histórico)
FORNECE  ──< NFENTRC  ──< NFENTRI          (fornecedor → entrada → itens comprados)
CLIENTE  ──< PEDIDOC  ──< PEDIDOI          (cliente → pedido → itens)
PEDIDOC  ──  ENCEFAT / NFSAIDC             (pedido → faturamento / nota)
PRODUTO  ──  COMPPROD                      (produto → estoque/custo, 1:1)
PRODUTO  ──< MVGERAL                       (produto → movimentações de estoque)
PRODUTO  ──< RELPRFO  >── FORNECE          (produto ↔ fornecedor)
CONTAS   ──< MOVIBAN ;  CONTAS ──< SALDOST (conta → movimento/saldo)
```

> As ligações acima são **inferidas pelos nomes e descrições**. Os campos de chave
> (ex.: `CODPEDIDO`, código de cliente/fornecedor) precisam ser confirmados com a
> introspecção de colunas da §"Como usar".
