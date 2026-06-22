# Documentação do Sistema
## Dashboard Executivo Cetel — Business Intelligence Resulth

---

| | |
|---|---|
| **Cliente** | Cetel |
| **Sistema de origem dos dados** | ERP Resulth (Firebird 2.5, `RESULTH.FB`) |
| **Tipo de documento** | Documentação funcional e técnica do sistema |
| **Versão** | 1.0 |
| **Data de emissão** | 2026-06-18 |
| **Classificação** | Uso interno |
| **Status** | Sistema em produção — 5 módulos + painel executivo |

---

## Sumário

1. [Introdução](#1-introdução)
2. [Visão Geral da Arquitetura](#2-visão-geral-da-arquitetura)
3. [Módulos do Sistema](#3-módulos-do-sistema)
   - 3.1 [Tela Inicial — Dashboard Executivo](#31-tela-inicial--dashboard-executivo)
   - 3.2 [Módulo Financeiro](#32-módulo-financeiro)
   - 3.3 [Módulo Comercial](#33-módulo-comercial)
   - 3.4 [Módulo Estoque](#34-módulo-estoque)
   - 3.5 [Módulo Compras](#35-módulo-compras)
   - 3.6 [Módulo Alertas](#36-módulo-alertas)
4. [Dicionário de Dados](#4-dicionário-de-dados)
   - 4.1 [Tabelas do Firebird (ERP — somente leitura)](#41-tabelas-do-firebird-erp--somente-leitura)
   - 4.2 [Tabelas do DuckDB (armazenamento interno)](#42-tabelas-do-duckdb-armazenamento-interno)
5. [Regras de Negócio Consolidadas](#5-regras-de-negócio-consolidadas)
6. [Segurança e Controle de Acesso](#6-segurança-e-controle-de-acesso)
7. [Glossário](#7-glossário)
8. [Histórico de Revisões](#8-histórico-de-revisões)

---

## 1. Introdução

### 1.1 Objetivo do documento

Este documento descreve, de forma completa e independente de código, o que o sistema
de Business Intelligence da Cetel faz, como está organizado e quais dados utiliza.
Destina-se a:

- **Gestores e usuários de negócio** — entender o que cada tela oferece e como apoia
  a tomada de decisão.
- **Novos integrantes da equipe técnica** — entender a arquitetura e onde encontrar
  cada informação sem precisar ler o código-fonte linha a linha.
- **Auditoria e continuidade** — servir de referência caso o sistema precise ser
  mantido, expandido ou auditado por terceiros no futuro.

Para detalhes de implementação (assinatura de funções Python, queries SQL completas),
ver o complemento técnico em `docs/MANUAL_TECNICO.md`.

### 1.2 Visão geral do sistema

O sistema é um **painel de Business Intelligence (BI) somente leitura** construído
sobre o banco de dados do ERP Resulth, usado pela Cetel para gestão de distribuição
de materiais elétricos, hidráulicos e afins. Ele não substitui o ERP — apenas lê os
dados nele lançados e os transforma em indicadores, gráficos, alertas e relatórios
para apoiar decisões financeiras, comerciais, de estoque e de compras.

O sistema é composto por **6 telas**: um painel executivo consolidado (Tela Inicial)
e 5 módulos especializados (Financeiro, Comercial, Estoque, Compras, Alertas).

### 1.3 Público-alvo do sistema

| Perfil | O que usa |
|---|---|
| Diretoria / Sócios | Tela Inicial, Módulo Alertas |
| Financeiro | Módulo Financeiro (contas a pagar/receber, fluxo de caixa) |
| Comercial / Vendas | Módulo Comercial (faturamento, metas, clientes) |
| Compras / Suprimentos | Módulo Compras (fornecedores, rentabilidade) |
| Logística / Estoque | Módulo Estoque (giro, ruptura, curva ABC) |

---

## 2. Visão Geral da Arquitetura

```
┌──────────────────────┐   leitura (read-only)   ┌────────────────────────┐
│   ERP Resulth          │ ───────────────────────▶ │  Camada de dados        │
│   Firebird 2.5          │   driver fdb +            │  (Python — core/data) │
│   RESULTH.FB             │   fbclient.dll            │                        │
└──────────────────────┘                           └───────────┬────────────┘
                                                                  │ DataFrames
                                                                  ▼
                                                     ┌────────────────────────┐
                                                     │  Telas (Streamlit)      │
                                                     │  app.py + pages/*.py    │
                                                     └───────────┬────────────┘
                                                                  │ grava
                                                                  ▼
                                                     ┌────────────────────────┐
                                                     │  Armazenamento interno   │
                                                     │  DuckDB — data/store.db  │
                                                     │  (comentários, metas,    │
                                                     │   histórico diário)      │
                                                     └────────────────────────┘
```

**Princípio fundamental de segurança de dados:** o ERP (Firebird) **nunca** recebe
escrita do painel de BI — é tratado estritamente como fonte de leitura. Tudo que o
usuário registra dentro do painel (comentários, metas configuradas, preferências de
tela, thresholds de alerta) é gravado em um banco local separado (DuckDB), que também
guarda o histórico diário de indicadores para permitir gráficos de evolução ao longo
do tempo — algo que o ERP por si só não oferece de forma pronta.

### 2.1 Stack tecnológico

| Camada | Tecnologia |
|---|---|
| Banco de origem | Firebird 2.5 (SQL Dialect 1), acesso via driver `fdb` |
| Armazenamento interno | DuckDB (arquivo local `data/store.duckdb`) |
| Interface | Streamlit (aplicação web) |
| Visualização de gráficos | Plotly |
| Tabelas interativas | streamlit-aggrid |
| Exportação | openpyxl (Excel), fpdf2 (PDF) |
| Agendamento de tarefas | APScheduler (snapshot diário automático às 08h) |
| Linguagem | Python 3.14 |

### 2.2 Atualização dos dados

Todas as telas consultam o Firebird **em tempo real** a cada carregamento (com cache
de curta duração, de 5 a 30 minutos conforme o módulo, para não sobrecarregar o banco
do ERP com consultas repetidas). Não há replicação nem cópia da base — o que está na
tela reflete o estado do ERP no momento da consulta, defasado apenas pelo tempo de
cache.

Adicionalmente, uma rotina automática roda todos os dias às 08h e grava uma fotografia
dos principais indicadores no armazenamento interno (DuckDB), permitindo construir
gráficos de evolução histórica (ex.: "saldo bancário nos últimos 30 dias") que o ERP
não fornece nativamente.

---

## 3. Módulos do Sistema

### 3.1 Tela Inicial — Dashboard Executivo

**Arquivo:** `app.py` · **Acesso:** página raiz do sistema

**Objetivo de negócio:** dar, em uma única tela, a fotografia mais importante do
estado da empresa — sem precisar abrir nenhum módulo específico. Pensada para quem
tem pouco tempo (diretoria, sócios) e precisa de uma visão de "tudo bem ou alguma
coisa precisa de atenção agora".

**O que a tela mostra:**

| Seção | Conteúdo | Pode ser ocultada? |
|---|---|---|
| KPIs Executivos | 12 indicadores: Contas a Receber, Vencido AR, Caixa, Faturamento do mês, Estoque, AR a Vencer, Contas a Pagar, Vencido AP, Capital Operacional, SKUs em estoque, Clientes inativos | Sim |
| Alertas Ativos | Resumo dos alertas críticos e urgentes de todos os módulos, com link direto para resolver | Sim |
| Gráficos Rápidos | Faturamento dos últimos 30 dias; comparação visual Contas a Receber × Contas a Pagar | Sim |
| Histórico de KPIs | Evolução diária de saldo, AR/AP, capital operacional e inadimplência (aparece após alguns dias de uso, conforme o histórico vai sendo construído) | Sim |
| Módulos do Sistema | Atalhos de navegação para os 5 módulos | Sim |

Cada seção pode ser ativada/desativada pelo próprio usuário na barra lateral — a
preferência é lembrada entre sessões.

**Indicadores-chave exibidos:** total a receber, total a pagar, saldo em caixa,
capital operacional (caixa + a receber + estoque − a pagar), faturamento do mês
corrente comparado ao anterior, quantidade de produtos em estoque, quantidade de
clientes que não compram há mais de 60 dias.

**Fontes de dados:** módulos Financeiro, Comercial, Estoque e Alertas (a Tela Inicial
não tem fonte de dados própria — ela agrega o que os outros módulos já calculam).

---

### 3.2 Módulo Financeiro

**Arquivo:** `pages/01_Financeiro.py` · **Ícone:** 💰

**Objetivo de negócio:** gerenciar o ciclo financeiro completo da empresa — quanto
tem a receber, quanto tem a pagar, qual o saldo em caixa, qual o nível de
inadimplência dos clientes, e como o caixa vai se comportar nos próximos dias.

**Funcionalidades (abas):**

| Aba | Para que serve |
|---|---|
| **Contas a Receber** | Lista de tudo que está em aberto para receber de clientes, organizado por faixa de atraso (1-30, 31-60, 61-90, +90 dias). Permite clicar em um cliente e ver cada título, e dentro de cada título o histórico de pagamentos e os itens da nota/pedido de origem. |
| **Fluxo de Caixa** | Projeção de quanto vai entrar e sair de dinheiro nos próximos 7/15/30/60/90 dias, com gráfico de saldo projetado dia a dia e aviso visual se o saldo cair abaixo de um piso mínimo configurável. |
| **Contas a Pagar** | Mesma lógica do Contas a Receber, mas para fornecedores — o que está em aberto, organizado por horizonte de vencimento e por fornecedor. |
| **Comparativos** | Evolução mensal (últimos 13 meses) de quanto foi recebido e pago, e o acumulado do ano corrente. |
| **Posição de Caixa** | Visão consolidada: saldo bancário + a receber + estoque − a pagar = capital operacional. Também mostra o Prazo Médio de Recebimento (PMR) e o Prazo Médio de Pagamento (PMP). |
| **Histórico** | Gráficos de evolução diária construídos a partir das fotografias automáticas (ver seção 2.2) — saldo bancário, AR/AP/Capital, inadimplência por faixa ao longo do tempo. |
| **Calendário** | Vencimentos de um dia ou período específico, em formato de agenda. |
| **Configurações** | Ajuste do piso mínimo de caixa e dos limites que disparam alertas (ex.: a partir de quantas horas um título a pagar é considerado "urgente"). |

**Indicadores-chave:** total a receber e a pagar (em aberto e vencido), saldo
bancário, capital operacional, PMR e PMP.

> **Nota de leitura — PMR e PMP negativos:** se esses indicadores aparecerem
> negativos, **não é erro**. Significa que, em média, os pagamentos/recebimentos
> estão acontecendo **antes** do vencimento. No caso específico da Cetel, o PMP tem
> sido consistentemente negativo (pagamentos antecipados a fornecedores) — um ponto
> de atenção para gestão de capital de giro, não um defeito do sistema.

**Principais tabelas do ERP consultadas:** `DOCUREC` (títulos a receber), `DOCUPAG`
(títulos a pagar), `MOVIREC`/`MOVIPAG` (histórico de pagamentos/recebimentos),
`MOVIBAN` (movimento bancário), `CLIENTE`, `FORNECE`, `COMPPROD`+`PRODUTO` (valor do
estoque), `NFSAIDI`/`PEDIDOI` (itens dos documentos no detalhamento).

---

### 3.3 Módulo Comercial

**Arquivo:** `pages/02_Comercial.py` · **Ícone:** 🛒 (carrinho)

**Objetivo de negócio:** acompanhar o desempenho de vendas — quanto a empresa está
faturando, se está batendo a meta, quem são os melhores clientes e vendedores, e
quais clientes estão deixando de comprar.

**Funcionalidades (abas):**

| Aba | Para que serve |
|---|---|
| **Meta & Indicadores** | Meta de faturamento do mês (vinda do ERP ou configurada manualmente), quanto já foi faturado, projeção de fechamento do mês baseada no ritmo atual, e funil de pedidos (criados → faturados → cancelados). |
| **Faturamento** | Evolução do faturamento por dia/semana/quinzena/mês, ticket médio geral e por vendedor, ranking de vendedores, e descontos concedidos no período. |
| **Clientes** | Top clientes por faturamento e por lucro gerado, clientes que pararam de comprar, clientes em queda de consumo, e comparação entre clientes novos e recorrentes. |
| **Concentração** | Curva ABC de clientes e de produtos — quais 20% dos clientes/produtos respondem por 80% do faturamento (princípio de Pareto). |
| **Sazonalidade** | Padrão de vendas ao longo dos meses, para identificar picos e baixas sazonais. |
| **Configurações** | Definição manual da meta de faturamento mensal, quando o ERP não tiver essa informação cadastrada. |

**Indicadores-chave:** faturamento do período, ticket médio, número de clientes
atendidos, taxa de conversão de pedidos (criados → efetivamente faturados).

**Principais tabelas do ERP consultadas:** `PEDIDOC` (cabeçalho de pedidos/vendas —
o filtro `FATURADO='S'` define o que é uma venda concretizada), `PEDIDOI` (itens
vendidos), `CLIENTE`, `PRODUTO`, `VENDEND` (cadastro de vendedores),
`METAFATURAMENTOMENSAL` (meta de faturamento do ERP, quando cadastrada).

---

### 3.4 Módulo Estoque

**Arquivo:** `pages/03_Estoque.py` · **Ícone:** 📦

**Objetivo de negócio:** controlar o capital imobilizado em estoque — o que está
girando bem, o que está parado consumindo capital sem necessidade, o que está em
ruptura (sem estoque disponível para vender) e onde estão os produtos mais valiosos.

**Funcionalidades (abas):**

| Aba | Para que serve |
|---|---|
| **Top Produtos** | Ranking dos produtos mais vendidos por quantidade, por faturamento gerado e por lucro bruto. |
| **Estoque Atual** | Lista completa de produtos com saldo, custo, valor de venda, estoque mínimo/máximo — com possibilidade de clicar em um produto e ver todo o histórico de movimentações (entradas, vendas, ajustes). |
| **Estoque Parado** | Produtos com saldo positivo que não vendem há um determinado número de dias (configurável: 30/60/90/180/365). Distingue produtos que "pararam de vender recentemente" de produtos que "nunca tiveram nenhuma venda registrada". |
| **Controle** | Dois alertas operacionais: produtos em ruptura (sem nenhum saldo disponível) e produtos abaixo do estoque mínimo cadastrado. |
| **Curva ABC** | Classificação dos produtos em A (alto valor investido), B (médio) e C (baixo) — para priorizar onde focar a gestão de estoque. |
| **Giro por Grupo** | Quanto cada categoria de produto (cabos, iluminação, hidráulica etc.) vendeu em relação ao valor que tem investido em estoque — quanto maior o giro, mais eficiente o capital aplicado naquele grupo. |
| **Configurações** | Ajuste dos limites usados nos alertas de estoque parado. |

**Indicadores-chave:** total de SKUs cadastrados, SKUs com saldo positivo, SKUs em
ruptura, valor do estoque a custo e a preço de venda.

**Principais tabelas do ERP consultadas:** `COMPPROD` (saldo de estoque — apenas o
código de empresa "00" tem saldo real, o código "01" está sempre zerado por desenho
do próprio ERP), `PRODUTO` (descrição, preço de venda, mínimo/máximo cadastrados),
`GRUPROD` (categoria do produto), `MVGERAL` (todas as movimentações de estoque —
vendas, entradas, ajustes).

---

### 3.5 Módulo Compras

**Arquivo:** `pages/04_Compras.py` · **Ícone:** 🛒

**Objetivo de negócio:** avaliar a relação com fornecedores — quanto está sendo
comprado, de quem, se a empresa está excessivamente dependente de poucos
fornecedores, e se o que está sendo comprado está efetivamente sendo vendido
(rentabilidade da compra).

**Funcionalidades (abas):**

| Aba | Para que serve |
|---|---|
| **Evolução de Compras** | Histórico mensal (até 13 meses) de quanto foi comprado e em quantas notas fiscais de entrada. |
| **Fornecedores** | Ranking dos 15 maiores fornecedores por valor comprado, com possibilidade de detalhar até as notas fiscais e os itens de cada nota. |
| **Dependência** | Quanto a empresa está concentrada nos principais fornecedores (ex.: os 3 maiores respondem por X% do total comprado) — com alerta automático quando a concentração é alta demais. |
| **Rentabilidade** | Cruza o que foi comprado de cada fornecedor com o que foi efetivamente vendido daqueles produtos — mostrando quais fornecedores geram mais retorno e quais têm produtos comprados que não estão vendendo. |
| **Alertas** | Produtos comprados que não tiveram nenhuma venda no período, e estoque parado agrupado por fornecedor responsável. |
| **Configurações** | Ajuste dos limites de concentração e de valor parado usados nos alertas. |

**Indicadores-chave:** total comprado no período, número de notas fiscais recebidas,
número de fornecedores ativos, lucro bruto gerado pelos produtos comprados.

**Principais tabelas do ERP consultadas:** `NFENTRC` (cabeçalho das notas fiscais de
entrada), `NFENTRI` (itens de cada nota), `FORNECE` (cadastro de fornecedores),
`RELPRFO` (qual fornecedor é o principal de cada produto), `MVGERAL` (para calcular
a venda gerada por produtos comprados), `COMPPROD`+`PRODUTO`+`GRUPROD` (estoque
parado por fornecedor).

---

### 3.6 Módulo Alertas

**Arquivo:** `pages/05_Alertas.py` · **Ícone:** 🚨

**Objetivo de negócio:** ser o ponto único de "gestão por exceção" — em vez de
precisar abrir os 4 módulos todos os dias para ver se algo está errado, esta tela
agrega automaticamente tudo que precisa de atenção, classificado por nível de
urgência.

**Como funciona:** o sistema verifica continuamente um conjunto de regras de negócio
pré-configuradas (ex.: "caixa abaixo de X", "cliente sem comprar há mais de Y dias",
"fornecedor concentrando mais de Z% das compras") e gera uma lista de alertas. Cada
alerta tem:

- **Nível**: 🔴 Crítico (ação imediata), 🟠 Urgente (ação em breve), 🟡 Atenção (monitorar)
- **Módulo de origem**: Financeiro, Comercial, Estoque ou Compras
- **Link direto** para a tela onde o problema pode ser investigado/resolvido

**Funcionalidades (abas):** Todos os alertas (com filtros e gráficos de distribuição),
mais uma aba dedicada por módulo (Financeiro, Comercial, Estoque, Compras), e uma
aba de Configurações onde ficam visíveis todos os limites (thresholds) usados pelas
regras.

**Principais limites configuráveis:**

| Regra | Limite atual |
|---|---|
| Piso mínimo de caixa | R$ 50.000 |
| Capital operacional mínimo | R$ 100.000 |
| Título a pagar "urgente" | vence em até 48 horas |
| Atraso de cliente considerado crítico | mais de 90 dias |
| Cliente considerado "parado" | sem comprar há mais de 60 dias |
| Produto/estoque considerado "parado" | sem vender há mais de 90 dias |
| Concentração de fornecedores considerada alta | top 3 acima de 60% das compras |

**Fontes de dados:** este módulo não acessa o ERP diretamente — ele reaproveita os
cálculos já feitos pelos módulos Financeiro, Comercial, Estoque e Compras,
combinando-os em uma visão única.

---

## 4. Dicionário de Dados

### 4.1 Tabelas do Firebird (ERP — somente leitura)

Todas as tabelas abaixo pertencem ao ERP Resulth e são **exclusivamente lidas** pelo
sistema de BI — nenhuma escrita é realizada nessas tabelas em nenhuma circunstância.

| Tabela | Descrição funcional | Usada em |
|---|---|---|
| **DOCUREC** | Títulos a receber de clientes (duplicatas/faturas). Campo `SITUACAO='1'` identifica títulos em aberto. | Financeiro |
| **DOCUPAG** | Títulos a pagar a fornecedores. Mesma lógica de `SITUACAO='1'` = em aberto. | Financeiro |
| **MOVIREC** | Histórico de movimentos de recebimento (pagamentos recebidos de clientes, liquidações, prorrogações). Usado para calcular o Prazo Médio de Recebimento. | Financeiro |
| **MOVIPAG** | Histórico de movimentos de pagamento a fornecedores. Usado para calcular o Prazo Médio de Pagamento. | Financeiro |
| **MOVIBAN** | Movimento das contas bancárias da empresa — usado para apurar o saldo bancário atual. | Financeiro |
| **CLIENTE** | Cadastro de clientes (código, nome, dados cadastrais). | Financeiro, Comercial, filtros globais |
| **FORNECE** | Cadastro de fornecedores (código, nome/razão social, nome fantasia). | Financeiro, Compras, filtros globais |
| **PEDIDOC** | Cabeçalho de pedidos de venda. O campo `FATURADO='S'` indica que o pedido se tornou uma venda efetiva (faturada); `DATAFATURA` é a data da venda. | Comercial |
| **PEDIDOI** | Itens de cada pedido de venda (produto, quantidade, valor, desconto). | Comercial |
| **VENDEND** | Cadastro de vendedores. | Comercial, filtros globais |
| **METAFATURAMENTOMENSAL** | Meta de faturamento mensal cadastrada no ERP (atualmente sem uso ativo pelo cliente — quando vazia, o sistema usa a meta configurada manualmente no painel). | Comercial |
| **COMPPROD** | Saldo de estoque por produto e por empresa. Apenas o código de empresa `'00'` mantém saldo real; `'01'` está sempre zerado por desenho do ERP. Contém também custo médio e estoque mínimo/máximo. | Estoque, Financeiro (estoque a custo), Compras |
| **PRODUTO** | Cadastro de produtos — descrição, grupo, preço de venda (`PRECO`), fabricante. **Importante:** o preço de venda correto está aqui, não em `COMPPROD.PRECONF` (que fica zerado). | Estoque, Comercial, Compras |
| **GRUPROD** | Categorias/grupos de produto (ex.: Cabos e Conexões, Iluminação, Hidráulica). | Estoque, Compras, filtros globais |
| **CADFABR** | Cadastro de fabricantes/marcas dos produtos. | Filtros globais |
| **MVGERAL** | Tabela central de movimentações de estoque — toda venda, entrada de nota fiscal, ajuste e devolução passa por aqui. O tipo de movimento (`TIPOMOV`) identifica a natureza: `'55'`=venda PDV, `'01'`=entrada de nota fiscal, `'09'`=saída em consignação/orçamento, `'61'`=devolução de entrada, `'05'`=devolução de venda. | Estoque, Comercial, Compras |
| **NFENTRC** | Cabeçalho das notas fiscais de entrada (compras). A data de entrada é `DT_ENTRADA` e o valor total é `TOTALNF`. | Compras |
| **NFENTRI** | Itens de cada nota fiscal de entrada. | Compras |
| **RELPRFO** | Relação entre produto e fornecedor(es) — identifica qual é o fornecedor principal de cada produto. | Compras |
| **NFSAIDI** | Itens das notas fiscais de saída (vendas faturadas com nota), usado no detalhamento de títulos do Financeiro. | Financeiro |
| **SALDOST** | Histórico de saldo financeiro acumulado — **não** representa o saldo bancário atual (esse vem de `MOVIBAN`); é um acumulado histórico de uso restrito. | (referência, não usado ativamente nas telas) |
| **EMPRESA** | Registro único de licenciamento/configuração do sistema ERP. **Não é** um cadastro de empresas/filiais — não tem lista de códigos com nomes. A lista de empresas exibida nos filtros do painel é fixa (códigos `'00'` e `'01'`, conforme efetivamente usados em `COMPPROD`), não consultada nesta tabela. | — |

### 4.2 Tabelas do DuckDB (armazenamento interno)

Estas tabelas pertencem exclusivamente ao painel de BI — não existem no ERP e são o
**único lugar onde o sistema grava dados**. Ficam no arquivo local `data/store.duckdb`.

| Tabela | Descrição funcional |
|---|---|
| **comentarios** | Comentários gerenciais que o usuário registra em qualquer indicador/aba de qualquer módulo — um histórico de observações de negócio ao longo do tempo. |
| **config_alertas** | Limites (thresholds) configuráveis de alertas — piso de caixa, dias de atraso crítico, etc. — ajustáveis pelo usuário na aba "Configurações" de cada módulo. |
| **preferencias_home** | Preferências do usuário sobre quais seções exibir na Tela Inicial (checkboxes da barra lateral). |
| **snap_kpis_diario** | Fotografia diária dos KPIs executivos (AR, AP, caixa, capital operacional, estoque, faturamento do mês) — gravada automaticamente todos os dias às 08h, base dos gráficos de "Histórico". |
| **snap_inadimplencia** | Fotografia diária do valor de inadimplência por faixa de atraso. |
| **snap_saldo_bancario** | Fotografia diária do saldo bancário por conta. |

---

## 5. Regras de Negócio Consolidadas

Estas são as regras de interpretação de dados mais importantes, válidas em todo o
sistema — conhecê-las evita interpretar um número incorretamente:

1. **Empresa `'00'` é a operação real; `'01'` é um código vestigial.** Praticamente
   todo o movimento financeiro, comercial e de compras acontece sob o código `'00'`.
   O código `'01'` aparece apenas em `COMPPROD`, sempre com saldo zero.
2. **Uma venda só "existe" para fins de faturamento quando `PEDIDOC.FATURADO='S'`.**
   Pedidos sem essa marcação são orçamentos/pendências, não vendas concretizadas.
3. **O preço de venda do produto vem de `PRODUTO.PRECO`**, nunca de
   `COMPPROD.PRECONF` (esse último é um campo de preço de fornecedor, normalmente
   vazio nesta base).
4. **PMR/PMP negativos significam pagamento/recebimento adiantado**, não um erro de
   cálculo — é um dado de negócio legítimo e relevante.
5. **"Estoque parado" e "produto nunca vendido" são conceitos diferentes.** O
   primeiro inclui produtos que já venderam alguma vez, mas não recentemente; o
   segundo é exclusivamente produtos sem nenhum registro histórico de venda.
6. **Os dados são de um sistema em produção real**, atualizados continuamente pela
   operação do dia a dia da empresa — dois relatórios tirados em momentos diferentes
   do dia podem (e devem) mostrar números diferentes. Isso é esperado e correto.

---

## 6. Segurança e Controle de Acesso

| Aspecto | Como é tratado |
|---|---|
| Acesso ao ERP | Conexão dedicada, somente leitura, usuário `SYSDBA` (credenciais armazenadas fora do código-fonte versionado) |
| Escrita de dados | Nunca ocorre no Firebird/ERP. Toda gravação do painel (comentários, configurações, histórico) vai para o DuckDB local |
| Biblioteca de conexão | `fbclient.dll`, necessária para o driver Python `fdb` acessar o Firebird |
| Exposição de rede | Aplicação Streamlit acessível na rede local da empresa (porta configurável, padrão 8501) |

---

## 7. Glossário

| Termo | Significado |
|---|---|
| **AR** | Accounts Receivable — Contas a Receber |
| **AP** | Accounts Payable — Contas a Pagar |
| **PMR** | Prazo Médio de Recebimento — média de dias entre vencimento e recebimento efetivo |
| **PMP** | Prazo Médio de Pagamento — média de dias entre vencimento e pagamento efetivo |
| **Capital Operacional** | Saldo em caixa + Contas a Receber + Estoque (a custo) − Contas a Pagar |
| **Curva ABC** | Classificação de itens pelo princípio de Pareto: A = itens que concentram a maior parte do valor, C = itens de baixo impacto individual |
| **Giro de estoque** | Quanto um produto/grupo vendeu em relação ao valor que tem investido em estoque — indicador de eficiência do capital aplicado |
| **SKU** | Stock Keeping Unit — unidade individual de produto no estoque |
| **Ticket médio** | Valor médio de cada pedido/venda |
| **Ruptura** | Situação em que um produto não tem nenhum saldo disponível para venda |
| **Concentração** | Percentual do total (vendas, compras) respondido pelos maiores clientes/fornecedores |

---

## 8. Histórico de Revisões

| Versão | Data | Descrição |
|---|---|---|
| 1.0 | 2026-06-18 | Emissão inicial — consolida as fases 0 a 8 do projeto (fundação, 5 módulos, alertas, tela inicial, polimento e auditoria completa de dados) |

> Para o detalhamento técnico (funções Python, queries SQL, achados específicos de
> auditoria e sugestões de evolução por tela), consultar `docs/MANUAL_TECNICO.md`.
> Para o histórico de implementação sprint a sprint, consultar `docs/PROGRESSO.md`.
