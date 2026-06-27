"""
Módulo Financeiro — completo
Filtros globais · Alertas · PMR/PMP · Concentração · Projeção acumulada
Mapa de calor · Comparativos · Exportação · Impressão · Comentários · Drill-Down
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import date
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, ColumnsAutoSizeMode
from components.bi_icons import inject_bi, bi, section_header, render_alerta_cards

from core.domain.financeiro import (
    get_contas_receber, get_contas_pagar, get_estoque_custo,
    get_saldo_bancario, get_evolucao_saldo, get_kpis,
    aging_por_cliente, aging_totais, fluxo_projetado, ap_por_fornecedor,
    get_fluxo_diario, get_titulos_do_dia,
    get_historico_ar, get_historico_ap, get_itens_nf,
    get_comparativo_recebimentos, get_comparativo_pagamentos,
    get_evolucao_inadimplencia, get_acumulado_ano,
    get_projecao_acumulada, get_pmr_pmp, get_concentracao_inadimplencia,
    get_alertas_financeiro, get_heatmap_vencimentos, get_itens_av,
    matriz_heatmap,
)
from core.data.duckdb_store import init_store, get_config, set_config
from core.sync.snapshot import get_evolucao_snapshot
from components.sidebar_filtros import render_sidebar, carregar_opcoes_filtros
from core.domain.filtros import aplicar
from components.print_btn import render_print_css, render_print_button
from components.metrics import fmt_brl, kpi_card
from components.theme import COR_PRIM, COR_OK, COR_ALERTA, COR_PERIGO
from components.widgets import df_selecionavel, selecao_mudou, make_widget_comentario, make_toolbar_export
from core.export import gerar_pdf

st.set_page_config(page_title="Financeiro", page_icon="💰", layout="wide")
init_store()
render_print_css()
inject_bi()

FAIXAS_AR  = ["1-30 dias", "31-60 dias", "61-90 dias", "+90 dias"]
CORES_FAIXA = dict(zip(FAIXAS_AR, ["#2ca02c","#ff7f0e","#d62728","#9467bd"]))
MODULO = "financeiro"


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════
def _grid(df: pd.DataFrame, key: str, height: int = 300):
    """
    Renderiza um AgGrid com seleção de linha única e devolve a linha
    selecionada como dict (ou None se nada estiver selecionado).
    """
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_selection(selection_mode="single", use_checkbox=False, pre_selected_rows=[])
    gb.configure_grid_options(rowHeight=38, headerHeight=38)
    gb.configure_default_column(resizable=True, sortable=True, filter=True,
                                cellStyle={"cursor": "pointer"})
    resp = AgGrid(df, gridOptions=gb.build(),
                  update_mode=GridUpdateMode.SELECTION_CHANGED,
                  height=height, use_container_width=True, key=key,
                  columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS,
                  allow_unsafe_jscode=True)
    # `selected_rows` muda de forma (dict-like, DataFrame ou list) conforme a
    # versão do st_aggrid/AgGrid — tratamos os 3 formatos possíveis.
    sel = resp.get("selected_rows") if isinstance(resp, dict) else getattr(resp, "selected_rows", None)
    if sel is None: return None
    if isinstance(sel, pd.DataFrame): return None if sel.empty else sel.iloc[0].to_dict()
    if isinstance(sel, list): return None if len(sel) == 0 else sel[0]
    return None


def _hist_table(hist: pd.DataFrame):
    """Renderiza a tabela de histórico de movimentações (AR ou AP) com valores já formatados em R$."""
    if hist.empty:
        st.info("Sem movimentações registradas."); return
    h = hist.copy()
    h["DT_MOVIMENTO"] = h["DT_MOVIMENTO"].dt.strftime("%d/%m/%Y %H:%M")
    h["VALORMOV"]     = h["VALORMOV"].apply(fmt_brl)
    h["VALORDESC"]    = h["VALORDESC"].apply(fmt_brl)
    h["JUROSMULTA"]   = h["JUROSMULTA"].apply(fmt_brl)
    cols = (["DESCRICAO"] if "DESCRICAO" in h.columns else []) + \
           ["DT_MOVIMENTO","VALORMOV","VALORDESC","JUROSMULTA","FORMAPGTO","USUARIO"]
    st.dataframe(h[cols].rename(columns={
        "DESCRICAO":"Tipo","DT_MOVIMENTO":"Data","VALORMOV":"Valor",
        "VALORDESC":"Desconto","JUROSMULTA":"Juros/Multa",
        "FORMAPGTO":"Forma Pgto","USUARIO":"Usuário"}),
        use_container_width=True, hide_index=True)


def _itens_table(codempresa: str, tipodocto: str, numdocorig: str):
    """Exibe os itens de produto vinculados ao título (NF via NFSAIDI, AV via PEDIDOI)."""
    st.markdown("---")
    st.markdown(section_header("Itens do Documento", "itens", level=5), unsafe_allow_html=True)
    tipo = tipodocto.strip().upper()

    if tipo == "NF" and str(numdocorig or "").startswith("VP"):
        itens = get_itens_nf(codempresa, tipodocto, numdocorig)
        if itens.empty:
            st.info("Nenhum item encontrado para esta NF.")
        else:
            i = itens.copy()
            i["PRECO_UNIT"] = i["PRECO_UNIT"].apply(fmt_brl)
            i["DESCONTO"]   = i["DESCONTO"].apply(fmt_brl)
            i["TOTAL"]      = i["TOTAL"].apply(fmt_brl)
            st.dataframe(
                i.rename(columns={"CODPROD":"Código","PRODUTO":"Produto",
                    "QUANTIDADE":"Qtd","PRECO_UNIT":"Preço Unit",
                    "DESCONTO":"Desconto","TOTAL":"Total"}),
                use_container_width=True, hide_index=True)

    elif tipo == "AV" and str(numdocorig or "").strip():
        itens = get_itens_av(codempresa, numdocorig)
        if itens.empty:
            st.info("Pedido AV sem itens em PEDIDOI.")
        else:
            i = itens.copy()
            i["PRECO_UNIT"] = i["PRECO_UNIT"].apply(fmt_brl)
            i["DESCONTO"]   = i["DESCONTO"].apply(fmt_brl)
            i["TOTAL"]      = i["TOTAL"].apply(fmt_brl)
            st.dataframe(
                i.rename(columns={"CODPROD":"Código","PRODUTO":"Produto",
                    "QUANTIDADE":"Qtd","PRECO_UNIT":"Preço Unit",
                    "DESCONTO":"Desconto","TOTAL":"Total"}),
                use_container_width=True, hide_index=True)

    else:
        msg = {
            "CO": "Título de convênio — sem itens de produto vinculados.",
        }.get(tipo, f"Tipo '{tipo}' — sem itens de produto vinculados.")
        st.info(msg)


# _widget_comentario, _toolbar_export e _df_selecionavel: ver components/widgets.py
# (antes duplicados de forma idêntica nas 4 páginas de módulo).
_widget_comentario = make_widget_comentario(
    MODULO, placeholder="Ex.: Este mês as compras foram maiores pois as vendas aumentaram 20%...")
_toolbar_export = make_toolbar_export(MODULO)
_df_selecionavel = df_selecionavel


def _btn_carta_cobranca(nome_cli: str, titulos: pd.DataFrame):
    """
    Botão "Gerar carta de cobrança" dentro do drill-down de AR: monta um PDF
    pronto para enviar ao cliente com os títulos vencidos, sem precisar
    montar a planilha manualmente — reaproveita core.export.gerar_pdf, só
    com KPIs/seção específicos deste cliente em vez do módulo inteiro.
    """
    if titulos.empty:
        return
    total_vencido = float(titulos["SALDO_ABERTO"].sum())
    kpis_carta = {
        "Cliente": nome_cli,
        "Total vencido": fmt_brl(total_vencido),
        "Títulos vencidos": str(len(titulos)),
        "Atraso máximo": f"{int(titulos['DIAS_ATRASO'].max())} dias",
    }
    tabela_carta = titulos[["CODDOCTO", "TIPODOCTO", "DT_VENCIMENTO", "SALDO_ABERTO", "DIAS_ATRASO"]].copy()
    tabela_carta["DT_VENCIMENTO"] = tabela_carta["DT_VENCIMENTO"].dt.strftime("%d/%m/%Y")
    tabela_carta["SALDO_ABERTO"]  = tabela_carta["SALDO_ABERTO"].apply(fmt_brl)
    tabela_carta = tabela_carta.rename(columns={
        "CODDOCTO": "Documento", "TIPODOCTO": "Tipo",
        "DT_VENCIMENTO": "Vencimento", "SALDO_ABERTO": "Saldo", "DIAS_ATRASO": "Dias de atraso",
    })
    pdf_bytes = gerar_pdf(
        titulo=f"Cobrança — {nome_cli}",
        kpis=kpis_carta,
        secoes={"Títulos em aberto": tabela_carta},
        comentario="Solicitamos a regularização dos títulos abaixo o mais breve possível.",
    )
    st.download_button(
        "📄 Gerar carta de cobrança (PDF)", data=bytes(pdf_bytes),
        file_name=f"cobranca_{nome_cli.lower().replace(' ', '_')}_{date.today()}.pdf",
        mime="application/pdf",
        help="PDF pronto para enviar ao cliente com os títulos vencidos",
        key=f"carta_cobranca_{nome_cli}")


# ══════════════════════════════════════════════════════════════════
#  DIALOGS — clique na linha para expandir o detalhe
# ══════════════════════════════════════════════════════════════════


@st.dialog("📋 Contas a Receber", width="large")
def dialog_ar():
    """Modal de drill-down: títulos AR vencidos do cliente clicado, com histórico e itens ao selecionar um título."""
    ctx = st.session_state.get("dlg_ctx", {})
    cod_cli, nome_cli = ctx.get("cod_cli"), ctx.get("nome_cli")
    vencidos = ctx.get("df_vencidos")
    if not cod_cli or vencidos is None:
        st.error("Contexto invalido."); return

    st.markdown(f"### {nome_cli}")
    st.caption("Clique em qualquer linha para ver o historico e os itens do titulo.")

    titulos = (vencidos[vencidos["CODCLIENTE"] == cod_cli]
               .sort_values("DIAS_ATRASO", ascending=False)
               .reset_index(drop=True))

    _btn_carta_cobranca(nome_cli, titulos)

    t_exib = titulos[["CODDOCTO","TIPODOCTO","DT_VENCIMENTO",
                       "VALORDOCTO","SALDO_ABERTO","DIAS_ATRASO","FAIXA"]].copy()
    t_exib["DT_VENCIMENTO"] = t_exib["DT_VENCIMENTO"].dt.strftime("%d/%m/%Y")
    t_exib["VALORDOCTO"]    = t_exib["VALORDOCTO"].apply(fmt_brl)
    t_exib["SALDO_ABERTO"]  = t_exib["SALDO_ABERTO"].apply(fmt_brl)
    t_exib = t_exib.rename(columns={"CODDOCTO":"Documento","TIPODOCTO":"Tipo",
        "DT_VENCIMENTO":"Vencimento","VALORDOCTO":"Valor","SALDO_ABERTO":"Saldo",
        "DIAS_ATRASO":"Dias","FAIXA":"Faixa"})

    idx = _df_selecionavel(t_exib, key="dlg_ar_tit")
    if idx is not None:
        t = titulos.iloc[idx]
        st.markdown("---")
        hdr = (f"Histórico — {t['CODDOCTO']} | "
               f"Venc. {t['DT_VENCIMENTO'].strftime('%d/%m/%Y')} | "
               f"{fmt_brl(t['SALDO_ABERTO'])}")
        st.markdown(section_header(hdr, "historico", 5), unsafe_allow_html=True)
        _hist_table(get_historico_ar(t["CODEMPRESA"], t["TIPODOCTO"], t["CODDOCTO"], cod_cli))
        _itens_table(t["CODEMPRESA"], t["TIPODOCTO"], t.get("NUMDOCORIG", ""))


@st.dialog("💳 Contas a Pagar", width="large")
def dialog_ap():
    """Modal de drill-down: títulos AP do fornecedor clicado, com histórico ao selecionar um título."""
    ctx = st.session_state.get("dlg_ctx", {})
    cod_forn, nome_forn = ctx.get("cod_forn"), ctx.get("nome_forn")
    df_ap_all = ctx.get("df_ap_all")
    if not cod_forn or df_ap_all is None:
        st.error("Contexto invalido."); return

    st.markdown(f"### {nome_forn}")
    st.caption("Clique em qualquer linha para ver o historico do titulo.")

    titulos = (df_ap_all[df_ap_all["CODFORNEC"] == cod_forn]
               .sort_values("DT_VENCIMENTO").reset_index(drop=True))

    t_exib = titulos[["CODDOCTO","TIPODOCTO","DT_VENCIMENTO",
                       "VALORDOCTO","SALDO_ABERTO","FAIXA"]].copy()
    t_exib["DT_VENCIMENTO"] = t_exib["DT_VENCIMENTO"].dt.strftime("%d/%m/%Y")
    t_exib["VALORDOCTO"]    = t_exib["VALORDOCTO"].apply(fmt_brl)
    t_exib["SALDO_ABERTO"]  = t_exib["SALDO_ABERTO"].apply(fmt_brl)
    t_exib = t_exib.rename(columns={"CODDOCTO":"Documento","TIPODOCTO":"Tipo",
        "DT_VENCIMENTO":"Vencimento","VALORDOCTO":"Valor","SALDO_ABERTO":"Saldo","FAIXA":"Prazo"})

    idx = _df_selecionavel(t_exib, key="dlg_ap_tit")
    if idx is not None:
        t = titulos.iloc[idx]
        st.markdown("---")
        hdr_ap = (f"Histórico — {t['CODDOCTO']} | "
                  f"Venc. {t['DT_VENCIMENTO'].strftime('%d/%m/%Y')} | "
                  f"{fmt_brl(t['SALDO_ABERTO'])}")
        st.markdown(section_header(hdr_ap, "historico", 5), unsafe_allow_html=True)
        _hist_table(get_historico_ap(t["CODEMPRESA"], t["TIPODOCTO"], t["CODDOCTO"], cod_forn))


@st.dialog("📊 Fluxo de Caixa", width="large")
def dialog_fluxo():
    """Modal de drill-down: gráfico AR×AP por dia no horizonte clicado, com lista de títulos ao selecionar um dia."""
    ctx = st.session_state.get("dlg_ctx", {})
    h_dias, h_nome = ctx.get("h_dias"), ctx.get("h_nome")
    df_ar, df_ap = ctx.get("df_ar"), ctx.get("df_ap")
    if h_dias is None or df_ar is None:
        st.error("Contexto invalido."); return

    st.markdown(f"### Proximos {h_nome}")
    df_dia = get_fluxo_diario(df_ar, df_ap, h_dias)
    if df_dia.empty:
        st.info("Sem lancamentos neste horizonte."); return

    fig = go.Figure()
    fig.add_trace(go.Bar(name="A Receber", x=df_dia["Data"], y=df_dia["A Receber"],
                         marker_color=COR_OK))
    fig.add_trace(go.Bar(name="A Pagar",   x=df_dia["Data"], y=df_dia["A Pagar"],
                         marker_color=COR_PERIGO))
    fig.update_layout(barmode="group", height=220, margin=dict(t=10,b=0,l=0,r=0))
    st.plotly_chart(fig, use_container_width=True)

    # Tabela de dias — clicável
    st.caption("Clique em um dia para ver os titulos:")
    df_dia_exib = df_dia.copy()
    # Normaliza coluna Líquido (pode ter ou não acento dependendo do locale)
    if "Líquido" in df_dia_exib.columns:
        df_dia_exib = df_dia_exib.rename(columns={"Líquido": "Liquido"})
    df_dia_exib["Data"]      = df_dia_exib["Data"].dt.strftime("%d/%m/%Y")
    df_dia_exib["A Receber"] = df_dia_exib["A Receber"].apply(fmt_brl)
    df_dia_exib["A Pagar"]   = df_dia_exib["A Pagar"].apply(fmt_brl)
    if "Liquido" in df_dia_exib.columns:
        df_dia_exib["Liquido"] = df_dia_exib["Liquido"].apply(fmt_brl)

    idx_dia = _df_selecionavel(df_dia_exib[["Data","A Receber","A Pagar"]], key="dlg_fl_dias", height=220)
    if idx_dia is not None:
        data_ts = df_dia.iloc[idx_dia]["Data"]
        ar_dia, ap_dia = get_titulos_do_dia(df_ar, df_ap, data_ts)
        data_str = pd.Timestamp(data_ts).strftime("%d/%m/%Y")

        st.markdown("---")
        st.markdown(f"**{data_str}**")
        col_r, col_p = st.columns(2)

        with col_r:
            st.markdown(f"**Recebimentos ({len(ar_dia)})**")
            if not ar_dia.empty:
                ar_e = ar_dia[["CODDOCTO","NOME_CLIENTE","SALDO_ABERTO"]].copy()
                ar_e["SALDO_ABERTO"] = ar_e["SALDO_ABERTO"].apply(fmt_brl)
                ar_e = ar_e.rename(columns={"CODDOCTO":"Documento",
                    "NOME_CLIENTE":"Cliente","SALDO_ABERTO":"Valor"})
                idx_ar = _df_selecionavel(ar_e, key="dlg_fl_ar_tit", height=180)
                if idx_ar is not None:
                    t = ar_dia.reset_index(drop=True).iloc[idx_ar]
                    st.markdown(f"**Historico — `{t['CODDOCTO']}`**")
                    _hist_table(get_historico_ar(t["CODEMPRESA"],t["TIPODOCTO"],
                                                  t["CODDOCTO"],t["CODCLIENTE"]))
                    _itens_table(t["CODEMPRESA"],t["TIPODOCTO"],t.get("NUMDOCORIG",""))
            else:
                st.info("Sem recebimentos.")

        with col_p:
            st.markdown(f"**Pagamentos ({len(ap_dia)})**")
            if not ap_dia.empty:
                ap_e = ap_dia[["CODDOCTO","NOME_FORNECEDOR","SALDO_ABERTO"]].copy()
                ap_e["SALDO_ABERTO"] = ap_e["SALDO_ABERTO"].apply(fmt_brl)
                ap_e = ap_e.rename(columns={"CODDOCTO":"Documento",
                    "NOME_FORNECEDOR":"Fornecedor","SALDO_ABERTO":"Valor"})
                idx_ap = _df_selecionavel(ap_e, key="dlg_fl_ap_tit", height=180)
                if idx_ap is not None:
                    t = ap_dia.reset_index(drop=True).iloc[idx_ap]
                    st.markdown(f"**Historico — `{t['CODDOCTO']}`**")
                    _hist_table(get_historico_ap(t["CODEMPRESA"],t["TIPODOCTO"],
                                                  t["CODDOCTO"],t["CODFORNEC"]))
            else:
                st.info("Sem pagamentos.")


# ══════════════════════════════════════════════════════════════════
#  CACHE
# ══════════════════════════════════════════════════════════════════
@st.cache_data(ttl=900, show_spinner="Carregando dados…")
def _carregar():
    """Carrega AR, AP, estoque a custo, saldo bancário e evolução de saldo — base de dados da página inteira."""
    return (get_contas_receber(), get_contas_pagar(),
            get_estoque_custo(), get_saldo_bancario(), get_evolucao_saldo())

@st.cache_data(ttl=900)
def _carregar_comparativos():
    """Carrega os comparativos históricos de recebimentos, pagamentos e inadimplência (aba Comparativos)."""
    return (get_comparativo_recebimentos(), get_comparativo_pagamentos(),
            get_evolucao_inadimplencia())

@st.cache_data(ttl=900)
def _carregar_acumulado():
    """Carrega o acumulado do ano corrente vs ano anterior (aba Comparativos)."""
    return get_acumulado_ano()

try:
    df_ar_raw, df_ap_raw, estoque, df_bco, df_evo = _carregar()
    opcoes = carregar_opcoes_filtros()
except Exception as e:
    st.error(f"Erro ao conectar ao banco: {e}"); st.stop()

# ── Sidebar com filtros centralizados ────────────────────────────
# Financeiro usa: período, empresa, vendedor, cliente, fornecedor
filtros = render_sidebar(
    opcoes,
    visiveis=["periodo", "empresa", "vendedor", "cliente", "fornecedor"],
)

data_ini = filtros["data_ini"]
data_fim = filtros["data_fim"]

# Aplica filtros — cada df usa o mapa de colunas correto
df_ar = aplicar(df_ar_raw, filtros, mapa={
    "periodo":   "DT_VENCIMENTO",
    "empresa":   "CODEMPRESA",
    "vendedor":  "CODVENDEDOR",
    "cliente":   "CODCLIENTE",
})
df_ap = aplicar(df_ap_raw, filtros, mapa={
    "periodo":    "DT_VENCIMENTO",
    "empresa":    "CODEMPRESA",
    "fornecedor": "CODFORNEC",
})

kpis = get_kpis(df_ar, df_ap, estoque, df_bco)

# ── Painel de alertas ────────────────────────────────────────────
@st.cache_data(ttl=300)
def _carregar_alertas(_df_ar, _df_ap, _kpis,
                      piso, horas_ap, dias_crit, cap_min):
    """Avalia as regras de alerta financeiro com os thresholds configurados pelo usuário (aba Config)."""
    return get_alertas_financeiro(_df_ar, _df_ap, _kpis,
                                   piso, horas_ap, dias_crit, cap_min)

piso_caixa    = float(get_config("piso_caixa", 50000))
horas_ap_cfg  = int(get_config("alerta_ap_horas", 48))
dias_crit_cfg = int(get_config("alerta_atraso_dias", 90))
cap_min_cfg   = float(get_config("alerta_capital_minimo", 100000))

alertas = _carregar_alertas(df_ar, df_ap, kpis,
                             piso_caixa, horas_ap_cfg, dias_crit_cfg, cap_min_cfg)

if alertas:
    render_alerta_cards(alertas)
    st.markdown("")

# ── KPIs ─────────────────────────────────────────────────────────
col_titulo, col_print = st.columns([9, 1])
with col_titulo:
    st.markdown(
        f"<h1 style='margin:0;display:flex;align-items:center;gap:10px'>"
        f"{bi('financeiro',28,'#1f6bb5')} Financeiro</h1>"
        f"<p style='margin:2px 0 0;color:#888;font-size:0.88em'>"
        f"{bi('calendar3',13,'#888')} Período: "
        f"{data_ini.strftime('%d/%m/%Y')} — {data_fim.strftime('%d/%m/%Y')}</p>",
        unsafe_allow_html=True)
with col_print:
    st.markdown("<div style='margin-top:12px'>", unsafe_allow_html=True)
    render_print_button(key="print_financeiro")
    st.markdown("</div>", unsafe_allow_html=True)

c1,c2,c3,c4,c5,c6 = st.columns(6)
with c1: kpi_card("A Receber",           kpis["total_ar"], cor=COR_OK)
with c2: kpi_card("Vencido (AR)",        kpis["vencido_ar"], cor=COR_PERIGO)
with c3: kpi_card("A Pagar",             kpis["total_ap"], cor=COR_ALERTA)
with c4: kpi_card("Vencido (AP)",        kpis["vencido_ap"], cor=COR_PERIGO)
with c5: kpi_card("Saldo Bancário",      kpis["saldo_bco"],  negativo_ruim=False, cor=COR_PRIM)
with c6: kpi_card("Capital Operacional", kpis["capital_op"], negativo_ruim=True, cor=COR_PRIM)

# Aviso quando o saldo bancário está desatualizado
if not df_bco.empty:
    _data_bco = pd.to_datetime(df_bco["DATA_MOV"].iloc[0])
    _dias_bco  = (pd.Timestamp.now() - _data_bco).days
    if _dias_bco > 3:
        st.warning(
            f"⚠️ Saldo bancário desatualizado — último registro MOVIBAN: "
            f"**{_data_bco.strftime('%d/%m/%Y')}** ({_dias_bco} dias atrás). "
            f"O saldo exibido pode não refletir a posição atual.")
st.divider()

# ── PMR/PMP calculados antes das abas (usado em AR e AP) ─────────
pmr_data = get_pmr_pmp(90)

aba_ar, aba_fluxo, aba_ap, aba_comp, aba_caixa, aba_hist, aba_cal, aba_cfg = st.tabs([
    "📋 Contas a Receber",
    "📊 Fluxo de Caixa",
    "💳 Contas a Pagar",
    "📈 Comparativos",
    "🏦 Posição de Caixa",
    "📉 Histórico",
    "📅 Calendário",
    "⚙️ Configurações",
])


# ══════════════════════════════════════════════════════════════════
#  ABA 1 — CONTAS A RECEBER
# ══════════════════════════════════════════════════════════════════
with aba_ar:
    totais       = aging_totais(df_ar)
    df_aging_cli = aging_por_cliente(df_ar)

    st.markdown(section_header("Distribuição da Inadimplência", "receber", 4),
                unsafe_allow_html=True)
    col_pie, col_bar = st.columns([1, 2])
    with col_pie:
        if not totais.empty:
            fig = px.pie(names=totais.index, values=totais.values,
                         color=totais.index, color_discrete_map=CORES_FAIXA,
                         hole=0.45)
            fig.update_traces(textinfo="percent+label", textfont_size=12)
            fig.update_layout(showlegend=False, margin=dict(t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem títulos vencidos no período selecionado.")
    with col_bar:
        if not df_aging_cli.empty:
            faixas_disp = [f for f in FAIXAS_AR if f in df_aging_cli.columns]
            fig2 = px.bar(df_aging_cli.sort_values("TOTAL").tail(12),
                          y="NOME_CLIENTE", x=faixas_disp, orientation="h",
                          color_discrete_map=CORES_FAIXA,
                          labels={"value": "R$", "variable": "Faixa", "NOME_CLIENTE": ""})
            fig2.update_layout(legend_title="Faixa", margin=dict(t=10, b=0),
                               title="Top inadimplentes por faixa")
            st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    vencidos = df_ar[df_ar["DIAS_ATRASO"] > 0].copy()
    resumo = (
        vencidos.groupby(["CODCLIENTE","NOME_CLIENTE"])
        .agg(Títulos=("CODDOCTO","count"), Total=("SALDO_ABERTO","sum"), Dias_Max=("DIAS_ATRASO","max"))
        .reset_index().sort_values("Total", ascending=False)
    )
    r_exib = resumo.rename(columns={"CODCLIENTE": "Cód", "NOME_CLIENTE": "Cliente", "Dias_Max": "Dias máx."}).copy()
    r_exib["Total"] = r_exib["Total"].apply(fmt_brl)

    # ── PMR + Concentração ────────────────────────────────────────
    conc = get_concentracao_inadimplencia(df_ar)

    col_pmr, col_conc = st.columns([1, 2])
    with col_pmr:
        st.markdown(
            section_header("PMR — Prazo Médio de Recebimento", "historico"),
            unsafe_allow_html=True)
        pmr     = pmr_data.get("pmr")
        pmr_ant = pmr_data.get("pmr_ant")
        if pmr is not None:
            delta_pmr = round(pmr - pmr_ant, 1) if pmr_ant else None
            delta_str = f"{delta_pmr:+.1f} dias vs período ant." if delta_pmr is not None else None
            st.metric("PMR — últimos 90 dias", f"{pmr:.1f} dias",
                      delta=delta_str, delta_color="inverse")
            if pmr < 0:
                st.markdown(
                    f"<small style='color:{COR_OK}'>"
                    f"{bi('ok',13,COR_OK)} Clientes pagando em média "
                    f"{abs(pmr):.0f} dias <b>antes</b> do vencimento</small>",
                    unsafe_allow_html=True)
            elif pmr <= 15:
                st.markdown(
                    f"<small style='color:{COR_OK}'>"
                    f"{bi('ok',13,COR_OK)} Recebimento em dia "
                    f"({pmr:.0f} dias após vencimento)</small>",
                    unsafe_allow_html=True)
            elif pmr <= 30:
                st.markdown(
                    f"<small style='color:#e67e22'>"
                    f"{bi('warning',13,'#e67e22')} Atenção: clientes pagando "
                    f"{pmr:.0f} dias após o vencimento</small>",
                    unsafe_allow_html=True)
            else:
                st.markdown(
                    f"<small style='color:{COR_PERIGO}'>"
                    f"{bi('warning',13,COR_PERIGO)} Inadimplência elevada — "
                    f"clientes pagando {pmr:.0f} dias após o vencimento</small>",
                    unsafe_allow_html=True)
        else:
            st.info("Sem liquidações nos últimos 90 dias.")

    with col_conc:
        st.markdown(section_header("Concentração de Inadimplência", "receber", 5),
                    unsafe_allow_html=True)
        if conc["total"] > 0:
            top3 = conc["top3_perc"]
            top5 = conc["top5_perc"]
            n    = conc["n_clientes"]
            cor_conc = COR_PERIGO if top3 > 60 else (COR_ALERTA if top3 > 40 else COR_OK)
            st.markdown(
                f"<div style='display:flex;gap:20px;align-items:center'>"
                f"<div style='text-align:center'><div style='font-size:2rem;font-weight:bold;color:{cor_conc}'>{top3}%</div>"
                f"<small>Top 3 clientes</small></div>"
                f"<div style='text-align:center'><div style='font-size:2rem;font-weight:bold;color:{COR_PRIM}'>{top5}%</div>"
                f"<small>Top 5 clientes</small></div>"
                f"<div style='text-align:center'><div style='font-size:2rem;font-weight:bold'>{n}</div>"
                f"<small>Clientes inadimplentes</small></div>"
                f"</div>",
                unsafe_allow_html=True)
            if top3 > 60:
                st.markdown(f"<small style='color:{COR_PERIGO}'>{bi('exclamation-triangle-fill',13,COR_PERIGO)} "
                            f"Alta concentração: 3 clientes respondem por mais de 60% da inadimplência</small>",
                            unsafe_allow_html=True)
            # Tabela top 10 concentração
            with st.expander("Ver distribuição completa"):
                top10 = conc["dados"].head(10).copy()
                top10["Valor"] = top10["Valor"].apply(fmt_brl)
                st.dataframe(top10, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(f"**{bi('clique',14,'#1f6bb5')} Clique em um cliente para abrir o detalhamento:**",
                unsafe_allow_html=True)
    sel_cli = _grid(r_exib, key="ar_clientes", height=360)
    if selecao_mudou("ar_clientes", sel_cli):
        st.session_state["dlg_ctx"] = {"cod_cli": sel_cli["Cód"], "nome_cli": sel_cli["Cliente"], "df_vencidos": vencidos}
        dialog_ar()

    # Exportação + Comentário
    st.divider()
    kpis_ar_exp = {
        "Total a Receber": fmt_brl(kpis["total_ar"]),
        "Total Vencido":   fmt_brl(kpis["vencido_ar"]),
        "Qtd. Títulos":    str(len(vencidos)),
    }
    secoes_ar = {"Inadimplentes": r_exib, "Detalhe Títulos": vencidos[["CODCLIENTE","NOME_CLIENTE","CODDOCTO","DT_VENCIMENTO","SALDO_ABERTO","FAIXA"]].assign(DT_VENCIMENTO=lambda d: d["DT_VENCIMENTO"].dt.strftime("%d/%m/%Y"))}
    _toolbar_export("Contas a Receber", secoes_ar, kpis_ar_exp, data_ini, data_fim, "ar")
    _widget_comentario("ar", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 2 — FLUXO DE CAIXA
# ══════════════════════════════════════════════════════════════════
with aba_fluxo:
    df_fluxo = fluxo_projetado(df_ar, df_ap)
    fig_f = go.Figure()
    fig_f.add_trace(go.Bar(name="A Receber",x=df_fluxo["Horizonte"],y=df_fluxo["A Receber"],marker_color=COR_OK))
    fig_f.add_trace(go.Bar(name="A Pagar",  x=df_fluxo["Horizonte"],y=df_fluxo["A Pagar"],  marker_color=COR_PERIGO))
    fig_f.add_trace(go.Scatter(name="Líquido",x=df_fluxo["Horizonte"],y=df_fluxo["Líquido"],
                               mode="lines+markers",line=dict(color=COR_PRIM,width=2)))
    fig_f.update_layout(barmode="group",yaxis_title="R$",title="Recebimentos vs Pagamentos por horizonte",
                        legend=dict(orientation="h",yanchor="bottom",y=1.02),margin=dict(t=60,b=0))
    st.plotly_chart(fig_f, use_container_width=True)

    st.divider()
    # ── Projeção de Caixa Acumulada ───────────────────────────────
    st.divider()
    st.markdown(section_header("Projeção de Caixa Acumulada", "caixa", 4), unsafe_allow_html=True)
    st.caption("Saldo bancário atual + AR previsto − AP previsto, dia a dia por 90 dias")

    proj = get_projecao_acumulada(df_ar, df_ap, kpis["saldo_bco"], dias=90)

    fig_proj = go.Figure()
    # Área preenchida de fundo — vermelho onde abaixo do piso
    fig_proj.add_hline(y=piso_caixa, line_dash="dash",
                       line_color=COR_PERIGO, opacity=0.6,
                       annotation_text=f"Piso mínimo ({fmt_brl(piso_caixa)})",
                       annotation_position="bottom right")
    # Área do saldo projetado
    cores_saldo = [COR_PERIGO if v < piso_caixa else COR_OK for v in proj["Saldo"]]
    fig_proj.add_trace(go.Scatter(
        x=proj["Data"], y=proj["Saldo"],
        mode="lines", name="Saldo projetado",
        fill="tozeroy",
        line=dict(color=COR_PRIM, width=2),
        fillcolor="rgba(31,107,181,0.12)",
    ))
    # Entradas e saídas como barras sobrepostas
    fig_proj.add_trace(go.Bar(
        x=proj["Data"], y=proj["Entradas"],
        name="Recebimentos", marker_color=COR_OK, opacity=0.4,
        yaxis="y2",
    ))
    fig_proj.add_trace(go.Bar(
        x=proj["Data"], y=-proj["Saídas"],
        name="Pagamentos", marker_color=COR_PERIGO, opacity=0.4,
        yaxis="y2",
    ))
    fig_proj.update_layout(
        yaxis=dict(title="Saldo (R$)", side="left"),
        yaxis2=dict(title="Movimentos (R$)", side="right", overlaying="y"),
        barmode="relative", height=320,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=30, b=0),
    )
    st.plotly_chart(fig_proj, use_container_width=True)

    # Mini KPIs da projeção (iloc[-1] seguro: filtra com .iloc[-1] só se a série não for vazia)
    _s7  = proj[proj["Data"] <= pd.Timestamp.now() + pd.Timedelta(days=7)]["Saldo"]
    _s30 = proj[proj["Data"] <= pd.Timestamp.now() + pd.Timedelta(days=30)]["Saldo"]
    saldo_7  = float(_s7.iloc[-1])  if not _s7.empty  else float(proj["Saldo"].iloc[0])
    saldo_30 = float(_s30.iloc[-1]) if not _s30.empty else float(proj["Saldo"].iloc[-1])
    saldo_90 = float(proj["Saldo"].iloc[-1])
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Saldo hoje",   fmt_brl(kpis["saldo_bco"]))
    with c2: st.metric("Em 7 dias",    fmt_brl(saldo_7),
                       delta=fmt_brl(saldo_7 - kpis["saldo_bco"]),
                       delta_color="normal")
    with c3: st.metric("Em 30 dias",   fmt_brl(saldo_30),
                       delta=fmt_brl(saldo_30 - kpis["saldo_bco"]),
                       delta_color="normal")
    with c4: st.metric("Em 90 dias",   fmt_brl(saldo_90),
                       delta=fmt_brl(saldo_90 - kpis["saldo_bco"]),
                       delta_color="normal")

    st.divider()
    df_fl_exib = df_fluxo.copy()
    for col in ["A Receber","A Pagar","Líquido"]:
        df_fl_exib[col] = df_fl_exib[col].apply(fmt_brl)
    st.markdown(f"**{bi('clique',14,'#1f6bb5')} Clique em um horizonte para detalhar:**",
                unsafe_allow_html=True)
    sel_hor = _grid(df_fl_exib, key="fl_horizontes", height=240)
    if selecao_mudou("fl_horizontes", sel_hor):
        h_nome = sel_hor["Horizonte"]
        h_dias = int(h_nome.split()[0])
        st.session_state["dlg_ctx"] = {"h_dias": h_dias, "h_nome": h_nome, "df_ar": df_ar, "df_ap": df_ap}
        dialog_fluxo()

    # Exportação + Comentário
    st.divider()
    kpis_fl_exp = {"A Receber (30d)": fmt_brl(df_fluxo[df_fluxo["Horizonte"]=="30 dias"]["A Receber"].iloc[0] if len(df_fluxo) >= 3 else 0),
                   "A Pagar (30d)":   fmt_brl(df_fluxo[df_fluxo["Horizonte"]=="30 dias"]["A Pagar"].iloc[0] if len(df_fluxo) >= 3 else 0)}
    _toolbar_export("Fluxo de Caixa", {"Projeção": df_fluxo}, kpis_fl_exp, data_ini, data_fim, "fluxo")
    _widget_comentario("fluxo", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 3 — CONTAS A PAGAR
# ══════════════════════════════════════════════════════════════════
with aba_ap:
    df_ap_forn = ap_por_fornecedor(df_ap)
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        if not df_ap_forn.empty:
            fig_ap = px.bar(df_ap_forn.head(12).sort_values("Total"),
                            y="Fornecedor", x="Total", orientation="h",
                            title="A pagar por fornecedor",
                            color="Total", color_continuous_scale="Reds", labels={"Total":"R$"})
            fig_ap.update_layout(coloraxis_showscale=False, margin=dict(t=40,b=0))
            st.plotly_chart(fig_ap, use_container_width=True)
    with col_a2:
        if not df_ap.empty:
            faixas = df_ap.groupby("FAIXA")["SALDO_ABERTO"].sum().reset_index()
            faixas.columns = ["Faixa","Total"]
            ordem = ["Vencido","0-7 dias","8-15 dias","15-30 dias","31-60 dias","61-90 dias","+90 dias"]
            faixas["Faixa"] = pd.Categorical(faixas["Faixa"],categories=ordem,ordered=True)
            fig_ap2 = px.bar(faixas.sort_values("Faixa"),x="Faixa",y="Total",
                             title="A pagar por prazo",labels={"Total":"R$"})
            fig_ap2.update_layout(showlegend=False, margin=dict(t=40,b=0))
            st.plotly_chart(fig_ap2, use_container_width=True)

    st.divider()
    resumo_forn = (df_ap.groupby(["CODFORNEC","NOME_FORNECEDOR"])
        .agg(Títulos=("CODDOCTO","count"),Total=("SALDO_ABERTO","sum"))
        .reset_index().sort_values("Total",ascending=False).reset_index(drop=True))
    rf_exib = resumo_forn.rename(columns={"CODFORNEC":"Cód","NOME_FORNECEDOR":"Fornecedor"}).copy()
    rf_exib["Total"] = rf_exib["Total"].apply(fmt_brl)

    st.divider()
    st.markdown(section_header("PMP — Prazo Médio de Pagamento", "historico", 5),
                unsafe_allow_html=True)
    pmp_val = pmr_data.get("pmp")
    pmp_ant = pmr_data.get("pmp_ant")
    if pmp_val is not None:
        delta_pmp = round(pmp_val - pmp_ant, 1) if pmp_ant else None
        st.metric("Últimos 90 dias",
                  f"{pmp_val:.1f} dias",
                  delta=f"{delta_pmp:+.1f} dias vs período ant." if delta_pmp else None,
                  delta_color="inverse")
        if pmp_val < -15:
            st.markdown(
                f"<small style='color:#e67e22'>"
                f"{bi('info',13,'#e67e22')} Empresa pagando fornecedores "
                f"<b>{abs(pmp_val):.0f} dias antes</b> do vencimento — "
                f"oportunidade de melhorar o fluxo de caixa</small>",
                unsafe_allow_html=True)
        elif pmp_val < 0:
            st.caption(f"Pagamentos realizados {abs(pmp_val):.0f} dias antes do vencimento em média.")
        else:
            st.caption("Dias médios entre o vencimento e a liquidação dos títulos a pagar.")
    else:
        st.info("Sem liquidações nos últimos 90 dias.")
    st.divider()
    st.markdown(f"**{bi('clique',14,'#1f6bb5')} Clique em um fornecedor para detalhar:**",
                unsafe_allow_html=True)
    sel_forn = _grid(rf_exib, key="ap_fornec", height=320)
    if selecao_mudou("ap_fornec", sel_forn):
        st.session_state["dlg_ctx"] = {"cod_forn": sel_forn["Cód"], "nome_forn": sel_forn["Fornecedor"], "df_ap_all": df_ap}
        dialog_ap()

    st.divider()
    kpis_ap_exp = {"Total a Pagar": fmt_brl(kpis["total_ap"]), "Vencido AP": fmt_brl(kpis["vencido_ap"])}
    _toolbar_export("Contas a Pagar", {"Por Fornecedor": rf_exib}, kpis_ap_exp, data_ini, data_fim, "ap")
    _widget_comentario("ap", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 4 — COMPARATIVOS HISTÓRICOS
# ══════════════════════════════════════════════════════════════════
with aba_comp:
    st.markdown(section_header("Comparativos Históricos", "comparativo", 3), unsafe_allow_html=True)
    st.caption("Baseado em liquidações reais (MOVIREC/MOVIPAG) — últimos 13 meses")

    try:
        df_rec, df_pag, df_inadimp = _carregar_comparativos()
    except Exception as e:
        st.error(f"Erro ao carregar comparativos: {e}")
        df_rec = df_pag = df_inadimp = pd.DataFrame()

    col_c1, col_c2 = st.columns(2)

    with col_c1:
        if not df_rec.empty:
            fig_rec = px.bar(df_rec, x="MES_ANO", y="RECEBIDO",
                             title="Recebimentos liquidados por mês",
                             labels={"MES_ANO":"Mês/Ano","RECEBIDO":"R$"},
                             color_discrete_sequence=[COR_OK])
            fig_rec.update_layout(margin=dict(t=40,b=0))
            st.plotly_chart(fig_rec, use_container_width=True)

            # Comparativo mês atual vs anterior
            if len(df_rec) >= 2:
                mes_atual = df_rec.iloc[-1]
                mes_ant   = df_rec.iloc[-2]
                delta = float(mes_atual["RECEBIDO"]) - float(mes_ant["RECEBIDO"])
                c1, c2, c3 = st.columns(3)
                with c1: st.metric(f"Mês atual ({mes_atual['MES_ANO']})",
                                   fmt_brl(float(mes_atual["RECEBIDO"])))
                with c2: st.metric(f"Mês anterior ({mes_ant['MES_ANO']})",
                                   fmt_brl(float(mes_ant["RECEBIDO"])),
                                   delta=fmt_brl(delta))
                if len(df_rec) >= 14:
                    mes_ano_ant = df_rec.iloc[-13]
                    with c3: st.metric(f"Mesmo mês ano ant. ({mes_ano_ant['MES_ANO']})",
                                       fmt_brl(float(mes_ano_ant["RECEBIDO"])))
        else:
            st.info("Sem dados de recebimentos no período.")

    with col_c2:
        if not df_pag.empty:
            fig_pag = px.bar(df_pag, x="MES_ANO", y="PAGO",
                             title="Pagamentos liquidados por mês",
                             labels={"MES_ANO":"Mês/Ano","PAGO":"R$"},
                             color_discrete_sequence=[COR_PERIGO])
            fig_pag.update_layout(margin=dict(t=40,b=0))
            st.plotly_chart(fig_pag, use_container_width=True)

            if len(df_pag) >= 2:
                m_atual = df_pag.iloc[-1]
                m_ant   = df_pag.iloc[-2]
                delta_p = float(m_atual["PAGO"]) - float(m_ant["PAGO"])
                c1, c2 = st.columns(2)
                with c1: st.metric(f"Mês atual ({m_atual['MES_ANO']})",
                                   fmt_brl(float(m_atual["PAGO"])))
                with c2: st.metric(f"Mês anterior ({m_ant['MES_ANO']})",
                                   fmt_brl(float(m_ant["PAGO"])),
                                   delta=fmt_brl(delta_p))
        else:
            st.info("Sem dados de pagamentos no período.")

    # Evolução da inadimplência (snapshots DuckDB)
    st.divider()
    st.markdown(section_header("Evolução da Inadimplência", "warning", 4), unsafe_allow_html=True)
    df_snap = get_evolucao_snapshot()
    if df_snap.empty or len(df_snap) < 2:
        st.info("A evolução da inadimplência acumula dados a partir do go-live. "
                f"Hoje foi gravado o primeiro registro: **{fmt_brl(kpis['vencido_ar'])}** em vencido. "
                "O gráfico preencherá com o tempo.")
    else:
        fig_inad = px.area(df_snap, x="data", y="valor_vencido",
                           title="Evolução do valor vencido (snapshots diários)",
                           labels={"data":"Data","valor_vencido":"R$ Vencido"},
                           color_discrete_sequence=[COR_PERIGO])
        fig_inad.update_layout(margin=dict(t=40,b=0))
        st.plotly_chart(fig_inad, use_container_width=True)

    # ── Acumulado do Ano ─────────────────────────────────────────
    st.divider()
    st.markdown(section_header("Acumulado do Ano", "comparativo", 4), unsafe_allow_html=True)
    try:
        acum = _carregar_acumulado()
        a1, a2, a3, a4 = st.columns(4)
        delta_rec = acum["recebido_ano"] - acum["recebido_ano_ant"]
        delta_pag = acum["pago_ano"]     - acum["pago_ano_ant"]
        with a1:
            st.metric(f"Recebido {acum['ano']}",    fmt_brl(acum["recebido_ano"]))
        with a2:
            st.metric(f"Recebido {acum['ano_ant']}", fmt_brl(acum["recebido_ano_ant"]),
                      delta=fmt_brl(delta_rec))
        with a3:
            st.metric(f"Pago {acum['ano']}",    fmt_brl(acum["pago_ano"]))
        with a4:
            st.metric(f"Pago {acum['ano_ant']}", fmt_brl(acum["pago_ano_ant"]),
                      delta=fmt_brl(delta_pag))
        st.caption(f"Comparativo: 01/01/{acum['ano']} até hoje vs mesmo período de {acum['ano_ant']}")
    except Exception as e:
        st.warning(f"Acumulado do ano indisponível: {e}")

    # Evolução inadimplência por faixas (se tiver dados)
    if not df_inadimp.empty:
        st.divider()
        st.markdown(section_header("Inadimplência aberta — por mês de vencimento", "warning", 4), unsafe_allow_html=True)
        fig_inad2 = px.bar(df_inadimp, x="MES_ANO", y="VENCIDO",
                           title="Saldo vencido por mês (títulos ainda abertos)",
                           labels={"MES_ANO":"Mês/Ano","VENCIDO":"R$"},
                           color_discrete_sequence=[COR_PERIGO])
        fig_inad2.update_layout(margin=dict(t=40,b=0))
        st.plotly_chart(fig_inad2, use_container_width=True)

    st.divider()
    kpis_comp_exp = {}
    sec_comp = {}
    if not df_rec.empty: sec_comp["Recebimentos por mês"] = df_rec[["MES_ANO","RECEBIDO"]]
    if not df_pag.empty: sec_comp["Pagamentos por mês"]   = df_pag[["MES_ANO","PAGO"]]
    _toolbar_export("Comparativos Históricos", sec_comp, kpis_comp_exp, data_ini, data_fim, "comparativos")
    _widget_comentario("comparativos", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 5 — POSIÇÃO DE CAIXA
# ══════════════════════════════════════════════════════════════════
with aba_caixa:
    col_w, col_det = st.columns([1,1])
    with col_w:
        componentes = {
            "Saldo Bancário":  kpis["saldo_bco"],
            "A Receber":       kpis["total_ar"],
            "Estoque (custo)": kpis["estoque_custo"],
            "A Pagar":        -kpis["total_ap"],
        }
        fig_wf = go.Figure(go.Waterfall(
            orientation="v",
            measure=["relative","relative","relative","relative","total"],
            x=list(componentes.keys())+["Capital Operacional"],
            y=list(componentes.values())+[0],
            connector={"line":{"color":"rgb(63,63,63)"}},
            increasing={"marker":{"color":COR_OK}},
            decreasing={"marker":{"color":COR_PERIGO}},
            totals={"marker":{"color":COR_PRIM}},
        ))
        fig_wf.update_layout(title="Capital Operacional",showlegend=False,margin=dict(t=40,b=0))
        st.plotly_chart(fig_wf, use_container_width=True)

    with col_det:
        st.markdown("**Detalhamento**")
        for label, valor in [("Saldo Bancário",kpis["saldo_bco"]),("A Receber (total)",kpis["total_ar"]),
                              ("Estoque ao custo",kpis["estoque_custo"]),("A Pagar (total)",-kpis["total_ap"])]:
            cor = COR_PERIGO if valor < 0 else COR_OK
            st.markdown(f"<div style='display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #eee'>"
                        f"<span>{label}</span><span style='color:{cor};font-weight:bold'>{fmt_brl(abs(valor))}</span></div>",
                        unsafe_allow_html=True)
        st.markdown(f"<div style='display:flex;justify-content:space-between;padding:10px 0;border-top:2px solid #333;margin-top:4px'>"
                    f"<span style='font-weight:bold;font-size:1.1em'>Capital Operacional</span>"
                    f"<span style='color:{COR_PRIM};font-weight:bold;font-size:1.1em'>{fmt_brl(kpis['capital_op'])}</span></div>",
                    unsafe_allow_html=True)
        if not df_bco.empty:
            st.markdown("---")
            bco_exib = df_bco.copy()
            bco_exib["SALDO"]    = bco_exib["SALDO"].apply(fmt_brl)
            bco_exib["DATA_MOV"] = pd.to_datetime(bco_exib["DATA_MOV"]).dt.strftime("%d/%m/%Y")
            st.dataframe(bco_exib.rename(columns={"CODBANCO":"Banco","CONTA":"Conta","SALDO":"Saldo","DATA_MOV":"Última mov."}),
                         use_container_width=True, hide_index=True)

    if not df_evo.empty and len(df_evo) > 1:
        st.divider()
        fig_evo = px.area(df_evo.tail(60),x="DATASALDO",y="SALDO",
                          title="Evolução do saldo — últimos 60 registros",
                          labels={"DATASALDO":"Data","SALDO":"R$"},
                          color_discrete_sequence=[COR_PRIM])
        fig_evo.update_layout(margin=dict(t=40,b=0))
        st.plotly_chart(fig_evo, use_container_width=True)

    st.divider()
    kpis_cx_exp = {k: fmt_brl(v) for k, v in kpis.items()}
    _toolbar_export("Posição de Caixa",
                    {"Saldo Bancário": df_bco.rename(columns={"CODBANCO":"Banco","CONTA":"Conta","SALDO":"Saldo","DATA_MOV":"Data"})},
                    kpis_cx_exp, data_ini, data_fim, "caixa")
    _widget_comentario("caixa", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 6 — HISTÓRICO (snapshots diários DuckDB)
# ══════════════════════════════════════════════════════════════════
with aba_hist:
    st.markdown(section_header("Histórico de Indicadores Financeiros", "clock-history", 3),
                unsafe_allow_html=True)
    st.caption(
        bi("info", 13, "#888") + " Dados coletados diariamente pelo agendador (tentativas às 08h, 11h e 15h). "
        "Gráficos aparecem após 3+ dias de coleta.",
        unsafe_allow_html=True)

    @st.cache_data(ttl=1800, show_spinner=False)
    def _hist_fin():
        """Carrega do DuckDB os snapshots diários de KPIs, inadimplência e saldo bancário (aba Histórico)."""
        from core.sync.snapshot import get_evolucao_kpis, get_evolucao_inadimplencia, get_evolucao_saldo_bancario
        return get_evolucao_kpis(), get_evolucao_inadimplencia(), get_evolucao_saldo_bancario()

    df_hk, df_hi, df_hs = _hist_fin()
    MIN_PT = 3

    # ── Saldo Bancário histórico ──────────────────────────────────
    st.markdown(section_header("Evolução do Saldo Bancário", "bank", 5), unsafe_allow_html=True)
    if df_hs.empty or len(df_hs) < MIN_PT:
        st.info(f"Aguardando {MIN_PT} snapshots (atual: {len(df_hs)}). Coletado diariamente.")
    else:
        df_hs["data"] = pd.to_datetime(df_hs["data"])
        fig_sb = go.Figure()
        fig_sb.add_trace(go.Scatter(
            x=df_hs["data"], y=df_hs["saldo_total"],
            mode="lines+markers", name="Saldo Bancário",
            fill="tozeroy", line=dict(color=COR_PRIM, width=2),
        ))
        fig_sb.update_layout(
            height=260, margin=dict(l=5, r=5, t=10, b=5),
            yaxis_title="R$", xaxis_title="")
        st.plotly_chart(fig_sb, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── AR/AP/Capital histórico ───────────────────────────────────
    st.markdown(section_header("Evolução de AR, AP e Capital Operacional", "bar-chart", 5),
                unsafe_allow_html=True)
    if df_hk.empty or len(df_hk) < MIN_PT:
        st.info(f"Aguardando {MIN_PT} snapshots (atual: {len(df_hk)}). Coletado diariamente.")
    else:
        df_hk["data"] = pd.to_datetime(df_hk["data"])
        col_h1, col_h2 = st.columns(2)
        with col_h1:
            fh1 = go.Figure()
            fh1.add_trace(go.Scatter(
                x=df_hk["data"], y=df_hk["total_ar"],
                mode="lines+markers", name="A Receber",
                line=dict(color=COR_OK, width=2)))
            fh1.add_trace(go.Scatter(
                x=df_hk["data"], y=df_hk["vencido_ar"],
                mode="lines+markers", name="Vencido AR",
                line=dict(color=COR_PERIGO, width=2, dash="dot")))
            fh1.add_trace(go.Scatter(
                x=df_hk["data"], y=df_hk["total_ap"],
                mode="lines+markers", name="A Pagar",
                line=dict(color=COR_ALERTA, width=2)))
            fh1.update_layout(
                height=300, margin=dict(l=5, r=5, t=10, b=5),
                yaxis_title="R$",
                legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fh1, use_container_width=True)

        with col_h2:
            fh2 = go.Figure()
            fh2.add_trace(go.Scatter(
                x=df_hk["data"], y=df_hk["capital_op"],
                mode="lines+markers", name="Capital Operacional",
                fill="tozeroy",
                line=dict(
                    color=COR_OK if float(df_hk["capital_op"].iloc[-1]) > 0 else COR_PERIGO,
                    width=2)))
            fh2.add_hline(y=0, line_dash="dash", line_color="#888",
                          annotation_text="Zero", annotation_position="right")
            fh2.update_layout(
                height=300, margin=dict(l=5, r=5, t=10, b=5),
                yaxis_title="R$", showlegend=False)
            st.plotly_chart(fh2, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Inadimplência histórica ───────────────────────────────────
    st.markdown(section_header("Evolução da Inadimplência (AR Vencido por Faixa)", "exclamation-triangle", 5),
                unsafe_allow_html=True)
    if df_hi.empty or len(df_hi) < MIN_PT:
        st.info(f"Aguardando {MIN_PT} snapshots (atual: {len(df_hi)}). Coletado diariamente.")
    else:
        df_hi["data"] = pd.to_datetime(df_hi["data"])
        fi = go.Figure()
        for col_s, label, cor in [
            ("faixa_1_30",   "1–30 dias",  "#f0b429"),
            ("faixa_31_60",  "31–60 dias", COR_ALERTA),
            ("faixa_61_90",  "61–90 dias", "#c0392b"),
            ("faixa_90_mais","90d+",        COR_PERIGO),
        ]:
            if col_s in df_hi.columns:
                fi.add_trace(go.Bar(
                    x=df_hi["data"], y=df_hi[col_s],
                    name=label, marker_color=cor))
        fi.update_layout(
            barmode="stack", height=300,
            yaxis_title="R$", margin=dict(l=5, r=5, t=10, b=5),
            legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fi, use_container_width=True)

    # Tabela dos snapshots
    with st.expander("📋 Ver tabela de snapshots"):
        if not df_hk.empty:
            tbl = df_hk.copy()
            for col in ["total_ar","vencido_ar","total_ap","vencido_ap","saldo_bco","capital_op","estoque_custo"]:
                if col in tbl.columns:
                    tbl[col] = tbl[col].apply(fmt_brl)
            tbl["data"] = tbl["data"].dt.strftime("%d/%m/%Y")
            st.dataframe(tbl, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum snapshot coletado ainda.")


# ══════════════════════════════════════════════════════════════════
#  ABA 7 — CALENDÁRIO DE VENCIMENTOS (Mapa de Calor)
# ══════════════════════════════════════════════════════════════════
with aba_cal:
    st.markdown(section_header("Mapa de Calor — Vencimentos dos próximos 42 dias", "calendario", 3), unsafe_allow_html=True)
    st.caption("Intensidade da cor = volume financeiro vencendo naquele dia. Passe o mouse para ver os valores.")

    df_heat = get_heatmap_vencimentos(df_ar, df_ap, semanas=6)

    if df_heat.empty:
        st.info("Sem vencimentos nos próximos 42 dias.")
    else:
        # Montar matrizes para AR, AP e Total
        DIAS_PT = ["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"]
        n_sem   = int(df_heat["Semana"].max()) + 1

        M_ar, lbl, hov = matriz_heatmap(df_heat, "AR", n_sem, fmt_brl)
        M_ap, _,   _   = matriz_heatmap(df_heat, "AP", n_sem, fmt_brl)
        M_tot, _,  _   = matriz_heatmap(df_heat, "Total", n_sem, fmt_brl)

        col_heat1, col_heat2 = st.columns(2)

        with col_heat1:
            st.markdown(f"**{bi('check-circle-fill',14,COR_OK)} Recebimentos (AR)**",
                        unsafe_allow_html=True)
            fig_har = go.Figure(go.Heatmap(
                z=M_ar, text=lbl, hovertext=hov,
                hovertemplate="%{hovertext}<extra></extra>",
                texttemplate="%{text}",
                colorscale=[[0,"#f0fdf4"],[0.5,"#4ade80"],[1,"#15803d"]],
                showscale=False,
            ))
            fig_har.update_layout(
                yaxis=dict(tickvals=list(range(7)), ticktext=DIAS_PT, autorange="reversed"),
                xaxis=dict(title="Semana"),
                height=260, margin=dict(t=10,b=0,l=0,r=0),
            )
            st.plotly_chart(fig_har, use_container_width=True)

        with col_heat2:
            st.markdown(f"**{bi('record-circle-fill',14,COR_PERIGO)} Pagamentos (AP)**",
                        unsafe_allow_html=True)
            fig_hap = go.Figure(go.Heatmap(
                z=M_ap, text=lbl, hovertext=hov,
                hovertemplate="%{hovertext}<extra></extra>",
                texttemplate="%{text}",
                colorscale=[[0,"#fff5f5"],[0.5,"#fc8181"],[1,"#c53030"]],
                showscale=False,
            ))
            fig_hap.update_layout(
                yaxis=dict(tickvals=list(range(7)), ticktext=DIAS_PT, autorange="reversed"),
                xaxis=dict(title="Semana"),
                height=260, margin=dict(t=10,b=0,l=0,r=0),
            )
            st.plotly_chart(fig_hap, use_container_width=True)

        # Heatmap combinado (total)
        st.markdown(f"**{bi('bar-chart-fill',14,COR_PRIM)} Total (AR + AP)**",
                    unsafe_allow_html=True)
        fig_htot = go.Figure(go.Heatmap(
            z=M_tot, text=lbl, hovertext=hov,
            hovertemplate="%{hovertext}<extra></extra>",
            texttemplate="%{text}",
            colorscale=[[0,"#f0f4ff"],[0.5,"#818cf8"],[1,"#3730a3"]],
            showscale=True,
            colorbar=dict(title="R$", tickformat=",.0f"),
        ))
        fig_htot.update_layout(
            yaxis=dict(tickvals=list(range(7)), ticktext=DIAS_PT, autorange="reversed"),
            xaxis=dict(title="Semana"),
            height=260, margin=dict(t=10,b=30,l=0,r=60),
        )
        st.plotly_chart(fig_htot, use_container_width=True)

        # Tabela dos dias com maior concentração
        st.divider()
        st.markdown("**Dias com maior volume de vencimentos:**")
        top_dias = df_heat[df_heat["Total"] > 0].nlargest(10, "Total")[
            ["Label","AR","AP","Total"]].copy()
        top_dias["AR"]    = top_dias["AR"].apply(fmt_brl)
        top_dias["AP"]    = top_dias["AP"].apply(fmt_brl)
        top_dias["Total"] = top_dias["Total"].apply(fmt_brl)
        st.dataframe(top_dias.rename(columns={"Label":"Data"}),
                     use_container_width=True, hide_index=True)

    _widget_comentario("calendario", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 7 — CONFIGURAÇÕES DE ALERTAS
# ══════════════════════════════════════════════════════════════════
with aba_cfg:
    st.markdown(section_header("Configurações dos Alertas", "config", 3), unsafe_allow_html=True)
    st.caption("Defina os limites que acionam os alertas no topo da página.")

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        novo_piso = st.number_input(
            "💰 Piso mínimo de caixa (R$)",
            min_value=0.0, step=5000.0,
            value=float(get_config("piso_caixa", 50000)),
            help="Abaixo deste valor o alerta de caixa é acionado na projeção acumulada")
        novo_cap = st.number_input(
            "📊 Capital operacional mínimo (R$)",
            min_value=0.0, step=10000.0,
            value=float(get_config("alerta_capital_minimo", 100000)),
            help="Alerta quando Capital Operacional cair abaixo deste valor")

    with col_c2:
        novo_horas = st.number_input(
            "⏰ Alertar AP vencendo em (horas)",
            min_value=1, max_value=168, step=12,
            value=int(get_config("alerta_ap_horas", 48)),
            help="Quantas horas antes do vencimento gerar alerta de AP urgente")
        novo_dias = st.number_input(
            "📋 Dias de atraso para cliente crítico",
            min_value=1, max_value=365, step=10,
            value=int(get_config("alerta_atraso_dias", 90)),
            help="Clientes com títulos acima deste prazo entram no alerta crítico")

    if st.button("💾 Salvar configurações", type="primary"):
        # Tenta gravar as 4 configs incondicionalmente (sem short-circuit do
        # "and") — uma falha isolada não deve impedir a tentativa das demais.
        campos = [
            ("Piso mínimo de caixa",              "piso_caixa",            str(novo_piso)),
            ("Capital operacional mínimo",        "alerta_capital_minimo", str(novo_cap)),
            ("Alertar AP vencendo em (horas)",    "alerta_ap_horas",       str(novo_horas)),
            ("Dias de atraso para cliente crítico","alerta_atraso_dias",   str(novo_dias)),
        ]
        falhas = [label for label, chave, valor in campos if not set_config(chave, valor)]
        if not falhas:
            st.success("Configurações salvas! Atualize a página para refletir nos alertas.")
            st.cache_data.clear()
        else:
            # Aponta exatamente qual(is) campo(s) falhou(aram), em vez de um erro genérico.
            st.error("Não foi possível salvar: " + ", ".join(falhas) + ". Tente novamente.")

    st.divider()
    st.markdown("**Valores atuais:**")
    cfg_atual = {
        "Piso mínimo de caixa":        fmt_brl(float(get_config("piso_caixa", 50000))),
        "Capital operacional mínimo":  fmt_brl(float(get_config("alerta_capital_minimo", 100000))),
        "AP — alertar com antecedência": f"{get_config('alerta_ap_horas', 48)}h",
        "Dias para cliente crítico":    f"{get_config('alerta_atraso_dias', 90)} dias",
    }
    for k, v in cfg_atual.items():
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;padding:5px 0;"
            f"border-bottom:1px solid #eee'><span>{k}</span><b>{v}</b></div>",
            unsafe_allow_html=True)
