# MÓDULO ESTOQUE/PRODUTOS — Especificação e Implementação

> Fase 3 do roadmap. Cobre simultaneamente o **Módulo Produtos** e o **Módulo Estoque**
> do documento de requisitos (compartilham as mesmas tabelas-base).
> **Data de implementação:** 2026-06-12

---

## Requisitos atendidos

### Módulo Produtos
| Requisito | Status | Observação |
|-----------|--------|------------|
| Top 10 por quantidade vendida | ✅ | Aba "Top Produtos" |
| Top 10 por faturamento | ✅ | Aba "Top Produtos" |
| Top 10 por lucro bruto | ✅ | Lucro = FAT - (QTD × PRECOCUSTO atual) |
| Produtos Sem Venda (30/60/90/180/365d) | ✅ | Aba "Top Produtos" + select slider |

### Módulo Estoque
| Requisito | Status | Observação |
|-----------|--------|------------|
| Estoque Atual — SKUs, Qtd física, Valor custo, Valor venda | ✅ | Aba "Estoque Atual" |
| Estoque Parado — faixas 30/60/90/180/365d | ✅ | Aba "Estoque Parado" |
| Controle Operacional — ruptura e abaixo do mínimo | ✅ | Aba "Controle" |
| Curva ABC de estoque | ✅ | Aba "Curva ABC" |
| Giro de estoque por grupo | ✅ | Aba "Giro por Grupo" |
| Drill-down Produto → Movimentações | ✅ | Dialog ao clicar em qualquer produto |
| Exportação Excel + PDF | ✅ | Por aba |
| Comentários gerenciais | ✅ | Por aba |
| Impressão | ✅ | Botão no cabeçalho |

---

## Fontes de dados (tabelas Firebird)

| Tabela | Uso | Campo-chave |
|--------|-----|-------------|
| `COMPPROD` (EMP='00') | Estoque atual, custo, preço | `CODPROD`, `ESTOQUE`, `PRECOCUSTO`, `PRECONF`, `ESTMINIMO` |
| `MVGERAL` TIPOMOV='55' | Vendas PDV (saídas) | `CODPROD`, `DT_MOVIMENTO`, `QUANTIDADE`, `PRECOVENDA` |
| `MVGERAL` TIPOMOV='01' | Entradas NF | `CODPROD`, `DT_MOVIMENTO`, `QUANTIDADE`, `PRECOCUSTO` |
| `PRODUTO` | Descrição, grupo, ativo | `CODPROD`, `DESCRICAO`, `CODGRUPO`, `ATIVO` |
| `GRUPROD` | Nome do grupo | `CODGRUPO`, `DESCRICAO` |

### MVGERAL — Dicionário de TIPOMOV
| TIPOMOV | Significado | QTD |
|---------|-------------|-----|
| `55` | Venda PDV (saída por venda) — TIPOAGENTE='C' | 9.481 |
| `01` | Entrada NF (compra de fornecedor) — TIPOAGENTE='F' | 1.273 |
| `09` | Saída consignação/orçamento (PRECOVENDA=0) | 557 |
| `61` | Devolução de entrada | 100 |
| `05` | Devolução de venda | 95 |
| `06` | Ajuste de saída | 4 |
| `11` | Ajuste de entrada | 3 |

**Vendas PDV:** apenas TIPOMOV='55' é usado para cálculos de venda, faturamento e giro.
TIPOMOV='09' tem PRECOVENDA=0 — não entra em faturamento.

---

## Decisões técnicas

### PRECONF (preço de venda em COMPPROD) = 0
O campo `PRECONF` está zerado para a maioria dos produtos. Confirmado na sessão anterior.
- **Impacto:** "Valor de Venda" do estoque exibe `—` quando PRECONF=0
- **Exibição:** a coluna é mantida na tabela para os produtos que têm preço cadastrado
- **Lucro bruto:** calculado como FAT_TOTAL (MVGERAL.PRECOVENDA × QUANTIDADE) menos CMV (QTD × COMPPROD.PRECOCUSTO)

### PRECOCUSTO em MVGERAL tipo '55' = 0 para muitos produtos
Produtos vendidos no PDV frequentemente têm PRECOCUSTO=0 na movimentação de saída.
- **Solução:** lucro bruto usa `COMPPROD.PRECOCUSTO` (custo atual) como proxy do CMV histórico
- **Limitação:** custo pode ter mudado — é uma aproximação aceitável para análise gerencial

