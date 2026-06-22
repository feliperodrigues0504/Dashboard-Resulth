"""
Módulo Compras — completo
Evolução de Compras · Top Fornecedores · Dependência · Rentabilidade
Alertas (sem giro + estoque parado) · Drill-down Fornecedor→NF→Itens
Exportação · Impressão · Comentários gerenciais
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import date

from components.bi_icons import inject_bi, bi, section_header
from core.domain.compras import (
    get_historico_compras, get_compras_por_fornecedor,
    get_nfs_fornecedor, get_itens_nf_entrada,
    get_rentabilidade_fornecedor, get_produtos_sem_giro,
    get_estoque_parado_por_fornecedor, get_kpis_compras,
    get_relprfo, get_estoque_prod,
)
from core.data.repositories.cadastros_repo import fetch_opcoes_filtros
from core.data.duckdb_store import init_store
from components.sidebar_filtros import render_sidebar
from components.print_btn import render_print_css, render_print_button
from components.metrics import fmt_brl, kpi_card
from components.theme import COR_PRIM, COR_OK, COR_ALERTA, COR_PERIGO
from components.widgets import df_selecionavel, make_widget_comentario, make_toolbar_export

st.set_page_config(page_title="Compras", page_icon="🛒", layout="wide")
init_store()
render_print_css()
inject_bi()

MODULO     = "compras"


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════
# _widget_comentario, _toolbar_export e _df_selecionavel: ver components/widgets.py
# (antes duplicados de forma idêntica nas 4 páginas de módulo).
_df_selecionavel = df_selecionavel
_widget_comentario = make_widget_comentario(
    MODULO, placeholder="Ex.: Aumento de compras de cabos por demanda de projetos...")
_toolbar_export = make_toolbar_export(MODULO)


# ══════════════════════════════════════════════════════════════════
#  DIALOG — Drill-down Fornecedor → NFs → Itens
# ══════════════════════════════════════════════════════════════════
@st.dialog("🏭 Compras do Fornecedor", width="large")
def dialog_fornecedor():
    """Modal de drill-down: NFs de entrada do fornecedor clicado no período, com itens ao selecionar uma NF."""
    ctx       = st.session_state.get("dlg_ctx_cmp", {})
    codfornec = ctx.get("codfornec", "")
    nome      = ctx.get("nome", codfornec)
    data_ini  = ctx.get("data_ini", "2026-01-01")
    data_fim  = ctx.get("data_fim", "2026-12-31")

    if not codfornec:
        st.error("Fornecedor não identificado."); return

    st.markdown(f"### {nome}")
    st.caption(f"Código: {codfornec} · Período: {data_ini} a {data_fim}")

    nfs = get_nfs_fornecedor(codfornec, data_ini, data_fim)
    if nfs.empty:
        st.info("Nenhuma NF de entrada encontrada no período."); return

    nf_exib = nfs[["NUMERONF", "DT_ENTRADA", "DT_EMISSAO", "TOTAL_NF"]].copy()
    nf_exib["DT_ENTRADA"] = nf_exib["DT_ENTRADA"].dt.strftime("%d/%m/%Y")
    nf_exib["DT_EMISSAO"] = nf_exib["DT_EMISSAO"].dt.strftime("%d/%m/%Y")
    nf_exib["TOTAL_NF"]   = nf_exib["TOTAL_NF"].apply(fmt_brl)
    nf_exib = nf_exib.rename(columns={
        "NUMERONF": "Nº NF", "DT_ENTRADA": "Entrada",
        "DT_EMISSAO": "Emissão", "TOTAL_NF": "Total",
    })

    idx = _df_selecionavel(nf_exib, key="dlg_cmp_nfs", height=280)
    if idx is not None:
        nf = nfs.iloc[idx]
        st.markdown("---")
        st.markdown(
            section_header(f"Itens da NF {nf['NUMERONF']} — {nf['DT_ENTRADA'].strftime('%d/%m/%Y')} — {fmt_brl(nf['TOTAL_NF'])}",
                           "itens", level=5),
            unsafe_allow_html=True)
        itens = get_itens_nf_entrada(codfornec, nf["NUMERONF"])
        if itens.empty:
            st.info("Sem itens para esta NF.")
        else:
            it = itens.copy()
            it["CUSTO_UNIT"] = it["CUSTO_UNIT"].apply(fmt_brl)
            it["DESCONTO"]   = it["DESCONTO"].apply(fmt_brl)
            it["TOTAL_ITEM"] = it["TOTAL_ITEM"].apply(fmt_brl)
            it["QUANTIDADE"] = it["QUANTIDADE"].apply(lambda x: f"{x:.2f}")
            it = it.rename(columns={
                "CODPROD": "Código", "PRODUTO": "Produto", "GRUPO": "Grupo",
                "QUANTIDADE": "Qtd", "CUSTO_UNIT": "Custo unit.",
                "DESCONTO": "Desconto", "TOTAL_ITEM": "Total",
            })
            st.dataframe(it, use_container_width=True, hide_index=True, height=320)


# ══════════════════════════════════════════════════════════════════
#  CACHE
# ══════════════════════════════════════════════════════════════════
@st.cache_data(ttl=1800, show_spinner="Carregando histórico de compras…")
def _carregar_historico():
    """Carrega as compras mensais dos últimos 13 meses (aba Histórico)."""
    return get_historico_compras(13)

@st.cache_data(ttl=900, show_spinner=False)
def _carregar_fornecedores(ini, fim):
    """Carrega as compras agregadas por fornecedor no período — base de dados da página inteira."""
    return get_compras_por_fornecedor(ini, fim)

# RELPRFO e estoque-por-produto são buscados 1x por carga de página (TTL 30min,
# tabelas pequenas e estáveis) e compartilhados entre as 3 funções abaixo —
# em vez de cada uma refazer a mesma busca completa de RELPRFO/COMPPROD.
@st.cache_data(ttl=1800, show_spinner=False)
def _carregar_relprfo():
    """Carrega a relação produto-fornecedor (RELPRFO) completa, compartilhada entre rentabilidade/sem-giro/parado."""
    return get_relprfo()

@st.cache_data(ttl=1800, show_spinner=False)
def _carregar_estoque_prod():
    """Carrega o estoque atual por produto (COMPPROD), compartilhado entre rentabilidade/sem-giro."""
    return get_estoque_prod()

@st.cache_data(ttl=900, show_spinner=False)
def _carregar_rentabilidade(ini, fim, df_relprfo, df_estoque):
    """Carrega a rentabilidade por fornecedor no período (aba Rentabilidade)."""
    return get_rentabilidade_fornecedor(ini, fim, df_relprfo, df_estoque)

@st.cache_data(ttl=900, show_spinner=False)
def _carregar_sem_giro(ini, fim, df_relprfo, df_estoque):
    """Carrega os produtos comprados sem nenhuma venda no período (aba Sem Giro)."""
    return get_produtos_sem_giro(ini, fim, df_relprfo, df_estoque)

@st.cache_data(ttl=900, show_spinner=False)
def _carregar_parado_forn(dias, df_relprfo):
    """Carrega o estoque parado agrupado por fornecedor principal (aba Estoque Parado)."""
    return get_estoque_parado_por_fornecedor(dias, df_relprfo)

@st.cache_data(ttl=3600, show_spinner=False)
def _carregar_opcoes():
    """Carrega as opções de filtro (cadastros) e as deixa em session_state para components.sidebar_filtros usar."""
    opc = fetch_opcoes_filtros()
    st.session_state["opcoes_cadastros"] = opc
    return opc


try:
    df_hist  = _carregar_historico()
    opcoes   = _carregar_opcoes()
except Exception as e:
    st.error(f"Erro ao conectar ao banco: {e}"); st.stop()

# ── Sidebar ──────────────────────────────────────────────────────
filtros  = render_sidebar(opcoes)
data_ini: date = filtros["data_ini"]
data_fim: date = filtros["data_fim"]

_ini_str = data_ini.strftime("%Y-%m-%d")
_fim_str = (pd.Timestamp(data_fim) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

# ── Dados do período ──────────────────────────────────────────────
# RELPRFO e estoque-por-produto: 1 busca cada, compartilhada pelas 3 abas
# que precisam deles (Rentabilidade, Sem Giro, Parado por Fornecedor).
_df_relprfo_shared = _carregar_relprfo()
_df_estoque_shared = _carregar_estoque_prod()

kpis         = get_kpis_compras(_ini_str, _fim_str)
df_forn      = _carregar_fornecedores(_ini_str, _fim_str)
df_rent      = _carregar_rentabilidade(_ini_str, _fim_str, _df_relprfo_shared, _df_estoque_shared)

# ── Cabeçalho ────────────────────────────────────────────────────
col_titulo, col_print = st.columns([9, 1])
with col_titulo:
    st.markdown(
        f"<h1 style='margin:0;display:flex;align-items:center;gap:10px'>"
        f"{bi('compras',28,'#1f6bb5')} Compras</h1>"
        f"<p style='margin:2px 0 0;color:#888;font-size:0.88em'>"
        f"{bi('calendar3',13,'#888')} Período: "
        f"{data_ini.strftime('%d/%m/%Y')} — {data_fim.strftime('%d/%m/%Y')}</p>",
        unsafe_allow_html=True)
with col_print:
    st.markdown("<div style='margin-top:12px'>", unsafe_allow_html=True)
    render_print_button(key="print_compras")
    st.markdown("</div>", unsafe_allow_html=True)

# ── KPIs header ──────────────────────────────────────────────────
_fmt_int = lambda v: f"{v:,.0f}".replace(",", ".")
c1, c2, c3, c4 = st.columns(4)
with c1:
    kpi_card("Total Comprado", kpis["total_comprado"], cor=COR_PRIM)
with c2:
    kpi_card("NFs Recebidas", kpis["qtd_nf"], cor=COR_PRIM, fmt=_fmt_int)
with c3:
    kpi_card("Fornecedores ativos", kpis["qtd_fornec"], cor=COR_PRIM, fmt=_fmt_int)
with c4:
    # Comparativo com total de rentabilidade
    fat_total = float(df_rent["FAT_TOTAL"].sum()) if not df_rent.empty else 0
    lucro_tot = float(df_rent["LUCRO_BRUTO"].sum()) if not df_rent.empty else 0
    kpi_card("Lucro Bruto Gerado", lucro_tot, negativo_ruim=False, cor=COR_OK)

st.divider()

# ══════════════════════════════════════════════════════════════════
#  ABAS
# ══════════════════════════════════════════════════════════════════
aba_evo, aba_forn, aba_dep, aba_rent, aba_alert, aba_cfg = st.tabs([
    "📈 Evolução de Compras",
    "🏭 Fornecedores",
    "⚖️ Dependência",
    "💰 Rentabilidade",
    "🚨 Alertas",
    "⚙️ Configurações",
])


# ══════════════════════════════════════════════════════════════════
#  ABA 1 — EVOLUÇÃO DE COMPRAS
# ══════════════════════════════════════════════════════════════════
with aba_evo:
    st.markdown(section_header("Evolução Mensal de Compras", "compras", 4),
                unsafe_allow_html=True)

    if df_hist.empty:
        st.info("Sem dados de compras no período.")
    else:
        # Gráfico barras
        fig_evo = go.Figure()
        fig_evo.add_trace(go.Bar(
            x=df_hist["PERIODO"], y=df_hist["TOTAL_COMPRADO"],
            name="Compras", marker_color=COR_PRIM,
            text=df_hist["TOTAL_COMPRADO"].apply(fmt_brl),
            textposition="outside",
        ))
        fig_evo.update_layout(
            title="Compras Mensais (últimos 13 meses)",
            xaxis_title="Período", yaxis_title="Valor (R$)",
            height=380,
            margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(fig_evo, use_container_width=True)

        # Métricas rápidas do histórico
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Maior mês", fmt_brl(df_hist["TOTAL_COMPRADO"].max()))
        col_m2.metric("Menor mês", fmt_brl(df_hist["TOTAL_COMPRADO"].min()))
        col_m3.metric("Média mensal", fmt_brl(df_hist["TOTAL_COMPRADO"].mean()))

        # Tabela histórico
        st.markdown(section_header("Detalhe por Mês", "itens", 5), unsafe_allow_html=True)
        h_exib = df_hist[["PERIODO", "QTD_NF", "QTD_FORNEC", "TOTAL_COMPRADO"]].copy()
        h_exib["TOTAL_COMPRADO"] = h_exib["TOTAL_COMPRADO"].apply(fmt_brl)
        h_exib = h_exib.rename(columns={
            "PERIODO": "Período", "QTD_NF": "NFs", "QTD_FORNEC": "Fornecedores",
            "TOTAL_COMPRADO": "Total Comprado",
        })
        st.dataframe(h_exib, use_container_width=True, hide_index=True)

    st.divider()
    _toolbar_export(
        "Evolução de Compras",
        {"Histórico Mensal": df_hist},
        {"Total período": fmt_brl(kpis["total_comprado"]),
         "NFs": str(kpis["qtd_nf"])},
        data_ini, data_fim, "evolucao_compras")
    _widget_comentario("evolucao_compras", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 2 — FORNECEDORES (TOP + RELEVÂNCIA)
# ══════════════════════════════════════════════════════════════════
with aba_forn:
    st.markdown(section_header("Top Fornecedores por Relevância", "fornecedor", 4),
                unsafe_allow_html=True)
    st.caption(
        bi("info", 13, "#888") + " Relevância medida pelo total comprado no período. "
        "Clique em um fornecedor para ver as NFs.",
        unsafe_allow_html=True)

    if df_forn.empty:
        st.info("Sem compras registradas no período.")
    else:
        top15 = df_forn.head(15).copy()

        fig_forn = px.bar(
            top15, x="TOTAL_COMPRADO", y="NOME_EXIB",
            orientation="h",
            text=top15["TOTAL_COMPRADO"].apply(fmt_brl),
            title="Top 15 Fornecedores por Valor Comprado",
            labels={"TOTAL_COMPRADO": "Total (R$)", "NOME_EXIB": "Fornecedor"},
            color="PARTICIPACAO", color_continuous_scale="Blues",
            height=max(350, len(top15) * 32 + 80),
        )
        fig_forn.update_traces(textposition="outside")
        fig_forn.update_layout(
            yaxis={"categoryorder": "total ascending"},
            coloraxis_showscale=False,
            margin=dict(l=10, r=120, t=50, b=10),
        )
        st.plotly_chart(fig_forn, use_container_width=True)

        st.markdown(section_header("Tabela — Todos os Fornecedores do Período", "itens", 5),
                    unsafe_allow_html=True)
        f_exib = df_forn[["NOME_EXIB", "QTD_NF", "TOTAL_COMPRADO",
                           "PARTICIPACAO", "PARTICIPACAO_ACUM"]].copy()
        f_exib["TOTAL_COMPRADO"]   = f_exib["TOTAL_COMPRADO"].apply(fmt_brl)
        f_exib["PARTICIPACAO"]     = f_exib["PARTICIPACAO"].apply(lambda x: f"{x:.1f}%")
        f_exib["PARTICIPACAO_ACUM"]= f_exib["PARTICIPACAO_ACUM"].apply(lambda x: f"{x:.1f}%")
        f_exib = f_exib.rename(columns={
            "NOME_EXIB": "Fornecedor", "QTD_NF": "NFs",
            "TOTAL_COMPRADO": "Total comprado",
            "PARTICIPACAO": "Participação", "PARTICIPACAO_ACUM": "% Acumulado",
        })
        idx_f = _df_selecionavel(f_exib, key="tbl_fornec", height=380)
        if idx_f is not None:
            sel = df_forn.iloc[idx_f]
            st.session_state["dlg_ctx_cmp"] = {
                "codfornec": sel["CODFORNEC"],
                "nome": sel["NOME_EXIB"],
                "data_ini": _ini_str,
                "data_fim": _fim_str,
            }
            dialog_fornecedor()

    st.divider()
    _toolbar_export(
        "Fornecedores",
        {"Fornecedores": df_forn},
        {"Total comprado": fmt_brl(kpis["total_comprado"]),
         "Fornecedores": str(kpis["qtd_fornec"])},
        data_ini, data_fim, "fornecedores")
    _widget_comentario("fornecedores", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 3 — DEPENDÊNCIA DE FORNECEDORES
# ══════════════════════════════════════════════════════════════════
with aba_dep:
    st.markdown(section_header("Dependência de Fornecedores", "compras", 4),
                unsafe_allow_html=True)
    st.caption(
        bi("info", 13, "#888") + " Alta concentração em poucos fornecedores representa risco operacional.",
        unsafe_allow_html=True)

    if df_forn.empty:
        st.info("Sem dados no período.")
    else:
        total_comp = df_forn["TOTAL_COMPRADO"].sum()

        # Gráfico pizza top 10
        top10 = df_forn.head(10).copy()
        outros = total_comp - top10["TOTAL_COMPRADO"].sum()
        if outros > 0:
            outros_row = pd.DataFrame([{"NOME_EXIB": "Demais", "TOTAL_COMPRADO": outros}])
            top10_pie = pd.concat([top10[["NOME_EXIB", "TOTAL_COMPRADO"]], outros_row], ignore_index=True)
        else:
            top10_pie = top10[["NOME_EXIB", "TOTAL_COMPRADO"]].copy()

        col_pie, col_metrics = st.columns([1, 1])
        with col_pie:
            fig_dep = px.pie(
                top10_pie, names="NOME_EXIB", values="TOTAL_COMPRADO",
                title="Top 10 × Demais (por valor comprado)",
                color_discrete_sequence=px.colors.qualitative.Set2,
                hole=0.38,
            )
            fig_dep.update_traces(textposition="inside", textinfo="percent+label")
            fig_dep.update_layout(showlegend=False, height=380,
                                   margin=dict(l=5, r=5, t=40, b=5))
            st.plotly_chart(fig_dep, use_container_width=True)

        with col_metrics:
            top1_pct  = float(df_forn["PARTICIPACAO"].iloc[0]) if len(df_forn) > 0 else 0
            top3_pct  = float(df_forn["PARTICIPACAO"].iloc[:3].sum()) if len(df_forn) >= 3 else 0
            top10_pct = float(df_forn["PARTICIPACAO"].iloc[:10].sum()) if len(df_forn) >= 10 else 0

            st.markdown("#### Concentração")
            for label, val, limiar in [
                ("Maior fornecedor", top1_pct, 30),
                ("Top 3 fornecedores", top3_pct, 60),
                ("Top 10 fornecedores", top10_pct, 80),
            ]:
                cor = COR_PERIGO if val > limiar else (COR_ALERTA if val > limiar * 0.8 else COR_OK)
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;"
                    f"padding:8px 12px;background:#f8f9fa;border-radius:6px;margin-bottom:6px'>"
                    f"<span>{label}</span>"
                    f"<span style='font-weight:700;color:{cor}'>{val:.1f}%</span>"
                    f"</div>",
                    unsafe_allow_html=True)

            if top1_pct > 30:
                st.warning(f"⚠️ O maior fornecedor representa **{top1_pct:.1f}%** das compras — "
                           f"risco de dependência.")
            if top3_pct > 60:
                st.warning(f"⚠️ Top 3 fornecedores concentram **{top3_pct:.1f}%** das compras.")

        # Tabela de dependência com curva acumulada
        st.markdown(section_header("Participação Individual", "itens", 5), unsafe_allow_html=True)
        dep_exib = df_forn[["NOME_EXIB", "QTD_NF", "TOTAL_COMPRADO",
                             "PARTICIPACAO", "PARTICIPACAO_ACUM"]].head(20).copy()
        dep_exib["TOTAL_COMPRADO"]   = dep_exib["TOTAL_COMPRADO"].apply(fmt_brl)
        dep_exib["PARTICIPACAO"]     = dep_exib["PARTICIPACAO"].apply(lambda x: f"{x:.1f}%")
        dep_exib["PARTICIPACAO_ACUM"]= dep_exib["PARTICIPACAO_ACUM"].apply(lambda x: f"{x:.1f}%")
        dep_exib = dep_exib.rename(columns={
            "NOME_EXIB": "Fornecedor", "QTD_NF": "NFs",
            "TOTAL_COMPRADO": "Total", "PARTICIPACAO": "%",
            "PARTICIPACAO_ACUM": "% Acumulado",
        })
        st.dataframe(dep_exib, use_container_width=True, hide_index=True, height=360)

    st.divider()
    _toolbar_export(
        "Dependência de Fornecedores",
        {"Dependência": df_forn},
        {"Top 1": f"{top1_pct:.1f}%" if not df_forn.empty else "—",
         "Top 3": f"{top3_pct:.1f}%" if not df_forn.empty else "—",
         "Top 10": f"{top10_pct:.1f}%" if not df_forn.empty else "—"},
        data_ini, data_fim, "dependencia")
    _widget_comentario("dependencia", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 4 — RENTABILIDADE POR FORNECEDOR
# ══════════════════════════════════════════════════════════════════
with aba_rent:
    st.markdown(section_header("Rentabilidade por Fornecedor", "compras", 4),
                unsafe_allow_html=True)
    st.caption(
        bi("info", 13, "#888") + " Compras = NFENTRC. Vendas geradas = produtos vinculados (RELPRFO) × vendas PDV (MVGERAL). "
        "Lucro Bruto = Vendas − CMV (custo atual COMPPROD como proxy).",
        unsafe_allow_html=True)

    if df_rent.empty:
        st.info("Sem dados de compras no período.")
    else:
        # Top 10 por lucro bruto
        top_lucro = df_rent[df_rent["LUCRO_BRUTO"] > 0].head(10).copy()

        if not top_lucro.empty:
            fig_rent = go.Figure()
            fig_rent.add_trace(go.Bar(
                name="Comprado", x=top_lucro["NOME_EXIB"],
                y=top_lucro["TOTAL_COMPRADO"],
                marker_color=COR_ALERTA,
            ))
            fig_rent.add_trace(go.Bar(
                name="Faturado gerado", x=top_lucro["NOME_EXIB"],
                y=top_lucro["FAT_TOTAL"],
                marker_color=COR_PRIM,
            ))
            fig_rent.add_trace(go.Bar(
                name="Lucro Bruto", x=top_lucro["NOME_EXIB"],
                y=top_lucro["LUCRO_BRUTO"],
                marker_color=COR_OK,
            ))
            fig_rent.update_layout(
                barmode="group",
                title="Top 10 — Compras × Faturado × Lucro Bruto por Fornecedor",
                xaxis_tickangle=-30, yaxis_title="Valor (R$)",
                height=420, legend=dict(orientation="h", yanchor="bottom", y=1.02),
                margin=dict(l=10, r=10, t=60, b=80),
            )
            st.plotly_chart(fig_rent, use_container_width=True)

        # Top 10 por lucro bruto gerado (requisito do protótipo)
        st.markdown(section_header("Top 10 Fornecedores por Lucro Bruto Gerado", "produto", 5),
                    unsafe_allow_html=True)
        total_lucro = float(df_rent["LUCRO_BRUTO"].sum())
        top10_lb = df_rent[df_rent["LUCRO_BRUTO"] > 0].head(10).copy()
        if not top10_lb.empty:
            top10_lb["PART_LUCRO"] = top10_lb["LUCRO_BRUTO"] / total_lucro * 100 if total_lucro > 0 else 0

            fig_lb = px.bar(
                top10_lb, x="LUCRO_BRUTO", y="NOME_EXIB",
                orientation="h",
                text=top10_lb["LUCRO_BRUTO"].apply(fmt_brl),
                title="Top 10 por Lucro Bruto Gerado",
                labels={"LUCRO_BRUTO": "Lucro Bruto (R$)", "NOME_EXIB": "Fornecedor"},
                color="PART_LUCRO", color_continuous_scale="Greens",
                height=350,
            )
            fig_lb.update_traces(textposition="outside")
            fig_lb.update_layout(yaxis={"categoryorder": "total ascending"},
                                  coloraxis_showscale=False,
                                  margin=dict(l=10, r=120, t=50, b=10))
            st.plotly_chart(fig_lb, use_container_width=True)

        # Tabela completa
        st.markdown(section_header("Tabela Completa de Rentabilidade", "itens", 5),
                    unsafe_allow_html=True)
        r_exib = df_rent[["NOME_EXIB", "QTD_NF", "TOTAL_COMPRADO",
                           "FAT_TOTAL", "LUCRO_BRUTO", "MARGEM",
                           "ESTOQUE_SKUS", "ESTOQUE_VALOR"]].copy()
        r_exib["TOTAL_COMPRADO"] = r_exib["TOTAL_COMPRADO"].apply(fmt_brl)
        r_exib["FAT_TOTAL"]      = r_exib["FAT_TOTAL"].apply(lambda x: fmt_brl(x) if x > 0 else "—")
        r_exib["LUCRO_BRUTO"]    = r_exib["LUCRO_BRUTO"].apply(lambda x: fmt_brl(x) if x != 0 else "—")
        r_exib["MARGEM"]         = r_exib["MARGEM"].apply(lambda x: f"{x:.1f}%" if x != 0 else "—")
        r_exib["ESTOQUE_VALOR"]  = r_exib["ESTOQUE_VALOR"].apply(lambda x: fmt_brl(x) if x > 0 else "—")
        r_exib = r_exib.rename(columns={
            "NOME_EXIB": "Fornecedor", "QTD_NF": "NFs",
            "TOTAL_COMPRADO": "Comprado", "FAT_TOTAL": "Faturado gerado",
            "LUCRO_BRUTO": "Lucro Bruto", "MARGEM": "Margem",
            "ESTOQUE_SKUS": "SKUs estoque", "ESTOQUE_VALOR": "Valor em estoque",
        })
        idx_r = _df_selecionavel(r_exib, key="tbl_rent", height=380)
        if idx_r is not None:
            sel = df_rent.iloc[idx_r]
            st.session_state["dlg_ctx_cmp"] = {
                "codfornec": sel["CODFORNEC"],
                "nome": sel["NOME_EXIB"],
                "data_ini": _ini_str,
                "data_fim": _fim_str,
            }
            dialog_fornecedor()

    st.divider()
    _toolbar_export(
        "Rentabilidade por Fornecedor",
        {"Rentabilidade": df_rent},
        {"Lucro Bruto Total": fmt_brl(total_lucro) if not df_rent.empty else "—"},
        data_ini, data_fim, "rentabilidade")
    _widget_comentario("rentabilidade", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 5 — ALERTAS
# ══════════════════════════════════════════════════════════════════
with aba_alert:
    st.markdown(section_header("Alertas de Compras", "alertas", 4),
                unsafe_allow_html=True)

    sub_sg, sub_ep = st.tabs(["⚠️ Produtos Comprados Sem Giro",
                               "📦 Estoque Parado por Fornecedor"])

    with sub_sg:
        st.markdown(
            f"<p style='color:#666;font-size:0.88em'>"
            f"{bi('info',13,'#888')} Produtos que foram comprados mas não tiveram nenhuma "
            f"venda PDV no período filtrado. Representa capital imobilizado sem retorno.</p>",
            unsafe_allow_html=True)

        df_sg = _carregar_sem_giro(_ini_str, _fim_str, _df_relprfo_shared, _df_estoque_shared)

        if df_sg.empty:
            st.success("Todos os produtos comprados no período tiveram vendas.")
        else:
            col_sg1, col_sg2, col_sg3 = st.columns(3)
            col_sg1.metric("Produtos sem giro", len(df_sg))
            col_sg2.metric("Qtd física parada", f"{df_sg['QTD'].sum():.0f}")
            col_sg3.metric("Valor em estoque", fmt_brl(df_sg["VALOR_CUSTO"].sum()))

            if df_sg["VALOR_CUSTO"].sum() > 50000:
                st.warning(f"⚠️ {fmt_brl(df_sg['VALOR_CUSTO'].sum())} imobilizado em produtos "
                           f"sem retorno de venda no período.")

            # Gráfico top 15 por valor
            top_sg = df_sg[df_sg["VALOR_CUSTO"] > 0].head(15)
            if not top_sg.empty:
                fig_sg = px.bar(
                    top_sg, x="VALOR_CUSTO", y="DESCRICAO",
                    orientation="h",
                    text=top_sg["VALOR_CUSTO"].apply(fmt_brl),
                    color="GRUPO", title="Top 15 — Produtos Comprados Sem Giro (por valor)",
                    labels={"VALOR_CUSTO": "Valor estoque (R$)", "DESCRICAO": "Produto"},
                    height=420,
                )
                fig_sg.update_traces(textposition="outside")
                fig_sg.update_layout(yaxis={"categoryorder": "total ascending"},
                                      legend=dict(orientation="h", yanchor="bottom", y=1.02),
                                      margin=dict(l=10, r=120, t=50, b=10))
                st.plotly_chart(fig_sg, use_container_width=True)

            sg_exib = df_sg[["CODPROD", "DESCRICAO", "GRUPO",
                              "QTD_COMPRADA", "VALOR_COMPRADO", "QTD", "VALOR_CUSTO"]].copy()
            sg_exib["VALOR_COMPRADO"] = sg_exib["VALOR_COMPRADO"].apply(fmt_brl)
            sg_exib["VALOR_CUSTO"]    = sg_exib["VALOR_CUSTO"].apply(lambda x: fmt_brl(x) if x > 0 else "—")
            sg_exib["QTD_COMPRADA"]   = sg_exib["QTD_COMPRADA"].apply(lambda x: f"{x:.1f}")
            sg_exib["QTD"]            = sg_exib["QTD"].apply(lambda x: f"{x:.1f}" if x > 0 else "—")
            sg_exib = sg_exib.rename(columns={
                "CODPROD": "Código", "DESCRICAO": "Produto", "GRUPO": "Grupo",
                "QTD_COMPRADA": "Qtd comprada", "VALOR_COMPRADO": "Valor comprado",
                "QTD": "Estoque atual", "VALOR_CUSTO": "Valor estoque",
            })
            st.dataframe(sg_exib, use_container_width=True, hide_index=True, height=380)

        _toolbar_export(
            "Produtos Sem Giro",
            {"Sem Giro": df_sg},
            {"Produtos sem giro": str(len(df_sg)) if not df_sg.empty else "0",
             "Valor imobilizado": fmt_brl(df_sg["VALOR_CUSTO"].sum()) if not df_sg.empty else "R$ 0,00"},
            data_ini, data_fim, "sem_giro")
        _widget_comentario("sem_giro", data_ini, data_fim)

    with sub_ep:
        st.markdown(
            f"<p style='color:#666;font-size:0.88em'>"
            f"{bi('info',13,'#888')} Estoque parado agrupado pelo fornecedor principal "
            f"(RELPRFO). Permite identificar quais fornecedores têm mais capital imobilizado.</p>",
            unsafe_allow_html=True)

        _dias_ep = st.select_slider("Parado há mais de:", options=[30, 60, 90, 180, 365],
                                    value=90, key="dias_ep_forn",
                                    format_func=lambda x: f"{x} dias")

        df_ep = _carregar_parado_forn(_dias_ep, _df_relprfo_shared)

        if df_ep.empty:
            st.success(f"Nenhum estoque parado há mais de {_dias_ep} dias com fornecedor identificado.")
        else:
            ep_col1, ep_col2 = st.columns(2)
            ep_col1.metric("Fornecedores com estoque parado", len(df_ep))
            ep_col2.metric("Valor total parado", fmt_brl(df_ep["VALOR_CUSTO"].sum()))

            fig_ep = px.bar(
                df_ep.head(15), x="VALOR_CUSTO", y="FORNECEDOR",
                orientation="h",
                text=df_ep.head(15)["VALOR_CUSTO"].apply(fmt_brl),
                title=f"Estoque Parado >{_dias_ep}d por Fornecedor (Top 15)",
                labels={"VALOR_CUSTO": "Valor custo (R$)", "FORNECEDOR": "Fornecedor"},
                color="VALOR_CUSTO", color_continuous_scale="Reds",
                height=400,
            )
            fig_ep.update_traces(textposition="outside")
            fig_ep.update_layout(yaxis={"categoryorder": "total ascending"},
                                  coloraxis_showscale=False,
                                  margin=dict(l=10, r=120, t=50, b=10))
            st.plotly_chart(fig_ep, use_container_width=True)

            ep_exib = df_ep.copy()
            ep_exib["VALOR_CUSTO"] = ep_exib["VALOR_CUSTO"].apply(fmt_brl)
            ep_exib["QTD"]         = ep_exib["QTD"].apply(lambda x: f"{x:.1f}")
            ep_exib = ep_exib.rename(columns={
                "FORNECEDOR": "Fornecedor", "SKUS": "SKUs parados",
                "QTD": "Qtd", "VALOR_CUSTO": "Valor custo",
            })
            st.dataframe(ep_exib, use_container_width=True, hide_index=True, height=340)

        _toolbar_export(
            f"Estoque Parado {_dias_ep}d por Fornecedor",
            {"Parado por Fornecedor": df_ep},
            {"Valor parado": fmt_brl(df_ep["VALOR_CUSTO"].sum()) if not df_ep.empty else "R$ 0,00"},
            data_ini, data_fim, "parado_forn")
        _widget_comentario("parado_forn", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 6 — CONFIGURAÇÕES
# ══════════════════════════════════════════════════════════════════
with aba_cfg:
    st.markdown(section_header("Configurações e Notas Gerais", "config", 4),
                unsafe_allow_html=True)
    _widget_comentario("geral_compras", data_ini, data_fim)

    st.divider()
    st.markdown("#### Informações do Módulo")
    st.markdown(
        f"- **Fonte de compras:** NFENTRC (cabeçalho) + NFENTRI (itens)\n"
        f"- **Fornecedores:** FORNECE + RELPRFO (relação produto-fornecedor)\n"
        f"- **Rentabilidade:** vendas via MVGERAL (TM=55) × produtos vinculados (RELPRFO)\n"
        f"- **CMV:** QTD vendida × COMPPROD.PRECOCUSTO (custo atual — aproximação)\n"
        f"- **Período atual:** {data_ini.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}\n"
        f"- **Total comprado:** {fmt_brl(kpis['total_comprado'])}\n"
        f"- **NFs recebidas:** {kpis['qtd_nf']}\n"
        f"- **Fornecedores:** {kpis['qtd_fornec']}")
