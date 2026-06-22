# Roadmap — Dashboards Personalizados Resulth

> Documento de planejamento do projeto. Serve tanto como guia de desenvolvimento
> quanto como contexto para o Claude integrado no VSCode.
> **Status da base de tabelas:** pendente (planilha ainda não analisada). As seções
> marcadas com `⏳ depende das tabelas` serão preenchidas após o mapeamento do banco.

---

## 1. Visão geral

Camada de BI/dashboards sobre o ERP **Resulth** (banco **Firebird local**), construída
em **Python**. O cliente forneceu um documento de requisitos (PDF) com 6 módulos:
Financeiro, Comercial, Produtos, Estoque, Compras e Alertas, além de requisitos
transversais (exportação, drill-down, filtros globais, comparativos, comentários
gerenciais e tela inicial personalizável).

**Objetivo de negócio:** dar ao gestor uma visão consolidada e acionável (com
detalhamento até o documento de origem) sem depender de relatórios manuais.

**Objetivo pessoal/profissional:** entregar algo polido, estável e com identidade,
vinculado ao seu nome. Por isso o roadmap prioriza **entregar um módulo redondo de
cada vez** em vez de tudo pela metade.

---

## 2. Premissas e contexto técnico

- Banco operacional: Firebird (provavelmente 2.5/3.x — confirmar versão).
- Acesso somente leitura à base operacional (nunca escrever no banco do ERP).
- Deploy local, na mesma máquina/rede do cliente (não é SaaS).
- Um pequeno número de usuários (uso interno do gestor/equipe).
- Você desenvolve sozinho, com apoio do Claude no VSCode.

---

## 3. Decisão de arquitetura (a parte mais importante)

O próprio PDF pede "evitar consultas excessivamente pesadas sobre a base operacional".
Isso, somado a vários indicadores que precisam de **histórico** (evolução de saldo,
evolução de inadimplência, sazonalidade de 24 meses), leva à decisão central:

### ➜ Não consultar o Firebird operacional direto para análise. Usar um *data store analítico* intermediário.

```
┌──────────────┐   sync periódico   ┌─────────────────┐   queries rápidas  ┌────────────┐
│  Firebird    │  (incremental +    │  Store analítico │   (read-only)      │ Dashboards │
│  (ERP, R/O)  │ ─ snapshots) ────► │  (DuckDB)        │ ─────────────────► │ (Streamlit)│
└──────────────┘                    └─────────────────┘                    └────────────┘
```

**Por que um store separado:**
1. **Isola a carga** — agregações pesadas (ABC, giro, sazonalidade) não derrubam o ERP.
2. **Permite histórico** — o banco operacional normalmente guarda só o estado *atual*
   (ex.: saldo bancário de hoje, títulos em aberto hoje). "Evolução dos últimos 30 dias"
   e "evolução da inadimplência" exigem **snapshots diários** que o job de sync grava
   daqui pra frente. Sem isso, esses gráficos nascem vazios.
3. **Velocidade** — DuckDB é colunar e voa em agregação.

**Recomendação de store:** **DuckDB**.
- Embarcado (um arquivo `.duckdb`, sem servidor pra administrar — combina com deploy local).
- Colunar, extremamente rápido para os `GROUP BY`/janelas dos dashboards.
- Integração nativa com Python/pandas e suporte a Parquet.
- Alternativas: SQLite (mais simples, porém fraco em analítico) ou PostgreSQL
  (melhor se houver muitos usuários simultâneos, mas adiciona ops de servidor).

**Camada de sync:**
- Extração incremental por chave/data de alteração quando a tabela permitir;
  full-refresh nas tabelas pequenas (cadastros).
- **Snapshots**: tabelas próprias no DuckDB (`snap_saldo_bancario`, `snap_inadimplencia`, …)
  alimentadas 1x/dia pelo job, para reconstruir as séries temporais.
- Agendamento via APScheduler (dentro do app) ou cron/Task Scheduler do Windows.
- Registrar `data/hora da última atualização` (a tela inicial exige exibir isso).

> ⚠️ Se o cliente exigir dado **em tempo real** (não dá pra ter lag de minutos),
> reabrir essa decisão. Para gestão, lag de 5–15 min costuma ser aceitável.

---