### Empresa do estoque: CODEMPRESA='00'
`COMPPROD` tem 2 registros por produto: EMP='00' (saldo real) e EMP='01' (sempre zero).
- Todas as queries de estoque filtram por `CODEMPRESA='00'`
- Filtros globais de empresa do sidebar não são aplicados ao estoque (não há correspondência)

### Estoque parado — lógica
```
produto parado = COMPPROD.ESTOQUE > 0
                AND (não existe MVGERAL TIPOMOV='55' com DT_MOVIMENTO >= (hoje - N dias))
```
- Calculado em Python com merge entre COMPPROD e MAX(DT_MOVIMENTO) por produto
- Produtos que nunca foram vendidos têm `ULT_VENDA = NaT` → considerados parados há 9999 dias

### Curva ABC — base de cálculo
```
VALOR_CUSTO = COMPPROD.ESTOQUE × COMPPROD.PRECOCUSTO
Classe A = produtos que representam 80% do valor total (ordenado por VALOR_CUSTO DESC)
Classe B = 80% a 95%
Classe C = acima de 95%
```

### Giro de estoque — limitação
```
GIRO = Σ(FAT_VENDIDO no período) / Σ(VALOR_CUSTO em estoque hoje)
```
- "Valor médio em estoque" seria mais preciso, mas exige snapshots diários
- Usa snapshot atual como proxy — adequado para análise gerencial
- Faturamento baseado em MVGERAL TIPOMOV='55' × PRECOVENDA

---

## Estrutura de arquivos

```
core/domain/estoque.py          — funções de dados (get_estoque_geral, get_kpis_estoque, etc.)
pages/03_Estoque.py      — página Streamlit (7 abas)
docs/MODULO_ESTOQUE.md   — este arquivo
```

---

## Abas do módulo

| Aba | Conteúdo |
|-----|----------|
| 🏆 Top Produtos | Top 10 por qtd, faturamento, lucro bruto + Sem venda no período |
| 📦 Estoque Atual | KPIs + distribuição por grupo (pizza/barras) + tabela filtrável |
| ⏰ Estoque Parado | KPIs por faixa + gráfico por grupo + tabela drill-down |
| 🚨 Controle | Ruptura (sem estoque) e Abaixo do mínimo |
| 📊 Curva ABC | Cards A/B/C + gráfico de barras + curva acumulada + tabela |
| 🔄 Giro por Grupo | Gráfico de barras (giro × grupo) + tabela + linha de referência giro=1x |
| ⚙️ Configurações | Comentários gerais + informações do módulo |

### Drill-down implementado
```
Produto (qualquer aba) → dialog "Movimentações do Produto" (últimas 200 do MVGERAL)
```
- Clicar em qualquer linha de produto abre o dialog com histórico completo
- Exibe: Data, Tipo, Quantidade, Custo unit., Venda unit., Estoque anterior

---

## Volumetria do banco (2026-06-12)

| Métrica | Valor |
|---------|-------|
| Total SKUs | 9.859 |
| Com estoque | 2.029 (aprox.) |
| MVGERAL TIPOMOV=55 | 9.481 registros |
| Estoque parado 90d | ~430 SKUs, R$ 139.204 |
| Grupo mais vendido | Cabos e conexões |

---

## Observações para próximas sessões

1. **PRECONF zerado:** confirmar com o cliente se o preço de venda está cadastrado em
   outra tabela (ex.: `PRECOFILIAL`) ou se o ERP usa outra lógica de precificação.
   Se confirmado que não existe, remover a coluna "Valor venda" do estoque para evitar confusão.

2. **Giro — snapshots diários:** para ter "valor médio em estoque" real, seria necessário
   implementar snapshot diário em DuckDB (ainda não implementado). Anotar para Fase 7 (Polimento).

3. **TIPOMOV='09':** saída com PRECOVENDA=0. Pode ser consignação, orçamento ou outro tipo.
   Confirmar com o cliente se deve entrar no cálculo de "produtos vendidos" para estoque parado.
   Por ora, não é considerado como venda.

4. **Curva ABC do ERP:** a tabela `CURVAABC` existe no Resulth. Investigar se já está calculada
   e se os critérios coincidem com o dashboard. Pode ser útil como dado de referência.
