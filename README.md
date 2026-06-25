# Cetel — Dashboard Executivo Resulth

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.58-FF4B4B?logo=streamlit&logoColor=white)
![Firebird](https://img.shields.io/badge/Firebird-2.5-orange)
![DuckDB](https://img.shields.io/badge/DuckDB-1.5-FFF000?logo=duckdb&logoColor=black)
![Status](https://img.shields.io/badge/status-em%20produção-success)

Dashboard executivo em Streamlit para a Cetel, consumindo dados em tempo real do
ERP Resulth (Firebird) e mantendo histórico/configurações próprios em DuckDB.
Cobre 5 módulos: **Financeiro**, **Comercial**, **Estoque**, **Compras** e uma
**Central de Alertas** que agrega sinais dos quatro.

## Sobre o projeto

Esse dashboard nasceu da necessidade de dar visibilidade executiva a um ERP
(Resulth) que só expõe os dados via relatórios internos do próprio sistema.
A ideia é simples: ler o Firebird do ERP **sem nunca escrever nele** (é a base
de produção real do cliente), calcular KPIs/indicadores em Python, e manter um
histórico próprio (DuckDB) para gráficos de evolução que o ERP não oferece.

### Funcionalidades por módulo

- 💰 **Financeiro** — Contas a Receber/Pagar, aging por faixa de atraso, fluxo
  de caixa projetado (7/15/30/60/90 dias), PMR/PMP, mapa de calor de
  vencimentos, concentração de inadimplência, drill-down até o título e os
  itens da NF/pedido.
- 📈 **Comercial** — Meta x realizado, funil de pedidos, ranking de vendedores,
  curva ABC de clientes/produtos, sazonalidade, clientes novos x recorrentes,
  clientes em queda de compra, drill-down Cliente → Pedido → Itens.
- 📦 **Estoque** — Curva ABC por valor investido, giro por grupo, estoque
  parado, produtos nunca vendidos, controle de ruptura/abaixo do mínimo,
  histórico de movimentações por produto.
- 🛒 **Compras** — Rentabilidade por fornecedor, dependência de fornecedor
  (concentração), produtos comprados sem giro, estoque parado por fornecedor.
- 🔔 **Central de Alertas** — agrega regras de negócio dos 4 módulos (caixa
  baixo, AP vencido, cliente inadimplente, estoque parado, fornecedor
  concentrado, snapshot atrasado...) em um painel único, com thresholds
  configuráveis.
- Exportação de qualquer seção em **Excel** e **PDF**, comentários gerenciais
  persistentes por indicador, e impressão formatada de cada página.

### Tecnologias utilizadas

| Camada | Tecnologia |
|---|---|
| Front-end / app | [Streamlit](https://streamlit.io/) + [Plotly](https://plotly.com/python/) (gráficos) + [streamlit-aggrid](https://github.com/PablocFonseca/streamlit-aggrid) (tabelas interativas) |
| Linguagem | Python 3.11+ |
| Origem dos dados | Firebird 2.5 (ERP, acesso somente leitura via [`fdb`](https://github.com/FirebirdSQL/python3-fdb)) |
| Armazenamento próprio | [DuckDB](https://duckdb.org/) (histórico, comentários, configurações) |
| Exportação | [fpdf2](https://github.com/py-pdf/fpdf2) (PDF) + [openpyxl](https://openpyxl.readthedocs.io/) (Excel) |
| Agendamento | [APScheduler](https://apscheduler.readthedocs.io/) (snapshot diário com retry) |
| Config | [python-dotenv](https://github.com/theskumar/python-dotenv) |

---

## Requisitos

- Python 3.11+ (testado em 3.14)
- Acesso de rede ao servidor Firebird 2.5 do ERP (somente leitura)
- `fbclient.dll` (cliente Firebird) — **já incluído na raiz do projeto**, não é instalado via pip
- Windows (o projeto foi desenvolvido e testado neste ambiente; os `.bat` de atalho são específicos do Windows, mas o app em si é portável)

## Instalação

```bash
pip install -r requirements.txt
```

Principais dependências: `streamlit`, `pandas`, `numpy`, `plotly`, `streamlit-aggrid`,
`fdb` (driver Firebird), `duckdb`, `fpdf2`, `openpyxl`, `apscheduler`, `python-dotenv`.

## Configuração — variáveis de ambiente

Copie `.env.example` para `.env` na raiz do projeto e preencha com as credenciais
reais do Firebird:

```bash
cp .env.example .env
```

```env
FB_HOST=localhost
FB_DATABASE=C:\Caminho\Para\RESULTH.FB
FB_USER=SYSDBA
FB_PASSWORD=sua-senha-aqui
FB_CHARSET=WIN1252
```

| Variável | Descrição |
|---|---|
| `FB_HOST` | Host do servidor Firebird (`localhost` se o banco estiver na mesma máquina) |
| `FB_DATABASE` | Caminho absoluto do arquivo `.FB` do ERP |
| `FB_USER` | Usuário Firebird (tipicamente `SYSDBA`) |
| `FB_PASSWORD` | Senha do usuário Firebird |
| `FB_CHARSET` | Charset da conexão (`WIN1252` no Resulth) |

**`.env` nunca deve ser commitado** — já está no `.gitignore`. Os valores em
`config/settings.py` sem `.env` são apenas fallback de desenvolvimento, não
credenciais reais.

> ⚠️ **A conexão com o Firebird é somente leitura.** Nenhuma função do projeto
> escreve no banco do ERP — é a base de produção do cliente. Tudo que o app
> precisa gravar (comentários, preferências, configurações de alerta, snapshots
> diários) vai para o DuckDB local (`data/store.duckdb`, criado automaticamente).

## Como executar

```bash
streamlit run app.py
```

ou, no Windows, dando duplo-clique em `iniciar.bat` (abre na porta 8501).

O agendador de snapshots diários (`core/sync/agendador.py`) inicia automaticamente
junto com o app via `@st.cache_resource` — não precisa de processo separado. Para
forçar a coleta do snapshot do dia manualmente (ex.: via Agendador de Tarefas do
Windows), use `snapshot_diario.bat` ou:

```bash
python -m core.sync.snapshot
```

## Estrutura do projeto

```
Projeto-Cetel/
├── app.py                      # Home: KPIs consolidados, alertas, atalhos para os módulos
├── pages/                      # Uma página Streamlit por módulo
│   ├── 01_Financeiro.py
│   ├── 02_Comercial.py
│   ├── 03_Estoque.py
│   ├── 04_Compras.py
│   └── 05_Alertas.py
│
├── core/
│   ├── data/                   # Acesso a dado puro — só SQL, sem regra de negócio
│   │   ├── firebird.py         # Conexão fdb + fb_query() (read-only)
│   │   ├── duckdb_store.py     # Schema e CRUD do DuckDB (único store gravável)
│   │   └── repositories/       # fetch_*() — uma query por necessidade, por módulo
│   ├── domain/                 # Regra de negócio — KPIs, classificações, alertas
│   │   ├── financeiro.py, comercial.py, estoque.py, compras.py
│   │   ├── classificacao.py    # Curva ABC compartilhada (comercial + estoque)
│   │   ├── alertas.py          # Motor único da Central de Alertas
│   │   └── filtros.py          # Aplicação dos filtros globais a um DataFrame
│   ├── export.py               # Geração de Excel/PDF
│   └── sync/                   # Snapshot diário (DuckDB) + agendador (APScheduler)
│
├── components/                 # UI reutilizável (sem regra de negócio)
│   ├── sidebar_filtros.py, theme.py, bi_icons.py, metrics.py, print_btn.py
│   └── widgets/                # Comentários gerenciais, exportação, seleção de linha
│
├── config/settings.py          # Credenciais (via .env) e constantes globais
├── scripts/dev/                # Ferramentas de introspecção do banco (uso manual, não fazem parte do app)
├── docs/                       # Documentação técnica detalhada por módulo
├── data/store.duckdb           # Gerado automaticamente — histórico e configurações locais
├── fbclient.dll                # Cliente Firebird (necessário, incluso no projeto)
├── iniciar.bat                 # Atalho Windows: inicia o Streamlit
└── snapshot_diario.bat         # Atalho Windows: força a coleta do snapshot do dia
```

A separação de camadas é deliberada: **pages/** e **components/** só fazem UI;
**core/domain/** calcula KPIs/classificações/alertas mas nunca faz SQL direto;
**core/data/** é a única camada que conversa com Firebird/DuckDB. Veja
`docs/MANUAL_TECNICO.md` para o detalhamento completo de cada módulo, tabelas
consultadas e funções utilizadas.

## Limitações conhecidas

- **Sem suporte a múltiplas empresas reais** — o cadastro de empresas do ERP é um
  registro único de licença, não uma lista; os dois códigos em uso (`00`/`01`)
  estão fixos em `core/data/repositories/cadastros_repo.py`, não vêm de uma tabela.
- **Sem histórico anterior a ~4 meses** — o histórico diário (`snap_*` no DuckDB)
  só existe a partir de quando o agendador começou a rodar; comparativos
  ano-a-ano (YoY) não são viáveis ainda.
- **Snapshot diário com retry limitado a 3 tentativas no mesmo dia** — o
  agendador tenta a coleta às 08:00, 11:00 e 15:00 (`core/sync/agendador.py
  :: _HORARIOS_TENTATIVA`); cada tentativa extra é segura porque
  `gravar_todos()` já é idempotente — se a coleta de uma tentativa anterior
  deu certo, as seguintes não fazem nada. Se as 3 tentativas falharem (ex.:
  Firebird fora do ar o dia inteiro), só é tentado de novo no dia seguinte.
  O atraso é sinalizado visualmente — badge na seção "Sistema" da Home e
  alerta na Central de Alertas (módulo "Sistema") a partir de 2 dias sem
  coleta — e pode ser forçado manualmente via `snapshot_diario.bat`.
- **`AppTest` (suíte de teste automatizada) não cobre `st.page_link`** —
  limitação conhecida do harness de teste do Streamlit ao rodar uma página
  isoladamente fora do app multipágina completo; não afeta o funcionamento real
  (confirmado via `streamlit run` real).
- **Sem testes automatizados unitários formais** — a validação deste projeto é
  feita via `AppTest` (carregamento/interação de página) e scripts de
  comparação manual contra o banco real; não há suíte `pytest` versionada.
- **Performance de algumas consultas depende do volume de dados do ERP** —
  consultas amplas sem filtro de período (ex. histórico completo de clientes)
  podem ficar lentas conforme a base cresce; já há otimizações aplicadas
  (ver `docs/MANUAL_TECNICO.md`), mas não há paginação no nível de UI.
- **Projeto não versionado em git** — não há repositório `.git` neste diretório;
  recomenda-se inicializar versionamento antes de qualquer deploy ou colaboração
  em equipe.

## Documentação adicional

- `docs/MANUAL_TECNICO.md` — referência completa: telas, funções, tabelas Firebird, achados de auditoria
- `docs/DOCUMENTACAO_SISTEMA.md` — visão geral de arquitetura
- `docs/MODULO_*.md` — detalhamento por módulo (Financeiro, Comercial, Estoque, Compras, Alertas)
- `docs/PLANO_DE_TESTES.md` — roteiro de teste manual por funcionalidade
- `docs/DB_REFERENCE.md` — referência de tabelas/colunas do Firebird usadas
- `docs/PROGRESSO.md` — changelog histórico do desenvolvimento (registro do que foi feito em cada fase — não reflete necessariamente os caminhos de arquivo atuais para entradas antigas)