## 4. Stack recomendada

| Camada            | Escolha                          | Observação |
|-------------------|----------------------------------|------------|
| Linguagem         | Python 3.11+                     | Boa escolha (ver §10) |
| Driver Firebird   | `firebird-driver`                | Moderno (FB 3+); `fdb` se for FB 2.5 |
| Store analítico   | `duckdb`                         | 1 arquivo, colunar |
| Manipulação dados | `pandas`                         | — |
| UI / dashboards   | **Streamlit**                    | Mais rápido pra entregar BI em Python puro |
| Gráficos          | `plotly`                         | Interativo, integra com Streamlit |
| Tabelas/drill     | `st.dataframe` (seleção) ou `streamlit-aggrid` | AgGrid dá filtro/expandir melhores |
| Export Excel      | `pandas.to_excel` + `openpyxl`   | — |
| Export PDF        | `reportlab` ou HTML→PDF (`weasyprint`) | — |
| Impressão         | CSS de impressão + print do navegador | — |
| Agendamento sync  | `APScheduler`                    | ou cron/Task Scheduler |

**Por que Streamlit e não Dash/web app custom:** para um dev solo querendo entregar
algo polido rápido, Streamlit elimina 80% do trabalho de frontend. O custo é menos
controle fino de layout — relevante só na "tela inicial arrastável" (ver §8, risco R1).

---

## 5. Convenções para o código (contexto p/ Claude no VSCode)

Estrutura de pastas sugerida:

```
resulth-dashboards/
├── app.py                  # entrypoint Streamlit (router de páginas)
├── pages/                  # uma página por dashboard
│   ├── 01_financeiro.py
│   ├── 02_comercial.py
│   └── ...
├── core/
│   ├── db_firebird.py      # conexão R/O com o ERP
│   ├── db_duck.py          # conexão com o store analítico
│   ├── sync/               # jobs de extração + snapshots
│   ├── filters.py          # filtros globais reaproveitáveis
│   ├── export.py           # excel / pdf / print
│   └── drilldown.py        # helpers de detalhamento
├── queries/                # SQL versionado (1 arquivo por consulta)
├── components/             # widgets Streamlit reutilizáveis (cards, KPIs)
├── config/                 # conexões, parâmetros, .env
├── data/                   # store.duckdb (gitignore)
└── ROADMAP.md / DB_REFERENCE.md
```

Regras:
- **Nunca** escrever no Firebird. Conexão sempre read-only.
- SQL fica em `queries/` (arquivos `.sql`), não espalhado no código — facilita revisão.
- Toda query analítica roda no DuckDB; o Firebird só é tocado pelo sync.
- KPIs e cards como componentes reutilizáveis (evita copiar/colar entre módulos).
- Filtros globais centralizados em `core/filters.py` e aplicados via session_state.

---

## 6. Fases do projeto

| Fase | Entrega | Conteúdo |
|------|---------|----------|
| **0 — Fundação** | Esqueleto técnico | Conexão Firebird R/O, DuckDB, 1ª rotina de sync, layout base do Streamlit, filtros globais, exibição de "última atualização". |
| **1 — Financeiro** | 1º módulo redondo | Todos os indicadores financeiros + drill-down + export. *Módulo escolhido para começar.* |
| **2 — Comercial** | Faturamento/metas | Meta, faturamento, ticket médio, top clientes, clientes sem comprar/queda, concentração, sazonalidade. |
| **3 — Produtos + Estoque** | Operacional | Top produtos, sem venda, estoque atual/parado, curva ABC, giro. (Compartilham muitas tabelas — fazer juntos.) |
| **4 — Compras** | Fornecedores | Compras, relevância, dependência, rentabilidade, alertas. |
| **5 — Alertas** | Transversal | Consolida sinais dos módulos anteriores + drill-down direto. Fazer por último (depende dos outros). |
| **6 — Tela inicial** | Personalização | Favoritos, organizar dashboards, salvar preferências. (Ver risco R1 sobre arrastar/redimensionar.) |
| **7 — Polimento** | Acabamento | Export/PDF/impressão padronizados, comentários gerenciais, comparativos históricos onde faltarem, performance. |

