# MÓDULO COMPRAS — Especificação e Implementação

> Fase 4 do roadmap. Cobre análise de compras, fornecedores, dependência,
> rentabilidade e alertas de compras.
> **Data de implementação:** 2026-06-12

---

## Requisitos atendidos

| Requisito | Status | Observação |
|-----------|--------|------------|
| Compras do mês + evolução 12 meses | ✅ | Aba "Evolução de Compras" — histórico 13 meses |
| Top Fornecedores por Relevância | ✅ | Aba "Fornecedores" — top 15 gráfico horizontal + tabela |
| Dependência de Fornecedores | ✅ | Aba "Dependência" — pizza top10, concentração top1/3/10 |
| Rentabilidade por Fornecedor | ✅ | Aba "Rentabilidade" — compras × vendas × lucro × margem |
| Top 10 por Lucro Bruto Gerado | ✅ | Sub-seção na aba "Rentabilidade" |
| Alertas — Produtos comprados sem giro | ✅ | Aba "Alertas" sub-aba "Sem Giro" |
| Alertas — Estoque parado por fornecedor | ✅ | Aba "Alertas" sub-aba "Parado por Fornecedor" |
| Drill-down Fornecedor → NFs → Itens | ✅ | Dialog ao clicar em fornecedor |
| Exportação Excel + PDF | ✅ | Por aba |
| Comentários gerenciais | ✅ | Por aba |
| Impressão | ✅ | Botão no cabeçalho |

---

## Fontes de dados (tabelas Firebird)

| Tabela | Uso | Campos principais |
|--------|-----|-------------------|
| `NFENTRC` | Cabeçalho das NFs de entrada | `NUMERONF`, `CODFORNEC`, `CODEMPRESA`, `DTEMISSAO`, `DTENTRADA`, `VLTOTAL` |
| `NFENTRI` | Itens das NFs de entrada | `NUMERONF`, `CODFORNEC`, `CODEMPRESA`, `CODPROD`, `QTDE`, `VLUNIT`, `VLDESCONTO` |
| `FORNECE` | Cadastro de fornecedores | `CODFORNEC`, `FORNECEDOR`, `FANTASIA` |
| `RELPRFO` | Relação Produto–Fornecedor principal | `CODPROD`, `PRINCIPAL` (=CODFORNEC) |
| `MVGERAL` TM='55' | Vendas PDV (para rentabilidade) | `CODPROD`, `QUANTIDADE`, `PRECOVENDA` |
| `COMPPROD` EMP='00' | Custo atual + estoque (CMV proxy) | `CODPROD`, `PRECOCUSTO`, `ESTOQUE` |
| `PRODUTO` | Descrição e grupo | `CODPROD`, `DESCRICAO`, `CODGRUPO` |
| `GRUPROD` | Nome do grupo | `CODGRUPO`, `DESCRICAO` |

### JOIN correto entre NFENTRC e NFENTRI

```sql
FROM NFENTRI i
JOIN NFENTRC n ON n.CODEMPRESA = i.CODEMPRESA
               AND n.NUMERONF  = i.NUMERONF
               AND n.CODFORNEC = i.CODFORNEC
```

**Importante:** a PK de NFENTRC/NFENTRI envolve **3 campos** — `CODEMPRESA + NUMERONF + CODFORNEC`.
Fazer JOIN somente por `NUMERONF` produz produto cartesiano (números de NF repetem entre fornecedores).

---

## Decisões técnicas

### Rentabilidade — Python merge, não SQL pesado

Para calcular rentabilidade por fornecedor, seriam necessários 4+ JOINs grandes no Firebird
(NFENTRC × FORNECE × RELPRFO × MVGERAL × COMPPROD). Dado o SQL Dialect 1 e a ausência de
window functions, a abordagem adotada é:

1. Buscar 4 DataFrames separados do Firebird: compras, vendas (MVGERAL TM=55), relação produto-forn (RELPRFO), estoque (COMPPROD)
2. Fazer os merges em Pandas no Python
3. Calcular CMV = QTD_VENDIDA × COMPPROD.PRECOCUSTO (custo atual)

**Limitação:** COMPPROD.PRECOCUSTO é o custo atual, não histórico — mesma limitação do módulo Estoque.

### NOME_EXIB — coluna computada em Python

O nome exibido para o fornecedor é calculado assim:
```python
NOME_EXIB = FANTASIA.strip() se FANTASIA não vazio, senão FORNECEDOR
```
Esta coluna não vem do Firebird — é computada em Python antes de qualquer merge.

### Produtos sem giro — lógica

