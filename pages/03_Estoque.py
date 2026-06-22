"""
Módulo Estoque/Produtos — completo
Top Produtos · Estoque Atual · Estoque Parado · Controle Operacional
Curva ABC · Giro por Grupo · Sem Venda · Drill-down · Exportação · Comentários
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import date

from components.bi_icons import inject_bi, bi, section_header, render_alerta_cards
from core.domain.estoque import (
    get_estoque_geral, get_kpis_estoque, get_ultima_venda,
    get_estoque_parado, get_controle_operacional,
    get_curva_abc_estoque, resumo_abc_estoque,
    get_giro_por_grupo, get_top_produtos,
    get_produtos_sem_venda, get_movimentacoes_produto,
)
from core.data.repositories.cadastros_repo import fetch_opcoes_filtros
from core.data.duckdb_store import init_store
from components.sidebar_filtros import render_sidebar
from components.print_btn import render_print_css, render_print_button
from components.metrics import fmt_brl, kpi_card
from components.theme import COR_PRIM, COR_OK, COR_ALERTA, COR_PERIGO
from components.widgets import df_selecionavel, make_widget_comentario, make_toolbar_export

st.set_page_config(page_title="Estoque / Produtos", page_icon="📦", layout="wide")
init_store()
render_print_css()
inject_bi()

COR_ABC_A  = "#1f77b4"
COR_ABC_B  = "#ff7f0e"
COR_ABC_C  = "#2ca02c"
MODULO     = "estoque"

FAIXAS_PARADO = [30, 60, 90, 180, 365]
CORES_PARADO  = {30: COR_OK, 60: COR_ALERTA, 90: COR_ALERTA,
                 180: COR_PERIGO, 365: "#7b1111"}


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════
# _widget_comentario, _toolbar_export e _df_selecionavel: ver components/widgets.py
# (antes duplicados de forma idêntica nas 4 páginas de módulo).
_df_selecionavel = df_selecionavel
_widget_comentario = make_widget_comentario(
    MODULO, placeholder="Ex.: Estoque parado alto — negociar liquidação com fornecedores...")
_toolbar_export = make_toolbar_export(MODULO)


# ══════════════════════════════════════════════════════════════════
#  DIALOG — drill-down Produto → Movimentações
# ══════════════════════════════════════════════════════════════════
@st.dialog("📦 Movimentações do Produto", width="large")
def dialog_movimentacoes():
    """Modal de drill-down: últimas 200 movimentações de estoque do produto clicado (entradas, vendas, ajustes)."""
    ctx = st.session_state.get("dlg_ctx_est", {})
    codprod  = ctx.get("codprod", "")
    descprod = ctx.get("descprod", codprod)
    if not codprod:
        st.error("Produto não identificado."); return

    st.markdown(f"### {descprod}")
    st.caption(f"Código: {codprod} — últimas 200 movimentações")

    df = get_movimentacoes_produto(codprod)
    if df.empty:
        st.info("Nenhuma movimentação encontrada."); return

    # DESC_TIPO já vem traduzido de core.domain.estoque.get_movimentacoes_produto()
    exib = df[["DT_MOVIMENTO", "DESC_TIPO", "TIPOMOV", "QUANTIDADE",
               "CUSTO_UNIT", "VENDA_UNIT", "ESTQ_ANTERIOR"]].copy()
    exib["DT_MOVIMENTO"]  = exib["DT_MOVIMENTO"].dt.strftime("%d/%m/%Y")
    exib["CUSTO_UNIT"]    = exib["CUSTO_UNIT"].apply(fmt_brl)
    exib["VENDA_UNIT"]    = exib["VENDA_UNIT"].apply(fmt_brl)
    exib["ESTQ_ANTERIOR"] = exib["ESTQ_ANTERIOR"].apply(lambda x: f"{x:.0f}")
    exib = exib.drop(columns=["TIPOMOV"])
    exib = exib.rename(columns={
        "DT_MOVIMENTO": "Data", "DESC_TIPO": "Tipo",
        "QUANTIDADE": "Qtd", "CUSTO_UNIT": "Custo unit.",
        "VENDA_UNIT": "Venda unit.", "ESTQ_ANTERIOR": "Estq. ant.",
    })
    st.dataframe(exib, use_container_width=True, hide_index=True, height=420)


# ══════════════════════════════════════════════════════════════════
#  CACHE
# ══════════════════════════════════════════════════════════════════
@st.cache_data(ttl=900, show_spinner="Carregando estoque…")
def _carregar_estoque():
    """Carrega o estoque geral (COMPPROD×PRODUTO×GRUPROD) — base de dados da página inteira."""
    return get_estoque_geral()

@st.cache_data(ttl=900, show_spinner=False)
def _carregar_ult_venda():
    """Carrega a data da última venda de cada produto (para estoque parado e produtos sem venda)."""
    return get_ultima_venda()

@st.cache_data(ttl=3600, show_spinner=False)
def _carregar_opcoes():
    """Carrega as opções de filtro (cadastros) e as deixa em session_state para components.sidebar_filtros usar."""
    opc = fetch_opcoes_filtros()
    st.session_state["opcoes_cadastros"] = opc
    return opc

@st.cache_data(ttl=900, show_spinner=False)
def _carregar_top(data_ini_str, data_fim_str):
    """Carrega o top produtos por quantidade/faturamento/lucro no período (aba Top Produtos)."""
    return get_top_produtos(data_ini_str, data_fim_str)

@st.cache_data(ttl=900, show_spinner=False)
def _carregar_giro(data_ini_str, data_fim_str):
    """Carrega o giro de estoque por grupo de produto no período (aba Giro)."""
    return get_giro_por_grupo(data_ini_str, data_fim_str)


try:
    df_est_raw = _carregar_estoque()
    df_ult_venda = _carregar_ult_venda()
    opcoes = _carregar_opcoes()
except Exception as e:
    st.error(f"Erro ao conectar ao banco: {e}"); st.stop()

# ── Sidebar ──────────────────────────────────────────────────────
filtros = render_sidebar(opcoes)
data_ini: date = filtros["data_ini"]
data_fim: date = filtros["data_fim"]

# Para estoque, o filtro de grupo é local (não via sidebar/aplicar)
# pois o DataFrame não tem colunas padrão de cliente/vendedor
grupos_disponiveis = sorted(df_est_raw["GRUPO"].dropna().unique().tolist())
grupos_sel = st.sidebar.multiselect(
    "Grupo de Produto", grupos_disponiveis,
    default=[], key="filtro_grupo_est",
    placeholder="Todos os grupos")

# Aplica filtro de grupo ao estoque
if grupos_sel:
    df_est = df_est_raw[df_est_raw["GRUPO"].isin(grupos_sel)].copy()
else:
    df_est = df_est_raw.copy()

# ── KPIs e dados derivados ────────────────────────────────────────
kpis = get_kpis_estoque(df_est)
df_parado_90 = get_estoque_parado(90, df_est, df_ult_venda)
df_abc = get_curva_abc_estoque(df_est)
ctrl = get_controle_operacional(df_est)

# ── Cabeçalho ────────────────────────────────────────────────────
col_titulo, col_print = st.columns([9, 1])
with col_titulo:
    st.markdown(
        f"<h1 style='margin:0;display:flex;align-items:center;gap:10px'>"
        f"{bi('estoque',28,'#1f6bb5')} Estoque / Produtos</h1>"
        f"<p style='margin:2px 0 0;color:#888;font-size:0.88em'>"
        f"{bi('calendar3',13,'#888')} Período: "
        f"{data_ini.strftime('%d/%m/%Y')} — {data_fim.strftime('%d/%m/%Y')}</p>",
        unsafe_allow_html=True)
with col_print:
    st.markdown("<div style='margin-top:12px'>", unsafe_allow_html=True)
    render_print_button(key="print_estoque")
    st.markdown("</div>", unsafe_allow_html=True)

# ── KPIs header ──────────────────────────────────────────────────
_fmt_int = lambda v: f"{v:,.0f}".replace(",", ".")
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    kpi_card("Total SKUs", kpis["total_skus"], cor=COR_PRIM, fmt=_fmt_int)
with c2:
    kpi_card("Com Estoque", kpis["skus_com_estoque"], cor=COR_OK, fmt=_fmt_int)
with c3:
    kpi_card("Ruptura", kpis["skus_ruptura"], cor=COR_ALERTA, fmt=_fmt_int)
with c4:
    kpi_card("Abaixo Mínimo", kpis["skus_abaixo_min"],
             cor=COR_PERIGO if kpis["skus_abaixo_min"] > 0 else COR_OK, fmt=_fmt_int)
with c5:
    kpi_card("Valor Custo", kpis["valor_custo"], negativo_ruim=False, cor=COR_PRIM)
with c6:
    kpi_card("Parado 90d", float(df_parado_90["VALOR_CUSTO"].sum()) if not df_parado_90.empty else 0.0,
             cor=COR_ALERTA)

st.divider()

# ── Alertas rápidos ──────────────────────────────────────────────
_alertas = []
_pct_ruptura = kpis["skus_ruptura"] / kpis["total_skus"] * 100 if kpis["total_skus"] > 0 else 0
if kpis["skus_com_estoque"] < 500 and kpis["total_skus"] > 1000:
    _alertas.append({"nivel": "critico", "titulo": "Estoque crítico",
                     "detalhe": f"Apenas {kpis['skus_com_estoque']} SKUs com estoque de {kpis['total_skus']:,} cadastrados"})
if kpis["skus_abaixo_min"] > 0:
    _alertas.append({"nivel": "urgente", "titulo": "Abaixo do mínimo",
                     "detalhe": f"{kpis['skus_abaixo_min']} produtos abaixo do estoque mínimo"})
if not df_parado_90.empty:
    val_p = df_parado_90["VALOR_CUSTO"].sum()
    if val_p > 10000:
        _alertas.append({"nivel": "atencao", "titulo": "Estoque parado (90d)",
                         "detalhe": f"{len(df_parado_90)} SKUs · {fmt_brl(val_p)} imobilizado"})
if _alertas:
    render_alerta_cards(_alertas)
    st.markdown("")

# ══════════════════════════════════════════════════════════════════
#  ABAS
# ══════════════════════════════════════════════════════════════════
aba_top, aba_est, aba_parado, aba_ctrl, aba_abc, aba_giro, aba_cfg = st.tabs([
    "🏆 Top Produtos",
    "📦 Estoque Atual",
    "⏰ Estoque Parado",
    "🚨 Controle",
    "📊 Curva ABC",
    "🔄 Giro por Grupo",
    "⚙️ Configurações",
])


# ══════════════════════════════════════════════════════════════════
#  ABA 1 — TOP PRODUTOS
# ══════════════════════════════════════════════════════════════════
with aba_top:
    st.markdown(section_header("Top Produtos — Período Selecionado", "produto", 4),
                unsafe_allow_html=True)
    st.caption(
        bi("info", 13, "#888") + " Baseado em movimentações de venda PDV (MVGERAL tipo 55) no período filtrado.",
        unsafe_allow_html=True)

    _data_ini_str = data_ini.strftime("%Y-%m-%d")
    _data_fim_str = date.today().strftime("%Y-%m-%d") if data_fim >= date.today() \
        else (pd.Timestamp(data_fim) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    tops = _carregar_top(_data_ini_str, _data_fim_str)

    sub_qtd, sub_fat, sub_lucro = st.tabs([
        "📦 Por Quantidade Vendida",
        "💰 Por Faturamento",
        "📈 Por Lucro Bruto",
    ])

    def _render_top_tab(df_top: pd.DataFrame, col_val: str, label_val: str,
                        col_bar_label: str, key_sfx: str, fmt_fn=fmt_brl):
        """Renderiza o gráfico de barras Top 10 + tabela completa para uma das 3 sub-abas de Top Produtos."""
        if df_top.empty:
            st.info("Sem dados de venda no período selecionado.")
            return
        df = df_top.copy()
        fig = px.bar(
            df.head(10), x=col_val, y="DESCRICAO",
            orientation="h", text=df.head(10)[col_val].apply(fmt_fn),
            color="GRUPO", title=f"Top 10 — {label_val}",
            labels={"DESCRICAO": "Produto", col_val: label_val, "GRUPO": "Grupo"},
            height=420,
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(yaxis={"categoryorder": "total ascending"},
                          legend=dict(orientation="h", yanchor="bottom", y=1.02),
                          margin=dict(l=10, r=20, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True, key=f"chart_top_{key_sfx}")

        st.markdown(section_header(f"Tabela — {label_val}", "itens", 5), unsafe_allow_html=True)
        exib = df[["CODPROD", "DESCRICAO", "GRUPO", "QTD_VENDIDA", "FAT_TOTAL",
                   "CMV", "LUCRO_BRUTO", "MARGEM"]].copy()
        exib["FAT_TOTAL"]   = exib["FAT_TOTAL"].apply(fmt_brl)
        exib["CMV"]         = exib["CMV"].apply(fmt_brl)
        exib["LUCRO_BRUTO"] = exib["LUCRO_BRUTO"].apply(fmt_brl)
        exib["MARGEM"]      = exib["MARGEM"].apply(lambda x: f"{x:.1f}%")
        exib["QTD_VENDIDA"] = exib["QTD_VENDIDA"].apply(lambda x: f"{x:.1f}")
        exib = exib.rename(columns={
            "CODPROD": "Código", "DESCRICAO": "Produto", "GRUPO": "Grupo",
            "QTD_VENDIDA": "Qtd Vendida", "FAT_TOTAL": "Faturamento",
            "CMV": "CMV", "LUCRO_BRUTO": "Lucro Bruto", "MARGEM": "Margem %",
        })

        idx = _df_selecionavel(exib, key=f"top_{key_sfx}")
        if idx is not None:
            prod = df.iloc[idx]
            st.session_state["dlg_ctx_est"] = {
                "codprod": prod["CODPROD"],
                "descprod": prod["DESCRICAO"],
            }
            dialog_movimentacoes()

    with sub_qtd:
        fmt_qtd = lambda x: f"{x:.1f}"
        _render_top_tab(tops.get("por_qtd", pd.DataFrame()),
                        "QTD_VENDIDA", "Quantidade Vendida", "Qtd", "top_qtd",
                        fmt_fn=fmt_qtd)
    with sub_fat:
        _render_top_tab(tops.get("por_fat", pd.DataFrame()),
                        "FAT_TOTAL", "Faturamento (R$)", "Fat", "top_fat")
    with sub_lucro:
        _render_top_tab(tops.get("por_lucro", pd.DataFrame()),
                        "LUCRO_BRUTO", "Lucro Bruto (R$)", "Lucro", "top_lucro")

    st.divider()
    # Sem venda no período
    st.markdown(section_header("Produtos Sem Venda no Período", "busca", 4),
                unsafe_allow_html=True)
    _dias_sv = st.select_slider(
        "Sem venda há quantos dias?", options=FAIXAS_PARADO,
        value=90, key="dias_sem_venda_top",
        format_func=lambda x: f"{x} dias")
    df_sv = get_estoque_parado(_dias_sv, df_est, df_ult_venda)
    if df_sv.empty:
        st.success(f"Nenhum produto com estoque parado há mais de {_dias_sv} dias.")
    else:
        col_sv1, col_sv2, col_sv3 = st.columns(3)
        col_sv1.metric("SKUs parados", len(df_sv))
        col_sv2.metric("Qtd física", f"{df_sv['QTD'].sum():.0f}")
        col_sv3.metric("Valor custo", fmt_brl(df_sv["VALOR_CUSTO"].sum()))

        sv_exib = df_sv[["CODPROD", "DESCRICAO", "GRUPO", "QTD", "CUSTO_UNIT",
                          "VALOR_CUSTO", "ULT_VENDA", "DIAS_PARADO"]].head(50).copy()
        sv_exib["ULT_VENDA"]  = sv_exib["ULT_VENDA"].dt.strftime("%d/%m/%Y").fillna("Nunca vendeu")
        sv_exib["CUSTO_UNIT"] = sv_exib["CUSTO_UNIT"].apply(fmt_brl)
        sv_exib["VALOR_CUSTO"]= sv_exib["VALOR_CUSTO"].apply(fmt_brl)
        sv_exib["QTD"]        = sv_exib["QTD"].apply(lambda x: f"{x:.1f}")
        sv_exib = sv_exib.rename(columns={
            "CODPROD": "Código", "DESCRICAO": "Produto", "GRUPO": "Grupo",
            "QTD": "Qtd", "CUSTO_UNIT": "Custo unit.", "VALOR_CUSTO": "Valor custo",
            "ULT_VENDA": "Última venda", "DIAS_PARADO": "Dias parado",
        })
        idx_sv = _df_selecionavel(sv_exib, key="sv_top_tbl", height=340)
        if idx_sv is not None:
            prod_sv = df_sv.iloc[idx_sv]
            st.session_state["dlg_ctx_est"] = {
                "codprod": prod_sv["CODPROD"],
                "descprod": prod_sv["DESCRICAO"],
            }
            dialog_movimentacoes()

    _toolbar_export(
        "Top Produtos",
        {"Top Qtd": tops.get("por_qtd", pd.DataFrame()),
         "Top Faturamento": tops.get("por_fat", pd.DataFrame()),
         "Top Lucro": tops.get("por_lucro", pd.DataFrame()),
         "Sem Venda": df_sv},
        {"Período": f"{data_ini} a {data_fim}"},
        data_ini, data_fim, "top_produtos")
    _widget_comentario("top_produtos", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 2 — ESTOQUE ATUAL
# ══════════════════════════════════════════════════════════════════
with aba_est:
    st.markdown(section_header("Posição de Estoque Atual", "estoque", 4),
                unsafe_allow_html=True)

    # Distribuição por grupo (gráfico)
    if not df_est.empty:
        df_com = df_est[df_est["QTD"] > 0].copy()
        if not df_com.empty:
            grp_val = (
                df_com.groupby("GRUPO")
                .agg(VALOR=("VALOR_CUSTO", "sum"), SKUS=("CODPROD", "count"))
                .reset_index()
                .sort_values("VALOR", ascending=False)
            )
            total_val = grp_val["VALOR"].sum()

            col_pie, col_bar = st.columns([1, 2])
            with col_pie:
                fig_pie = px.pie(
                    grp_val.head(12), names="GRUPO", values="VALOR",
                    title="Valor de Custo por Grupo",
                    color_discrete_sequence=px.colors.qualitative.Set3,
                    hole=0.4,
                )
                fig_pie.update_traces(textposition="inside", textinfo="percent+label")
                fig_pie.update_layout(showlegend=False, margin=dict(l=5, r=5, t=40, b=5), height=380)
                st.plotly_chart(fig_pie, use_container_width=True)

            with col_bar:
                grp_top = grp_val.head(15).copy()
                grp_top["PERC"] = grp_top["VALOR"] / total_val * 100
                grp_top["LABEL"] = grp_top["VALOR"].apply(fmt_brl)
                fig_bar = px.bar(
                    grp_top, x="VALOR", y="GRUPO", orientation="h",
                    text="LABEL", title="Valor de Estoque por Grupo (Top 15)",
                    labels={"VALOR": "Valor (R$)", "GRUPO": "Grupo"},
                    color="PERC", color_continuous_scale="Blues",
                    height=380,
                )
                fig_bar.update_traces(textposition="outside")
                fig_bar.update_layout(yaxis={"categoryorder": "total ascending"},
                                       coloraxis_showscale=False,
                                       margin=dict(l=10, r=80, t=40, b=10))
                st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown(section_header("Tabela de Produtos — Estoque Atual", "itens", 5),
                unsafe_allow_html=True)

    # Filtro rápido de situação
    sit_op = st.radio(
        "Mostrar:", ["Com estoque", "Em ruptura", "Todos"],
        horizontal=True, key="sit_estoque",
    )
    df_tbl = df_est.copy()
    if sit_op == "Com estoque":
        df_tbl = df_tbl[df_tbl["QTD"] > 0]
    elif sit_op == "Em ruptura":
        df_tbl = df_tbl[df_tbl["QTD"] <= 0]

    if df_tbl.empty:
        st.info("Nenhum produto encontrado.")
    else:
        exib = df_tbl[["CODPROD", "DESCRICAO", "GRUPO", "QTD", "CUSTO_UNIT",
                        "VENDA_UNIT", "VALOR_CUSTO", "VALOR_VENDA",
                        "EST_MINIMO", "EST_MAXIMO"]].copy()
        exib["CUSTO_UNIT"]  = exib["CUSTO_UNIT"].apply(fmt_brl)
        exib["VENDA_UNIT"]  = exib["VENDA_UNIT"].apply(lambda x: fmt_brl(x) if x > 0 else "—")
        exib["VALOR_CUSTO"] = exib["VALOR_CUSTO"].apply(fmt_brl)
        exib["VALOR_VENDA"] = exib["VALOR_VENDA"].apply(lambda x: fmt_brl(x) if x > 0 else "—")
        exib["QTD"]         = exib["QTD"].apply(lambda x: f"{x:.1f}")
        exib["EST_MINIMO"]  = exib["EST_MINIMO"].apply(lambda x: f"{x:.1f}" if x > 0 else "—")
        exib["EST_MAXIMO"]  = exib["EST_MAXIMO"].apply(lambda x: f"{x:.1f}" if x > 0 else "—")
        exib = exib.rename(columns={
            "CODPROD": "Código", "DESCRICAO": "Produto", "GRUPO": "Grupo",
            "QTD": "Qtd", "CUSTO_UNIT": "Custo unit.", "VENDA_UNIT": "Venda unit.",
            "VALOR_CUSTO": "Valor custo", "VALOR_VENDA": "Valor venda",
            "EST_MINIMO": "Mínimo", "EST_MAXIMO": "Máximo",
        })
        idx_est = _df_selecionavel(exib, key="tbl_est_atual", height=420)
        if idx_est is not None:
            prod = df_tbl.iloc[idx_est]
            st.session_state["dlg_ctx_est"] = {
                "codprod": prod["CODPROD"],
                "descprod": prod["DESCRICAO"],
            }
            dialog_movimentacoes()

    st.caption(
        bi("info", 13, "#888") + f" {len(df_tbl):,} produtos exibidos. "
        f"Clique em uma linha para ver as movimentações.",
        unsafe_allow_html=True)

    st.divider()
    _toolbar_export(
        "Estoque Atual",
        {"Estoque": df_tbl},
        {"Total SKUs": str(kpis["total_skus"]),
         "Com estoque": str(kpis["skus_com_estoque"]),
         "Ruptura": str(kpis["skus_ruptura"]),
         "Valor custo": fmt_brl(kpis["valor_custo"])},
        data_ini, data_fim, "estoque_atual")
    _widget_comentario("estoque_atual", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 3 — ESTOQUE PARADO
# ══════════════════════════════════════════════════════════════════
with aba_parado:
    st.markdown(section_header("Estoque Parado — Produtos sem Venda", "estoque", 4),
                unsafe_allow_html=True)
    st.caption(
        bi("info", 13, "#888") + " Produto com estoque > 0 sem nenhuma venda PDV (MVGERAL tipo 55) no período.",
        unsafe_allow_html=True)

    # KPIs por faixa
    faixa_cols = st.columns(len(FAIXAS_PARADO))
    for i, dias in enumerate(FAIXAS_PARADO):
        df_f = get_estoque_parado(dias, df_est, df_ult_venda)
        with faixa_cols[i]:
            cor = CORES_PARADO[dias]
            st.markdown(
                f"<div style='text-align:center;padding:12px 8px;border-radius:8px;"
                f"background:#f8f9fa;border-top:4px solid {cor}'>"
                f"<div style='font-size:0.78em;color:#666;margin-bottom:4px'>"
                f"Parado &gt; {dias}d</div>"
                f"<div style='font-size:1.3em;font-weight:700;color:{cor}'>{len(df_f)}</div>"
                f"<div style='font-size:0.75em;color:#444'>SKUs</div>"
                f"<div style='font-size:0.85em;font-weight:600;margin-top:4px'>"
                f"{fmt_brl(df_f['VALOR_CUSTO'].sum() if not df_f.empty else 0)}</div>"
                f"</div>",
                unsafe_allow_html=True)

    st.markdown("")
    _dias_p = st.select_slider(
        "Analisar produtos parados há mais de:", options=FAIXAS_PARADO,
        value=90, key="dias_parado_sel",
        format_func=lambda x: f"{x} dias")

    df_parado = get_estoque_parado(_dias_p, df_est, df_ult_venda)

    if df_parado.empty:
        st.success(f"Nenhum produto com estoque parado há mais de {_dias_p} dias.")
    else:
        df_nunca = get_produtos_sem_venda(df_est, df_ult_venda)
        col_p1, col_p2, col_p3, col_p4, col_p5 = st.columns(5)
        col_p1.metric("SKUs parados", len(df_parado))
        col_p2.metric("Qtd física total", f"{df_parado['QTD'].sum():.0f}")
        col_p3.metric("Valor custo", fmt_brl(df_parado["VALOR_CUSTO"].sum()))
        pct_par = df_parado["VALOR_CUSTO"].sum() / kpis["valor_custo"] * 100 \
            if kpis["valor_custo"] > 0 else 0
        col_p4.metric("% do estoque total", f"{pct_par:.1f}%")
        col_p5.metric("Nunca venderam", len(df_nunca),
                      help="Produtos com estoque que nunca tiveram nenhuma venda PDV registrada — subconjunto dos parados.")

        # Gráfico por grupo
        grp_par = (
            df_parado.groupby("GRUPO")
            .agg(SKUS=("CODPROD", "count"), VALOR=("VALOR_CUSTO", "sum"))
            .reset_index()
            .sort_values("VALOR", ascending=False)
            .head(15)
        )
        fig_par = px.bar(
            grp_par, x="VALOR", y="GRUPO", orientation="h",
            text=grp_par["VALOR"].apply(fmt_brl),
            title=f"Estoque Parado por Grupo (>{_dias_p} dias)",
            labels={"VALOR": "Valor custo (R$)", "GRUPO": "Grupo"},
            color="VALOR", color_continuous_scale="Reds",
            height=350,
        )
        fig_par.update_traces(textposition="outside")
        fig_par.update_layout(yaxis={"categoryorder": "total ascending"},
                               coloraxis_showscale=False,
                               margin=dict(l=10, r=80, t=40, b=10))
        st.plotly_chart(fig_par, use_container_width=True)

        # Tabela drill-down
        st.markdown(section_header("Produtos Parados — Detalhamento", "itens", 5),
                    unsafe_allow_html=True)
        st.caption(bi("clique", 13, "#888") + " Clique em um produto para ver o histórico de movimentações.",
                   unsafe_allow_html=True)

        p_exib = df_parado[["CODPROD", "DESCRICAO", "GRUPO", "QTD", "CUSTO_UNIT",
                              "VALOR_CUSTO", "ULT_VENDA", "DIAS_PARADO"]].copy()
        p_exib["ULT_VENDA"]  = p_exib["ULT_VENDA"].dt.strftime("%d/%m/%Y").fillna("Nunca vendeu")
        p_exib["CUSTO_UNIT"] = p_exib["CUSTO_UNIT"].apply(fmt_brl)
        p_exib["VALOR_CUSTO"]= p_exib["VALOR_CUSTO"].apply(fmt_brl)
        p_exib["QTD"]        = p_exib["QTD"].apply(lambda x: f"{x:.1f}")
        p_exib = p_exib.rename(columns={
            "CODPROD": "Código", "DESCRICAO": "Produto", "GRUPO": "Grupo",
            "QTD": "Qtd", "CUSTO_UNIT": "Custo unit.", "VALOR_CUSTO": "Valor custo",
            "ULT_VENDA": "Última venda", "DIAS_PARADO": "Dias parado",
        })
        idx_p = _df_selecionavel(p_exib, key="tbl_parado", height=400)
        if idx_p is not None:
            prod_p = df_parado.iloc[idx_p]
            st.session_state["dlg_ctx_est"] = {
                "codprod": prod_p["CODPROD"],
                "descprod": prod_p["DESCRICAO"],
            }
            dialog_movimentacoes()

    st.divider()
    _toolbar_export(
        f"Estoque Parado {_dias_p}d",
        {f"Parado >{_dias_p}d": df_parado},
        {"SKUs parados": str(len(df_parado)) if not df_parado.empty else "0",
         "Valor imobilizado": fmt_brl(df_parado["VALOR_CUSTO"].sum() if not df_parado.empty else 0)},
        data_ini, data_fim, "estoque_parado")
    _widget_comentario("estoque_parado", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 4 — CONTROLE OPERACIONAL
# ══════════════════════════════════════════════════════════════════
with aba_ctrl:
    st.markdown(section_header("Controle Operacional de Estoque", "alertas", 4),
                unsafe_allow_html=True)

    sub_ruptura, sub_minimo = st.tabs(["🔴 Ruptura (sem estoque)", "🟡 Abaixo do Mínimo"])

    with sub_ruptura:
        df_rupt = ctrl["ruptura"]
        if df_rupt.empty:
            st.success("Nenhum produto ativo em situação de ruptura.")
        else:
            st.warning(f"**{len(df_rupt)}** produtos ativos sem estoque (ruptura).")
            r_exib = df_rupt[["CODPROD", "DESCRICAO", "GRUPO", "QTD",
                               "EST_MINIMO", "DT_ULT_ENTRADA"]].copy()
            r_exib["DT_ULT_ENTRADA"] = r_exib["DT_ULT_ENTRADA"].dt.strftime("%d/%m/%Y").fillna("—")
            r_exib["EST_MINIMO"]     = r_exib["EST_MINIMO"].apply(lambda x: f"{x:.1f}" if x > 0 else "—")
            r_exib["QTD"]            = r_exib["QTD"].apply(lambda x: f"{x:.1f}")
            r_exib = r_exib.rename(columns={
                "CODPROD": "Código", "DESCRICAO": "Produto", "GRUPO": "Grupo",
                "QTD": "Estoque", "EST_MINIMO": "Mínimo", "DT_ULT_ENTRADA": "Última entrada",
            })
            idx_r = _df_selecionavel(r_exib, key="tbl_ruptura", height=400)
            if idx_r is not None:
                prod_r = df_rupt.iloc[idx_r]
                st.session_state["dlg_ctx_est"] = {
                    "codprod": prod_r["CODPROD"],
                    "descprod": prod_r["DESCRICAO"],
                }
                dialog_movimentacoes()

        _toolbar_export(
            "Ruptura de Estoque",
            {"Ruptura": df_rupt},
            {"Produtos em ruptura": str(len(df_rupt))},
            data_ini, data_fim, "ruptura")
        _widget_comentario("ruptura", data_ini, data_fim)

    with sub_minimo:
        df_abx = ctrl["abaixo_minimo"]
        if df_abx.empty:
            st.success("Nenhum produto abaixo do estoque mínimo configurado.")
        else:
            st.warning(f"**{len(df_abx)}** produtos abaixo do estoque mínimo.")
            a_exib = df_abx[["CODPROD", "DESCRICAO", "GRUPO", "QTD",
                              "EST_MINIMO", "DEFICIT", "CUSTO_UNIT"]].copy()
            a_exib["VALOR_REPOR"] = a_exib["DEFICIT"] * a_exib["CUSTO_UNIT"]
            a_exib["CUSTO_UNIT"]  = a_exib["CUSTO_UNIT"].apply(fmt_brl)
            a_exib["VALOR_REPOR"] = a_exib["VALOR_REPOR"].apply(fmt_brl)
            a_exib["QTD"]         = a_exib["QTD"].apply(lambda x: f"{x:.1f}")
            a_exib["EST_MINIMO"]  = a_exib["EST_MINIMO"].apply(lambda x: f"{x:.1f}")
            a_exib["DEFICIT"]     = a_exib["DEFICIT"].apply(lambda x: f"{x:.1f}")
            a_exib = a_exib.drop(columns=["CUSTO_UNIT"])
            a_exib = a_exib.rename(columns={
                "CODPROD": "Código", "DESCRICAO": "Produto", "GRUPO": "Grupo",
                "QTD": "Estoque", "EST_MINIMO": "Mínimo", "DEFICIT": "Déficit",
                "VALOR_REPOR": "Custo p/ repor",
            })
            idx_a = _df_selecionavel(a_exib, key="tbl_abaixo", height=400)
            if idx_a is not None:
                prod_a = df_abx.iloc[idx_a]
                st.session_state["dlg_ctx_est"] = {
                    "codprod": prod_a["CODPROD"],
                    "descprod": prod_a["DESCRICAO"],
                }
                dialog_movimentacoes()

        _toolbar_export(
            "Abaixo do Mínimo",
            {"Abaixo do Mínimo": df_abx},
            {"Produtos abaixo do mínimo": str(len(df_abx))},
            data_ini, data_fim, "abaixo_minimo")
        _widget_comentario("abaixo_minimo", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 5 — CURVA ABC
# ══════════════════════════════════════════════════════════════════
with aba_abc:
    st.markdown(section_header("Curva ABC — Valor de Estoque", "estoque", 4),
                unsafe_allow_html=True)
    st.caption(
        bi("info", 13, "#888") + " Classificação pelo valor de custo investido: "
        "A = 80% do valor, B = 80–95%, C = 95–100%.",
        unsafe_allow_html=True)

    if df_abc.empty:
        st.info("Sem dados para gerar a curva ABC.")
    else:
        resumo = resumo_abc_estoque(df_abc)

        # Cards por classe
        c_a, c_b, c_c = st.columns(3)
        for col_abc, cls, cor in [(c_a, "A", COR_ABC_A), (c_b, "B", COR_ABC_B), (c_c, "C", COR_ABC_C)]:
            r = resumo[resumo["CLASSE"] == cls]
            if r.empty:
                continue
            skus  = int(r["SKUS"].iloc[0])
            valor = float(r["VALOR"].iloc[0])
            perc  = float(r["PERC"].iloc[0])
            with col_abc:
                st.markdown(
                    f"<div style='text-align:center;padding:16px;border-radius:10px;"
                    f"background:#f0f4ff;border-top:5px solid {cor}'>"
                    f"<div style='font-size:1.8em;font-weight:800;color:{cor}'>Classe {cls}</div>"
                    f"<div style='font-size:1.1em;font-weight:700;margin-top:4px'>{skus:,} SKUs</div>"
                    f"<div style='font-size:0.9em;color:#555'>{fmt_brl(valor)}</div>"
                    f"<div style='font-size:0.85em;color:#888'>{perc:.1f}% do valor total</div>"
                    f"</div>",
                    unsafe_allow_html=True)

        st.markdown("")

        # Curva ABC gráfico
        fig_abc = go.Figure()
        cores_abc = {"A": COR_ABC_A, "B": COR_ABC_B, "C": COR_ABC_C}
        for cls in ["A", "B", "C"]:
            sub = df_abc[df_abc["CLASSE"] == cls]
            fig_abc.add_trace(go.Bar(
                x=list(range(len(sub))),
                y=sub["VALOR_CUSTO"].tolist(),
                name=f"Classe {cls}",
                marker_color=cores_abc[cls],
            ))
        fig_abc.add_trace(go.Scatter(
            x=list(range(len(df_abc))),
            y=df_abc["ACUMULADO"].tolist(),
            name="% Acumulado", yaxis="y2",
            line=dict(color="#d62728", width=2),
            mode="lines",
        ))
        fig_abc.update_layout(
            title="Distribuição de Valor — Curva ABC",
            xaxis_title="Produtos (ordenados por valor)", yaxis_title="Valor custo (R$)",
            yaxis2=dict(title="% Acumulado", overlaying="y", side="right",
                        range=[0, 110], tickformat=".0f"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=420, margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(fig_abc, use_container_width=True)

        # Tabela
        st.markdown(section_header("Detalhamento por Produto", "itens", 5), unsafe_allow_html=True)
        _filtro_abc = st.multiselect("Filtrar por classe:", ["A", "B", "C"], default=["A", "B"],
                                     key="filtro_abc_cls")
        df_abc_fil = df_abc[df_abc["CLASSE"].isin(_filtro_abc)] if _filtro_abc else df_abc

        abc_exib = df_abc_fil[["CODPROD", "DESCRICAO", "GRUPO", "QTD",
                                "CUSTO_UNIT", "VALOR_CUSTO", "PERC", "ACUMULADO", "CLASSE"]].copy()
        abc_exib["CUSTO_UNIT"]  = abc_exib["CUSTO_UNIT"].apply(fmt_brl)
        abc_exib["VALOR_CUSTO"] = abc_exib["VALOR_CUSTO"].apply(fmt_brl)
        abc_exib["PERC"]        = abc_exib["PERC"].apply(lambda x: f"{x:.2f}%")
        abc_exib["ACUMULADO"]   = abc_exib["ACUMULADO"].apply(lambda x: f"{x:.1f}%")
        abc_exib["QTD"]         = abc_exib["QTD"].apply(lambda x: f"{x:.1f}")
        abc_exib = abc_exib.rename(columns={
            "CODPROD": "Código", "DESCRICAO": "Produto", "GRUPO": "Grupo",
            "QTD": "Qtd", "CUSTO_UNIT": "Custo unit.", "VALOR_CUSTO": "Valor custo",
            "PERC": "% do total", "ACUMULADO": "% Acumulado", "CLASSE": "Classe",
        })
        idx_abc = _df_selecionavel(abc_exib, key="tbl_abc", height=380)
        if idx_abc is not None:
            prod_abc = df_abc_fil.iloc[idx_abc]
            st.session_state["dlg_ctx_est"] = {
                "codprod": prod_abc["CODPROD"],
                "descprod": prod_abc["DESCRICAO"],
            }
            dialog_movimentacoes()

    st.divider()
    _toolbar_export(
        "Curva ABC Estoque",
        {"ABC": df_abc, "Resumo ABC": resumo_abc_estoque(df_abc)},
        {"Classe A": str(len(df_abc[df_abc["CLASSE"] == "A"])) if not df_abc.empty else "0",
         "Classe B": str(len(df_abc[df_abc["CLASSE"] == "B"])) if not df_abc.empty else "0",
         "Classe C": str(len(df_abc[df_abc["CLASSE"] == "C"])) if not df_abc.empty else "0"},
        data_ini, data_fim, "curva_abc")
    _widget_comentario("curva_abc", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 6 — GIRO POR GRUPO
# ══════════════════════════════════════════════════════════════════
with aba_giro:
    st.markdown(section_header("Giro de Estoque por Grupo", "fluxo", 4),
                unsafe_allow_html=True)
    st.caption(
        bi("info", 13, "#888") + " Giro = Valor Vendido no período / Valor em Estoque (snapshot atual). "
        "Giro > 1 indica rotatividade saudável.",
        unsafe_allow_html=True)

    _g_ini = data_ini.strftime("%Y-%m-%d")
    _g_fim = (pd.Timestamp(data_fim) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    df_giro = _carregar_giro(_g_ini, _g_fim)

    if df_giro.empty:
        st.info("Sem dados de giro para o período selecionado.")
    else:
        # Gráfico giro
        df_g = df_giro[df_giro["VALOR_ESTOQUE"] > 0].copy()
        df_g["COR"] = df_g["GIRO"].apply(
            lambda x: COR_OK if x >= 1 else (COR_ALERTA if x >= 0.5 else COR_PERIGO))

        fig_giro = go.Figure(go.Bar(
            x=df_g["GIRO"], y=df_g["GRUPO"],
            orientation="h",
            text=df_g["GIRO"].apply(lambda x: f"{x:.2f}x"),
            textposition="outside",
            marker_color=df_g["COR"].tolist(),
        ))
        fig_giro.add_vline(x=1.0, line_dash="dash", line_color="#666",
                           annotation_text="Giro = 1x", annotation_position="top right")
        fig_giro.update_layout(
            title="Giro de Estoque por Grupo de Produtos",
            xaxis_title="Giro (vezes)", yaxis_title="",
            yaxis={"categoryorder": "total ascending"},
            height=max(350, len(df_g) * 35 + 80),
            margin=dict(l=10, r=100, t=50, b=10),
        )
        st.plotly_chart(fig_giro, use_container_width=True)

        # Tabela
        g_exib = df_giro.copy()
        g_exib["VALOR_ESTOQUE"]  = g_exib["VALOR_ESTOQUE"].apply(fmt_brl)
        g_exib["FAT_VENDIDO"]    = g_exib["FAT_VENDIDO"].apply(fmt_brl)
        g_exib["GIRO"]           = g_exib["GIRO"].apply(lambda x: f"{x:.2f}x")
        g_exib = g_exib.rename(columns={
            "GRUPO": "Grupo", "QTD_SKUS": "SKUs",
            "VALOR_ESTOQUE": "Valor em estoque", "FAT_VENDIDO": "Faturado no período",
            "GIRO": "Giro",
        })
        g_exib = g_exib.drop(columns=["CODGRUPO"], errors="ignore")
        st.dataframe(g_exib, use_container_width=True, hide_index=True, height=360)

        st.markdown("")
        st.markdown(
            f"<small style='color:#666'>"
            f"{bi('info',13,'#888')} Giro calculado com base no faturamento PDV (MVGERAL tipo 55) "
            f"de {data_ini.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}.</small>",
            unsafe_allow_html=True)

    st.divider()
    _toolbar_export(
        "Giro de Estoque",
        {"Giro por Grupo": df_giro},
        {"Período": f"{data_ini} a {data_fim}"},
        data_ini, data_fim, "giro_estoque")
    _widget_comentario("giro_estoque", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 7 — CONFIGURAÇÕES / COMENTÁRIOS
# ══════════════════════════════════════════════════════════════════
with aba_cfg:
    st.markdown(section_header("Configurações e Notas Gerais", "config", 4),
                unsafe_allow_html=True)
    _widget_comentario("geral_estoque", data_ini, data_fim)

    st.divider()
    st.markdown("#### Informações do Módulo")
    col_i1, col_i2 = st.columns(2)
    with col_i1:
        st.markdown(
            f"- **Fonte de estoque:** COMPPROD (empresa 00)\n"
            f"- **Movimentações:** MVGERAL (tipo 55 = venda, 01 = entrada)\n"
            f"- **Produtos:** {kpis['total_skus']:,} cadastrados\n"
            f"- **Com estoque:** {kpis['skus_com_estoque']:,} SKUs\n"
            f"- **Em ruptura:** {kpis['skus_ruptura']:,} SKUs")
    with col_i2:
        st.markdown(
            f"- **Valor custo total:** {fmt_brl(kpis['valor_custo'])}\n"
            f"- **Valor de venda total:** {fmt_brl(kpis['valor_venda'])} (PRODUTO.PRECO)\n"
            f"- **Curva ABC:** por valor investido (custo × qtd)\n"
            f"- **Giro:** faturamento PDV / valor em estoque (snapshot)\n"
            f"- **Estoque mínimo:** base para alertas de reposição")