> Ordem proposital: a **fundação** (Fase 0) precisa estar sólida antes do Financeiro,
> porque export, filtros e drill-down são transversais e serão reaproveitados.
> Os **Alertas** e a **tela inicial** ficam para o fim porque dependem do resto.

---

## 7. Requisitos transversais — como implementar

- **Filtros globais** (período, empresa, vendedor, cliente, fornecedor, grupo, marca):
  componente único; estado em `st.session_state`; cada query recebe os filtros como parâmetros.
- **Drill-down**: padrão "do agregado ao documento". Em Streamlit, clique/seleção na
  tabela (AgGrid) abre o nível seguinte. Cada nível é uma query parametrizada pelo ID
  do nível anterior. Ex.: Faturamento → Cliente → Pedido → Itens.
- **Comparativos** (mês x mês anterior, mês x mesmo mês ano anterior, acumulado ano):
  helper de período que calcula as janelas; exige histórico no store.
- **Comentários gerenciais**: tabela própria no DuckDB (`comentarios`), vinculada a
  (indicador, período). CRUD simples.
- **Exportação/impressão**: módulo `export.py` genérico; cada dashboard expõe seu
  dataframe corrente → Excel/PDF. Impressão inclui data de emissão + período analisado.

---

## 8. Itens potencialmente "irreais" / a renegociar com o cliente

| ID | Item | Avaliação | Sugestão |
|----|------|-----------|----------|
| **R1** | Tela inicial **arrastável e redimensionável** com persistência | Caro no Streamlit. Existe `streamlit-elements` (grid arrastável), mas é componente da comunidade e adiciona complexidade desproporcional ao valor. | MVP: favoritos + mostrar/ocultar + reordenar simples. Arrastar/redimensionar só numa v2, se o cliente fizer questão. |
| **R2** | Séries históricas (evolução de saldo, de inadimplência) | O ERP provavelmente **não guarda** esses snapshots. | Começar a gravar snapshots diários **a partir do go-live**. Avisar o cliente que o histórico "enche" com o tempo (ou tentar reconstruir do operacional, quando possível). |
| **R3** | Tempo real | Conflita com a arquitetura de sync. | Acordar uma janela de atualização (ex.: a cada 10 min). Exibir "última atualização". |
| **R4** | Saldo bancário / conciliação | ⏳ depende das tabelas — só existe se o cliente **usa** o módulo financeiro-bancário do ERP. | Confirmar na planilha + com o cliente se há lançamentos bancários reais. |
| **R5** | Lucro bruto / CMV por item | ⏳ depende de haver **custo** confiável por produto na base. | Validar se o custo está preenchido e qual custo usar (médio, última compra…). |

> Princípio: não prometer indicador que a base não sustenta. Melhor entregar menos e
> certo. Cada "⏳" acima vira um ✅ ou ❌ depois do mapeamento das tabelas.

---

## 9. Registro de dependências de dados (preenchido após a planilha)

⏳ *depende das tabelas* — esta seção lista, por indicador, de quais tabelas/campos ele
depende, e marca **viável / parcial / inviável**. Será gerada junto com o
`DB_REFERENCE.md` assim que a planilha for analisada. (Ver prévia da análise do módulo
Financeiro na conversa.)

---

## 10. Sobre a linguagem (Python) e considerações finais

- **Python é uma boa escolha aqui.** Para um dev solo entregando BI sobre banco
  relacional, é provavelmente a melhor relação esforço/resultado: drivers Firebird
  prontos, pandas pra modelagem, Streamlit pra UI, DuckDB pra analítico. Tudo na mesma
  linguagem.
- **Limite honesto:** Python+Streamlit brilha em ferramenta interna pra poucos usuários.
  Se um dia virar produto multiusuário, com autenticação robusta, alta concorrência e
  mobile, a stack pesa — mas **não é o caso deste cliente**.
- **Maior risco do projeto não é técnico, é de escopo.** O PDF pede muito. A estratégia
  vencedora é fatiar: entregar o **Financeiro impecável** primeiro, mostrar pro cliente,
  e seguir módulo a módulo. Isso protege seu nome melhor do que tentar tudo de uma vez.
- **Performance:** com o store analítico, a maioria das queries será trivial. Os pontos
  a vigiar são sazonalidade (24 meses) e curva ABC — resolvidos com pré-agregação no sync.