```
produto sem giro = foi comprado no período (NFENTRI)
                   AND não teve venda PDV (MVGERAL TM='55') no mesmo período
```
- Comparação feita via Python: `~isin(codprods_vendidos)`
- Inclui QTD e VALOR em estoque atual como referência

### Estoque parado por fornecedor — lógica

```
parado N dias = COMPPROD.ESTOQUE > 0
                AND MAX(DT_MOV MVGERAL TM='55') < (hoje - N dias)
                Agrupado pelo RELPRFO.PRINCIPAL (fornecedor principal do produto)
```

### Concentração — limiares de alerta

| Indicador | Limiar warning | Limiar danger |
|-----------|---------------|---------------|
| Top 1 fornecedor (%) | 24% | 30% |
| Top 3 fornecedores (%) | 48% | 60% |
| Top 10 fornecedores (%) | 64% | 80% |

---

## Estrutura de arquivos

```
core/domain/compras.py           — funções de dados (8 funções)
pages/04_Compras.py       — página Streamlit (6 abas)
docs/MODULO_COMPRAS.md    — este arquivo
```

### Funções em `core/domain/compras.py`

| Função | Retorno | Uso |
|--------|---------|-----|
| `get_historico_compras(meses=13)` | DataFrame mensal com PERIODO | Aba Evolução |
| `get_compras_por_fornecedor(ini, fim)` | DataFrame com PARTICIPACAO, PARTICIPACAO_ACUM | Aba Fornecedores |
| `get_nfs_fornecedor(codfornec, ini, fim)` | DataFrame por NF | Dialog nível 1 |
| `get_itens_nf_entrada(codfornec, numeronf)` | DataFrame de itens | Dialog nível 2 |
| `get_rentabilidade_fornecedor(ini, fim)` | DataFrame com FAT, CMV, LUCRO, MARGEM | Aba Rentabilidade |
| `get_produtos_sem_giro(ini, fim)` | DataFrame de produtos comprados sem venda | Aba Alertas |
| `get_estoque_parado_por_fornecedor(dias=90)` | DataFrame agrupado por PRINCIPAL | Aba Alertas |
| `get_kpis_compras(ini, fim)` | Dict: total_comprado, qtd_nf, qtd_fornec | KPIs do cabeçalho |

---

## Abas do módulo

| Aba | Conteúdo |
|-----|----------|
| 📈 Evolução de Compras | Gráfico barras 13 meses + métricas (max/min/média) + tabela histórica |
| 🏭 Fornecedores | Top 15 gráfico horizontal + tabela completa + drill-down |
| ⚖️ Dependência | Pizza top10, concentração top1/3/10 + alerta automático |
| 💰 Rentabilidade | Barras grupadas (comprado×faturado×lucro) + Top 10 lucro bruto + tabela + drill-down |
| 🚨 Alertas | Sub-abas: Sem Giro + Parado por Fornecedor |
| ⚙️ Configurações | Comentários gerenciais gerais + informações do módulo |

### Drill-down implementado

```
Clique no fornecedor (qualquer aba) → dialog "Compras do Fornecedor"
  └─ Lista NFs do fornecedor no período
       └─ Clique na NF → Itens da NF (NFENTRI)
```

---

## Volumetria do banco (2026-06-12)

| Métrica | Valor |
|---------|-------|
| Total comprado (3 meses) | R$ 944.923,90 |
| NFs de entrada | 192 |
| Fornecedores ativos | 88 |
| Maior fornecedor | CONDUMIG (25,6% — R$ 242.288) |
| Margem média (fornecedor topo) | CONDUMIG 84%, MARGIRIUS 45%, KRONA 50% |
| Produtos sem giro | 877 — R$ 231.629 imobilizado |
| Estoque parado por fornecedor (>90d) | KRONA 154 SKUs, CONDUMIG 4 SKUs R$ 22.926 |

---

## Observações para próximas sessões

1. **CONDUMIG concentração 25,6%:** representa risco de dependência de fornecedor.
   Verificar com o cliente se há contratos de exclusividade ou alternativas.

2. **Rentabilidade proxy:** CMV via COMPPROD.PRECOCUSTO atual — custo pode ter variado.
   Para histórico mais preciso, usar NFENTRI.VLUNIT × QTD_VENDIDA (custo da NF de entrada).

3. **RELPRFO.PRINCIPAL sem cadastro:** produtos sem registro em RELPRFO não aparecem no
   "estoque parado por fornecedor" — verificar cobertura da relação.

4. **CURVAABC de compras:** não implementada neste módulo — seria: top 80% por valor comprado = A.
   Pode ser adicionado se o cliente solicitar.

5. **Próximo módulo:** Alertas (Fase 5) — consolidar alertas de todos os módulos em uma tela única.
