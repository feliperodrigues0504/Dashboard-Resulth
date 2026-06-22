# DASHBOARDS

## REQUISITOS GERAIS

### Exportação e Impressão

Todos os dashboards deverão possuir:

- Exportação para Excel (.xlsx)
- Exportação para PDF
- Botão de impressão

Impressão contendo:

- Data da emissão
- Período analisado

### Drill Down (Obrigatório)

- Todos os dashboards deverão permitir detalhamento progressivo até o documento de origem.

**Exemplos:**

- **Faturamento:** Faturamento → Cliente → Pedido → Itens do Pedido
- **Inadimplência:** Inadimplência → Cliente → Título → Histórico
- **Estoque:** Estoque Parado → Grupo de Produtos → Produto → Movimentações
- **Compras:** Fornecedor → Pedido de Compra → Itens Comprados

### Filtros Globais

Todos os dashboards deverão permitir:

- Período
- Empresa
- Vendedor
- Cliente
- Fornecedor
- Grupo de Produto
- Marca

### Comparativos Históricos

Sempre que aplicável:

- Mês atual x mês anterior
- Mês atual x mesmo mês do ano anterior
- Acumulado do ano

### Comentários Gerenciais

- Permitir registrar observações relacionadas ao período ou indicador.

### Performance

Os dashboards deverão ser desenvolvidos com foco em desempenho, evitando consultas excessivamente pesadas sobre a base operacional.

Sempre que possível:

- Utilizar consultas otimizadas
- Carregar dados sob demanda
- Atualizar apenas dashboards acessados
- Evitar recálculo simultâneo de todos os indicadores

---

## TELA INICIAL

- Tela inicial totalmente personalizável.
- Sistema de Favoritos (Adicionar aos Favoritos).
- Permitir adicionar e remover dashboards.
- Permitir reorganizar dashboards.
- Permitir redimensionar dashboards.
- Salvar preferências do usuário.
- Exibir data e hora da última atualização dos dados.

---

## MÓDULO FINANCEIRO

### Saldo Bancário

- Saldo individual por conta
- Saldo consolidado (somatório de todas as contas)
- Evolução dos últimos 30 dias

### Fluxo de Caixa

- Recebimentos previstos
- Pagamentos previstos
- Projeção para:
  - 7 dias
  - 15 dias
  - 30 dias
  - 60 dias
  - 90 dias

**Drill Down:** Fluxo de Caixa → Dia → Recebimentos/Pagamentos → Documento → Título

### Contas a Receber

- Valor total vencido
- Quantidade de títulos vencidos
- Ranking de clientes inadimplentes

**Faixas:**

- 1 a 30 dias
- 31 a 60 dias
- 61 a 90 dias
- Acima de 90 dias

### Contas a Pagar

- Vencimentos em 7 dias
- Vencimentos em 15 dias
- Vencimentos em 30 dias
- Vencimentos em 60 dias
- Vencimentos em 90 dias

Separação por fornecedor.

### Inadimplência

- Valor vencido
- Evolução da inadimplência

### Posição de Caixa

- Saldo Bancário Consolidado (somatório de todas as contas)
- Contas a Receber em Aberto
- Estoque ao Custo
- Contas a Pagar em Aberto

**Capital Operacional:**

> Caixa + Receber + Estoque – Pagar

---

## MÓDULO COMERCIAL

### Meta Comercial

- Meta do mês

Filtrar somente documentos faturados, separados por:

- Dinheiro
- PIX
- Cartão Débito
- Cartão Crédito (detalhamento por quantidade de parcelas)
- Boleto

### Indicadores

- Total faturado
- Percentual da meta atingido
- Projeção de fechamento do mês

### Faturamento

- Dia
- Semana
- Quinzena
- Mês

**Comparativos:**

- Mês anterior
- Mesmo mês do ano anterior

### Ticket Médio

- Geral
- Por vendedor

### Top Clientes

- Top 10 por faturamento
- Top 10 por lucro bruto (valor final da venda – custo dos produtos)

### Clientes Sem Comprar

- 30 dias
- 60 dias
- 90 dias
- 180 dias

### Clientes com Queda de Compras

Top 10 clientes com maior redução de compras.

Exibir (por cliente):

- Média dos últimos 6 meses
- Compras dos últimos 30 dias
- Percentual de queda
- Valor perdido

### Concentração de Faturamento

**Por Clientes**

- Participação percentual dos Top 10 clientes
- Participação individual

**Por Produtos**

- Participação percentual dos Top 20 produtos
- Participação individual

### Sazonalidade

Comparativo dos últimos 24 meses para:

- Faturamento
- Compras
- Margem Bruta

---

## MÓDULO PRODUTOS

### Top Produtos

- Top 10 por quantidade vendida
- Top 10 por faturamento
- Top 10 por lucro bruto

**Definição de Lucro Bruto:** Lucro Bruto = Valor de Venda - Custo da Mercadoria Vendida (CMV)

### Produtos Sem Venda

Top 10 por valor parado.

**Filtros:**

- 30 dias
- 60 dias
- 90 dias
- 180 dias
- 365 dias

---

## MÓDULO ESTOQUE

### Estoque Atual

- Quantidade de SKUs (produtos cadastrados)
- Quantidade física em estoque (produtos cadastrados vezes a quantidade em estoque de cada item)
- Valor de custo
- Valor de venda

### Estoque Parado

**Faixas:**

- 30 dias
- 60 dias
- 90 dias
- 180 dias
- 365 dias

**Exibir:**

- Quantidade de SKUs
- Quantidade física
- Valor de custo
- Valor de venda

### Controle Operacional

- Produtos abaixo do estoque mínimo
- Produtos sem estoque (ruptura)

### Curva ABC de Estoque

Classe A | Classe B | Classe C

**Exibir:**

- Quantidade de SKUs
- Valor investido
- Percentual sobre estoque total

### Giro de Estoque por Grupo de Produtos

**Exibir:**

- Grupo de Produtos
- Valor médio em estoque
- Valor vendido no período
- Giro de estoque

---

## MÓDULO COMPRAS

### Compras

- Compras do mês
- Evolução das compras (últimos 12 meses)

### Fornecedores

**Top Fornecedores por Relevância**

Exibir:

- Compras
- Vendas geradas
- Lucro bruto gerado
- Estoque atual
- Estoque parado
- Participação percentual

### Dependência de Fornecedores

Exibir:

- Participação percentual individual
- Participação dos Top 10 fornecedores

### Rentabilidade por Fornecedor

Exibir:

- Compras
- Vendas
- Lucro bruto
- Margem %

### Top 10 Fornecedores por Lucro Bruto Gerado

Exibir:

- Valor
- Percentual sobre o lucro total

### Alertas de Compras

- Produtos comprados sem giro
- Estoque parado por fornecedor

---

## MÓDULO ALERTAS

### Produtos

- Produtos sem venda acima de 180 dias
- Produtos abaixo do estoque mínimo
- Produtos sem estoque

### Clientes

- Clientes com atraso superior a 90 dias
- Clientes com queda de compras

### Compras

- Produtos comprados sem giro
- Estoque parado por fornecedor

Os alertas deverão possuir acesso direto ao Drill Down para facilitar a análise e a tomada de decisão.
