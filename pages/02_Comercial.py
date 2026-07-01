"""
Módulo Comercial — completo
Filtros globais · Meta & Indicadores · Faturamento · Clientes · Concentração
Sazonalidade · Drill-down (Cliente → Pedido → Itens) · Exportação · Comentários
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from components.bi_icons import inject_bi, bi, section_header

from core.domain.comercial import (
    get_faturamento, get_kpis_comercial, get_meta_mes, get_projecao_fechamento_mes,
    get_faturamento_periodo, get_comparativo_faturamento, get_ticket_medio,
    get_ranking_vendedores, get_funil_pedidos, get_descontos_periodo,
    get_itens_periodo, get_itens_pedido, get_pedidos_cliente,
    get_top_clientes_faturamento, get_top_clientes_lucro, get_top_produtos,
    get_ultima_compra_clientes, get_clientes_sem_comprar, get_clientes_queda_compras,
    get_clientes_novos_recorrentes,
    get_concentracao_clientes, get_concentracao_produtos, get_sazonalidade,
    get_faturamento_por_forma_pgto,
    classifica_faixa_sem_comprar, classifica_curva_abc, resumo_curva_abc,
)
from core.data.duckdb_store import init_store, get_config, set_config
from components.sidebar_filtros import render_sidebar, carregar_opcoes_filtros
from core.domain.filtros import aplicar
from components.print_btn import render_print_css, render_print_button
from components.metrics import fmt_brl, kpi_card
from components.theme import COR_PRIM, COR_OK, COR_ALERTA, COR_PERIGO
from components.widgets import df_selecionavel, selecao_mudou, make_widget_comentario, make_toolbar_export

st.set_page_config(page_title="Comercial", page_icon="🛒", layout="wide")
init_store()
render_print_css()
inject_bi()

MODULO = "comercial"


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════
# _widget_comentario, _toolbar_export e _df_selecionavel: ver components/widgets.py
# (antes duplicados de forma idêntica nas 4 páginas de módulo).
_df_selecionavel = df_selecionavel
_widget_comentario = make_widget_comentario(
    MODULO, placeholder="Ex.: Faturamento subiu por causa da campanha de junho...")
_toolbar_export = make_toolbar_export(MODULO)


def _itens_pedido_table(codempresa: str, tipopedido: str, codpedido: str, codcliente: str):
    """Renderiza a tabela de itens de um pedido específico (drill-down nível 2 do dialog_cliente)."""
    st.markdown(section_header("Itens do Pedido", "itens", level=5), unsafe_allow_html=True)
    itens = get_itens_pedido(codempresa, tipopedido, codpedido, codcliente)
    if itens.empty:
        st.info("Nenhum item encontrado para este pedido.")
        return
    i = itens.copy()
    i["PRECOUNIT"]   = i["PRECOUNIT"].apply(fmt_brl)
    i["DESCONTO"]    = i["DESCONTO"].apply(fmt_brl)
    i["TOTAL"]       = i["TOTAL"].apply(fmt_brl)
    st.dataframe(
        i.rename(columns={"CODPROD": "Código", "PRODUTO": "Produto", "QUANTIDADE": "Qtd",
                          "PRECOUNIT": "Preço Unit", "DESCONTO": "Desconto", "TOTAL": "Total"}),
        use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════
#  DIALOG — drill-down Cliente → Pedido → Itens
# ══════════════════════════════════════════════════════════════════
@st.dialog("🛒 Pedidos do Cliente", width="large")
def dialog_cliente():
    """Modal de drill-down: pedidos faturados do cliente clicado, com itens ao selecionar um pedido."""
    ctx = st.session_state.get("dlg_ctx_com", {})
    cod_cli, nome_cli, df_fat = ctx.get("cod_cli"), ctx.get("nome_cli"), ctx.get("df_fat")
    if not cod_cli or df_fat is None:
        st.error("Contexto inválido."); return

    st.markdown(f"### {nome_cli}")
    st.caption("Clique em um pedido para ver os itens.")

    pedidos = get_pedidos_cliente(df_fat, cod_cli)
    p_exib = pedidos[["CODPEDIDO", "TIPOPEDIDO", "DATAFATURA", "TOTALPEDIDO", "NOME_VENDEDOR"]].copy()
    p_exib["DATAFATURA"]  = p_exib["DATAFATURA"].dt.strftime("%d/%m/%Y")
    p_exib["TOTALPEDIDO"] = p_exib["TOTALPEDIDO"].apply(fmt_brl)
    p_exib = p_exib.rename(columns={"CODPEDIDO": "Pedido", "TIPOPEDIDO": "Tipo",
        "DATAFATURA": "Faturado em", "TOTALPEDIDO": "Valor", "NOME_VENDEDOR": "Vendedor"})

    idx = _df_selecionavel(p_exib, key="dlg_com_pedidos")
    if idx is not None:
        p = pedidos.iloc[idx]
        st.markdown("---")
        hdr = f"Pedido {p['CODPEDIDO']} | {p['DATAFATURA'].strftime('%d/%m/%Y')} | {fmt_brl(p['TOTALPEDIDO'])}"
        st.markdown(section_header(hdr, "documento", 5), unsafe_allow_html=True)
        _itens_pedido_table(p["CODEMPRESA"], p["TIPOPEDIDO"], p["CODPEDIDO"], p["CODCLIENTE"])


# ══════════════════════════════════════════════════════════════════
#  CACHE
# ══════════════════════════════════════════════════════════════════
@st.cache_data(ttl=900, show_spinner="Carregando dados de faturamento…")
def _carregar_faturamento():
    """Carrega os últimos 25 meses de faturamento — base para todas as análises da página."""
    return get_faturamento(meses_historico=25)

@st.cache_data(ttl=900, show_spinner=False)
def _carregar_itens(data_ini_str, data_fim_str):
    """Carrega os itens de pedido faturados no período (para lucro bruto e top produtos)."""
    return get_itens_periodo(pd.Timestamp(data_ini_str), pd.Timestamp(data_fim_str))

@st.cache_data(ttl=900, show_spinner=False)
def _carregar_funil(data_ini_str, data_fim_str):
    """Carrega o funil de pedidos criados no período (aba Meta & Indicadores)."""
    return get_funil_pedidos(pd.Timestamp(data_ini_str), pd.Timestamp(data_fim_str))

@st.cache_data(ttl=1800, show_spinner=False)
def _carregar_ultima_compra():
    """Carrega a primeira/última compra de cada cliente (base de Novos×Recorrentes e Clientes sem comprar)."""
    return get_ultima_compra_clientes()

@st.cache_data(ttl=1800, show_spinner=False)
def _carregar_queda():
    """Carrega os clientes com maior queda de compras nos últimos 30 dias vs média de 6 meses."""
    return get_clientes_queda_compras()

@st.cache_data(ttl=3600, show_spinner=False)
def _carregar_sazonalidade():
    """Carrega a série mensal de faturamento dos últimos 24 meses (aba Sazonalidade)."""
    return get_sazonalidade(24)


try:
    df_fat_raw = _carregar_faturamento()
    opcoes = carregar_opcoes_filtros()
except Exception as e:
    st.error(f"Erro ao conectar ao banco: {e}"); st.stop()

# ── Sidebar com filtros centralizados ────────────────────────────
filtros = render_sidebar(
    opcoes,
    visiveis=["periodo", "empresa", "vendedor", "cliente", "grupo", "marca"],
)

data_ini = filtros["data_ini"]
data_fim = filtros["data_fim"]

df_fat = aplicar(df_fat_raw, filtros, mapa={
    "periodo":  "DATAFATURA",
    "empresa":  "CODEMPRESA",
    "vendedor": "CODVENDEDOR",
    "cliente":  "CODCLIENTE",
})

kpis = get_kpis_comercial(df_fat)

# ── Cabeçalho ─────────────────────────────────────────────────────
col_titulo, col_print = st.columns([9, 1])
with col_titulo:
    st.markdown(
        f"<h1 style='margin:0;display:flex;align-items:center;gap:10px'>"
        f"{bi('comercial',28,'#1f6bb5')} Comercial</h1>"
        f"<p style='margin:2px 0 0;color:#888;font-size:0.88em'>"
        f"{bi('calendario',13,'#888')} Período: "
        f"{data_ini.strftime('%d/%m/%Y')} — {data_fim.strftime('%d/%m/%Y')}</p>",
        unsafe_allow_html=True)
with col_print:
    st.markdown("<div style='margin-top:12px'>", unsafe_allow_html=True)
    render_print_button(key="print_comercial")
    st.markdown("</div>", unsafe_allow_html=True)

_fmt_int = lambda v: f"{v:,.0f}".replace(",", ".")
c1, c2, c3, c4 = st.columns(4)
with c1: kpi_card("Faturamento (período)", kpis["total_faturado"], cor=COR_PRIM)
with c2: kpi_card("Ticket Médio",          kpis["ticket_medio"], negativo_ruim=False, cor=COR_PRIM)
with c3: kpi_card("Pedidos faturados",     kpis["qtd_pedidos"], cor=COR_OK, fmt=_fmt_int)
with c4: kpi_card("Clientes atendidos",    kpis["n_clientes"], cor=COR_OK, fmt=_fmt_int)
st.divider()

aba_meta, aba_fat, aba_pgto, aba_cli, aba_conc, aba_saz, aba_cfg = st.tabs([
    "🎯 Meta & Indicadores",
    "📈 Faturamento",
    "💳 Forma de Pagamento",
    "👥 Clientes",
    "🧩 Concentração",
    "📅 Sazonalidade",
    "⚙️ Configurações",
])

# Itens do período filtrado — base para lucro bruto / top produtos / concentração de produto
df_itens = _carregar_itens(data_ini.strftime("%Y-%m-%d"), data_fim.strftime("%Y-%m-%d"))


# ══════════════════════════════════════════════════════════════════
#  ABA 1 — META & INDICADORES
# ══════════════════════════════════════════════════════════════════
with aba_meta:
    meta_configurada = float(get_config("meta_faturamento_mensal", 0) or 0)
    meta_info = get_meta_mes(meta_configurada)
    proj = get_projecao_fechamento_mes(df_fat_raw)

    st.markdown(section_header(f"Indicadores do mês corrente — {meta_info['mes_ano']}", "comercial", 4),
                unsafe_allow_html=True)

    meta_valor = meta_info["meta"]
    pct_meta = (proj["total_ate_hoje"] / meta_valor * 100) if meta_valor else None

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Meta do mês", fmt_brl(meta_valor) if meta_valor else "Não configurada")
        st.caption(f"Fonte: {meta_info['fonte']}")
    with c2:
        kpi_card("Faturado até hoje", proj["total_ate_hoje"], negativo_ruim=False, cor=COR_OK)
    with c3:
        if pct_meta is not None:
            cor = COR_OK if pct_meta >= 100 else (COR_ALERTA if pct_meta >= 70 else COR_PERIGO)
            st.markdown(
                f"<div style='text-align:center'>"
                f"<div style='font-size:2.2rem;font-weight:800;color:{cor};line-height:1'>"
                f"{pct_meta:.1f}%</div>"
                f"<small style='color:#888'>da meta atingida</small></div>",
                unsafe_allow_html=True)
        else:
            st.warning("⚙️ Meta não configurada — acesse a aba **Configurações** para definir a meta do mês.")
    with c4:
        kpi_card("Projeção de fechamento", proj["projecao"], negativo_ruim=False, cor=COR_PRIM)
        st.caption(f"Ritmo dos {proj['dias_passados']} dias decorridos × {proj['dias_no_mes']} dias do mês")

    if meta_valor and pct_meta is not None:
        st.progress(min(pct_meta / 100, 1.0),
                    text=f"{fmt_brl(proj['total_ate_hoje'])} de {fmt_brl(meta_valor)} ({pct_meta:.1f}%)")

    st.divider()
    st.markdown(section_header("Comparativo de Faturamento", "comparativo", 4), unsafe_allow_html=True)
    comp = get_comparativo_faturamento(df_fat_raw)
    if comp:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric(f"Mês atual ({comp['label_atual']})", fmt_brl(comp["atual"]))
        with c2:
            delta = comp["atual"] - comp["mes_anterior"]
            st.metric(f"Mês anterior ({comp['label_mes_anterior']})", fmt_brl(comp["mes_anterior"]),
                      delta=fmt_brl(delta), delta_color="normal")
        with c3:
            delta2 = comp["atual"] - comp["mesmo_mes_ano_anterior"]
            st.metric(f"Mesmo mês ano anterior ({comp['label_ano_anterior']})",
                      fmt_brl(comp["mesmo_mes_ano_anterior"]),
                      delta=fmt_brl(delta2), delta_color="normal")
        if comp["mesmo_mes_ano_anterior"] == 0:
            st.caption(f"{bi('info',13,'#888')} Sem histórico de faturamento em "
                       f"{comp['label_ano_anterior']} na base disponível.", unsafe_allow_html=True)

    st.divider()
    st.markdown(section_header("Funil de Pedidos do Período", "fluxo", 4), unsafe_allow_html=True)
    st.caption(
        f"{bi('info',13,'#888')} Pedidos **criados** no período (`DATAPEDIDO`), pelo status "
        f"atual de faturamento — mostra a taxa de aproveitamento e o valor parado em "
        f"pendentes. Pedidos criados perto do fim do período ainda podem ser faturados "
        f"depois; a taxa reflete o status até o momento da consulta, não o resultado final.",
        unsafe_allow_html=True)
    funil = _carregar_funil(data_ini.strftime("%Y-%m-%d"), data_fim.strftime("%Y-%m-%d"))
    if funil["total_pedidos"] == 0:
        st.info("Nenhum pedido criado no período selecionado.")
    else:
        cf1, cf2, cf3 = st.columns(3)
        with cf1:
            kpi_card("Pedidos criados no período", funil["total_pedidos"], cor=COR_PRIM, fmt=_fmt_int)
        with cf2:
            cor_tx = COR_OK if funil["taxa_conversao"] >= 70 else (COR_ALERTA if funil["taxa_conversao"] >= 40 else COR_PERIGO)
            st.markdown(
                f"<div style='text-align:center'><div style='font-size:1.9rem;font-weight:bold;color:{cor_tx}'>"
                f"{funil['taxa_conversao']:.1f}%</div><small>taxa de conversão (faturados / criados)</small></div>",
                unsafe_allow_html=True)
        with cf3:
            kpi_card("Valor parado em pendentes", funil["valor_pendente"], negativo_ruim=True, cor=COR_ALERTA)

        col_fn_graf, col_fn_tab = st.columns([2, 1])
        with col_fn_graf:
            _fd = funil["dados"].copy()
            _cor_map = {"Faturado": COR_OK, "Não faturado / pendente": COR_ALERTA, "Cancelado / outro": COR_PERIGO}
            fig_fn = px.bar(
                _fd, x="Quantidade", y="Situação", orientation="h",
                color="Situação", color_discrete_map=_cor_map,
                text_auto=True,
            )
            fig_fn.update_traces(textposition="outside")
            fig_fn.update_layout(height=160, margin=dict(t=10, b=0, l=0, r=60),
                                 showlegend=False, xaxis_title="Qtd. pedidos", yaxis_title="")
            st.plotly_chart(fig_fn, use_container_width=True)
        with col_fn_tab:
            f_exib = funil["dados"].copy()
            f_exib["Valor"] = f_exib["Valor"].apply(fmt_brl)
            st.dataframe(f_exib, use_container_width=True, hide_index=True, height=160)

    _widget_comentario("meta_indicadores", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 2 — FATURAMENTO
# ══════════════════════════════════════════════════════════════════
with aba_fat:
    st.markdown(section_header("Faturamento por período", "fluxo", 4), unsafe_allow_html=True)
    granularidade = st.radio("Agrupar por:", ["Dia", "Semana", "Quinzena", "Mês"],
                             horizontal=True, key="gran_fat")
    gran_map = {"Dia": "dia", "Semana": "semana", "Quinzena": "quinzena", "Mês": "mes"}
    df_periodo = get_faturamento_periodo(df_fat, gran_map[granularidade])

    if df_periodo.empty:
        st.info("Sem faturamento no período selecionado.")
    else:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_periodo["Periodo"], y=df_periodo["Faturamento"],
                             marker_color=COR_PRIM, name="Faturamento"))
        fig.update_layout(height=320, margin=dict(t=10, b=0, l=0, r=0), yaxis_title="R$")
        st.plotly_chart(fig, use_container_width=True)

    # ── Stacked por vendedor ──────────────────────────────────────
    if not df_fat.empty and "NOME_VENDEDOR" in df_fat.columns:
        st.markdown(section_header("Faturamento por Vendedor — Evolução Mensal", "cliente", 4),
                    unsafe_allow_html=True)
        _vd = df_fat.copy()
        _vd["MES_DT"] = _vd["DATAFATURA"].dt.to_period("M").dt.to_timestamp()
        _vd_grp = (
            _vd.groupby(["MES_DT", "NOME_VENDEDOR"])
            .agg(FATURAMENTO=("TOTALPEDIDO", "sum"), PEDIDOS=("CODPEDIDO", "nunique"))
            .reset_index()
        )
        _vd_grp["TICKET"] = (_vd_grp["FATURAMENTO"] / _vd_grp["PEDIDOS"].replace(0, pd.NA)).fillna(0)

        if not _vd_grp.empty:
            fig_vd = px.bar(
                _vd_grp.sort_values("MES_DT"),
                x="MES_DT", y="FATURAMENTO", color="NOME_VENDEDOR",
                barmode="stack",
                custom_data=["NOME_VENDEDOR", "PEDIDOS", "TICKET"],
                labels={"MES_DT": "Mês", "FATURAMENTO": "R$", "NOME_VENDEDOR": "Vendedor"},
                title="Contribuição de cada vendedor por mês",
            )
            fig_vd.update_traces(
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Faturamento: <b>R$ %{y:,.2f}</b><br>"
                    "Pedidos: %{customdata[1]}<br>"
                    "Ticket médio: R$ %{customdata[2]:,.2f}"
                    "<extra></extra>"
                )
            )
            fig_vd.update_layout(
                height=380,
                xaxis=dict(
                    rangeselector=dict(buttons=[
                        dict(count=3,  label="3M",  step="month", stepmode="backward"),
                        dict(count=6,  label="6M",  step="month", stepmode="backward"),
                        dict(count=12, label="12M", step="month", stepmode="backward"),
                        dict(step="all", label="Tudo"),
                    ]),
                    tickformat="%m/%Y",
                ),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                margin=dict(t=60, b=0, l=0, r=0),
                yaxis_title="R$",
            )
            st.plotly_chart(fig_vd, use_container_width=True)

    st.divider()
    col_tk, col_tk2 = st.columns([1, 2])
    tm = get_ticket_medio(df_fat)
    with col_tk:
        st.markdown(section_header("Ticket Médio Geral", "comercial", 5), unsafe_allow_html=True)
        st.metric("Ticket médio", fmt_brl(tm["geral"]))
    with col_tk2:
        st.markdown(section_header("Ticket Médio por Vendedor", "cliente", 5), unsafe_allow_html=True)
        if not tm["por_vendedor"].empty:
            pv = tm["por_vendedor"].copy()
            fig_v = px.bar(pv, x="Ticket_Medio", y="NOME_VENDEDOR", orientation="h",
                           labels={"Ticket_Medio": "Ticket Médio (R$)", "NOME_VENDEDOR": ""},
                           color_discrete_sequence=[COR_PRIM])
            fig_v.update_layout(height=260, margin=dict(t=10, b=0))
            st.plotly_chart(fig_v, use_container_width=True)
        else:
            st.info("Sem dados de vendedor no período.")

    st.divider()
    st.markdown(section_header("Ranking de Vendedores", "cliente", 4), unsafe_allow_html=True)
    ranking = get_ranking_vendedores(df_fat)
    if ranking.empty:
        st.info("Sem dados de vendedor no período selecionado.")
    else:
        r_exib = ranking.copy()
        r_exib["Faturamento"] = r_exib["Faturamento"].apply(fmt_brl)
        r_exib["Ticket_Medio"] = r_exib["Ticket_Medio"].apply(fmt_brl)
        st.dataframe(
            r_exib.rename(columns={"NOME_VENDEDOR": "Vendedor", "Ticket_Medio": "Ticket Médio"})
                  [["Posição", "Vendedor", "Faturamento", "Pedidos", "Clientes", "Ticket Médio"]],
            use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(section_header("Descontos Concedidos", "comparativo", 4), unsafe_allow_html=True)
    st.caption(f"{bi('info',13,'#888')} Baseado em `PEDIDOI.DESCONTOVLR` dos itens faturados no "
               f"período — ajuda a identificar onde a margem está sendo cedida em negociação.",
               unsafe_allow_html=True)
    desc = get_descontos_periodo(df_itens, df_fat)
    if desc["total_desconto"] == 0:
        st.success("Nenhum desconto registrado nos itens do período — margens preservadas.")
    else:
        cd1, cd2 = st.columns(2)
        with cd1:
            kpi_card("Total concedido em descontos", desc["total_desconto"], negativo_ruim=True, cor=COR_ALERTA)
        with cd2:
            kpi_card("% sobre o faturamento dos itens", desc["perc_sobre_faturado"],
                     cor=COR_ALERTA, fmt=lambda v: f"{v:.2f}%")

        col_dv, col_dc = st.columns(2)
        with col_dv:
            st.markdown("**Por Vendedor**")
            dv = desc["por_vendedor"].copy()
            dv["Desconto"] = dv["Desconto"].apply(fmt_brl)
            dv["Faturamento"] = dv["Faturamento"].apply(fmt_brl)
            dv["Desconto_%"] = dv["Desconto_%"].apply(lambda v: f"{v:.1f}%")
            st.dataframe(
                dv.rename(columns={"NOME_VENDEDOR": "Vendedor", "Desconto_%": "% s/ faturado"})
                  [["Vendedor", "Desconto", "Faturamento", "% s/ faturado"]],
                use_container_width=True, hide_index=True, height=240)
        with col_dc:
            st.markdown("**Top 10 Clientes (maior desconto absoluto)**")
            dc = desc["por_cliente"].copy()
            if dc.empty:
                st.info("Nenhum cliente com desconto no período.")
            else:
                dc["Desconto"] = dc["Desconto"].apply(fmt_brl)
                dc["Faturamento"] = dc["Faturamento"].apply(fmt_brl)
                dc["Desconto_%"] = dc["Desconto_%"].apply(lambda v: f"{v:.1f}%")
                st.dataframe(
                    dc.rename(columns={"NOME_CLIENTE": "Cliente", "Desconto_%": "% s/ faturado"})
                      [["Cliente", "Desconto", "Faturamento", "% s/ faturado"]],
                    use_container_width=True, hide_index=True, height=240)

    st.divider()
    secoes_fat = {
        "Faturamento por período": df_periodo.assign(Periodo=lambda d: d["Periodo"].astype(str)),
        "Ranking de Vendedores": ranking,
        "Descontos por Vendedor": desc.get("por_vendedor", pd.DataFrame()),
    }
    kpis_fat_exp = {
        "Faturamento total": fmt_brl(kpis["total_faturado"]),
        "Ticket médio":      fmt_brl(tm["geral"]),
        "Pedidos":           str(kpis["qtd_pedidos"]),
        "Total em descontos": fmt_brl(desc["total_desconto"]),
    }
    _toolbar_export("Faturamento", secoes_fat, kpis_fat_exp, data_ini, data_fim, "faturamento")
    _widget_comentario("faturamento", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA — FORMA DE PAGAMENTO
# ══════════════════════════════════════════════════════════════════
with aba_pgto:
    st.markdown(section_header("Faturamento por Forma de Pagamento", "credit-card", 4), unsafe_allow_html=True)
    st.caption(
        "Rateio proporcional: quando um pedido foi liquidado em mais de uma forma de "
        "pagamento, o valor é dividido entre elas proporcionalmente ao peso de cada uma "
        "nas liquidações reais (MOVIREC) — em vez de atribuído inteiro a uma só forma."
    )

    df_pgto = get_faturamento_por_forma_pgto(df_fat)

    if df_pgto.empty:
        st.info("Nenhuma liquidação rastreável encontrada para o período filtrado "
                "(títulos de convênio ou ainda em aberto não entram neste rateio).")
    else:
        total_fat_periodo = kpis["total_faturado"]
        cobertura = (df_pgto["VALOR_RATEADO"].sum() / total_fat_periodo * 100
                     if total_fat_periodo > 0 else 0)

        # O ERP só identifica a forma de pagamento por código (ex.: '03', '07',
        # 'CK') — não existe cadastro com os nomes. Mapeamento editável,
        # salvo no DuckDB (mesmo padrão de meta_faturamento_mensal/piso_caixa).
        def _label_forma(codigo: str) -> str:
            cod_chave = codigo.strip() if codigo and codigo.strip() else "EM_BRANCO"
            return get_config(f"forma_pgto_label_{cod_chave}", codigo or "(sem código)")

        df_pgto_exib = df_pgto.copy()
        df_pgto_exib["FORMA"] = df_pgto_exib["CODFORMAPGTO"].apply(_label_forma)

        col_pg1, col_pg2 = st.columns([3, 2])
        with col_pg1:
            fig_pgto = px.pie(df_pgto_exib, names="FORMA", values="VALOR_RATEADO",
                              title="Distribuição por forma de pagamento", hole=0.4)
            fig_pgto.update_traces(textinfo="label+percent")
            fig_pgto.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig_pgto, use_container_width=True)
        with col_pg2:
            tab_exib = df_pgto_exib[["FORMA", "VALOR_RATEADO", "PCT"]].copy()
            tab_exib["VALOR_RATEADO"] = tab_exib["VALOR_RATEADO"].apply(fmt_brl)
            tab_exib["PCT"] = tab_exib["PCT"].apply(lambda v: f"{v:.1f}%")
            st.dataframe(
                tab_exib.rename(columns={"FORMA": "Forma", "VALOR_RATEADO": "Valor", "PCT": "%"}),
                use_container_width=True, hide_index=True)
            st.caption(f"Cobertura: {cobertura:.0f}% do faturamento do período tem liquidação "
                       f"rastreada até uma forma de pagamento. O restante são títulos de "
                       f"convênio (CO) ou ainda em aberto, sem liquidação para ratear.")

        with st.expander("⚙️ Mapear nomes das formas de pagamento (códigos do ERP)"):
            st.caption("O ERP identifica a forma de pagamento só por código — dê um nome para "
                       "cada uma (ex.: Dinheiro, PIX, Cartão Débito). Fica salvo e passa a "
                       "valer para todos os relatórios deste módulo.")
            for codigo in sorted(df_pgto["CODFORMAPGTO"].unique()):
                cod_chave = codigo.strip() if codigo and codigo.strip() else "EM_BRANCO"
                atual = get_config(f"forma_pgto_label_{cod_chave}", codigo or "(sem código)")
                novo = st.text_input(f"Código '{codigo or '(em branco)'}'", value=atual,
                                     key=f"forma_pgto_input_{cod_chave}")
                if novo != atual:
                    set_config(f"forma_pgto_label_{cod_chave}", novo)
                    st.rerun()


# ══════════════════════════════════════════════════════════════════
#  ABA 3 — CLIENTES
# ══════════════════════════════════════════════════════════════════
with aba_cli:
    st.markdown(section_header("Clientes Novos vs Recorrentes", "cliente", 4), unsafe_allow_html=True)
    df_ultima = _carregar_ultima_compra()
    novos_rec = get_clientes_novos_recorrentes(df_fat, df_ultima, data_ini)
    if novos_rec["dados"].empty:
        st.info("Sem dados suficientes para classificar clientes novos/recorrentes no período.")
    else:
        cnr1, cnr2 = st.columns(2)
        with cnr1:
            st.metric("Clientes novos no período", novos_rec["novos"])
            st.caption(f"{fmt_brl(novos_rec['fat_novos'])} em faturamento")
        with cnr2:
            st.metric("Clientes recorrentes no período", novos_rec["recorrentes"])
            st.caption(f"{fmt_brl(novos_rec['fat_recorrentes'])} em faturamento")

        col_nr_graf, col_nr_tab = st.columns([1, 1])
        with col_nr_graf:
            fig_nr = px.pie(novos_rec["dados"], names="Categoria", values="Clientes",
                            color_discrete_sequence=[COR_PRIM, COR_OK])
            fig_nr.update_layout(height=260, margin=dict(t=10, b=0))
            st.plotly_chart(fig_nr, use_container_width=True)
        with col_nr_tab:
            nr_exib = novos_rec["dados"].copy()
            nr_exib["Faturamento"] = nr_exib["Faturamento"].apply(fmt_brl)
            st.dataframe(nr_exib, use_container_width=True, hide_index=True, height=140)

        st.caption(
            f"{bi('info',13,'#888')} 'Novo' = 1ª compra (em todo o histórico disponível) "
            f"dentro do período filtrado; 'recorrente' = cliente que já comprava antes do filtro.",
            unsafe_allow_html=True)
        if novos_rec["recorrentes"] == 0 and novos_rec["novos"] > 0:
            st.caption(
                f"{bi('warning',13,'#888')} Nesta cópia de teste, o histórico de faturamento "
                f"disponível é curto (poucos meses) — por isso a 1ª compra de praticamente todos "
                f"os clientes ativos cai dentro do próprio período filtrado, e todos aparecem "
                f"como 'novos'. No ERP em produção, com histórico completo, este indicador "
                f"refletirá corretamente a proporção entre captação de clientes e retenção.",
                unsafe_allow_html=True)

    st.divider()
    st.markdown(section_header("Top Clientes", "cliente", 4), unsafe_allow_html=True)
    criterio_top = st.radio("Ordenar por:", ["Faturamento", "Lucro Bruto (estimado)"],
                            horizontal=True, key="crit_top_cli")

    if criterio_top == "Faturamento":
        top_cli = get_top_clientes_faturamento(df_fat, top_n=10)
        col_show = ["NOME_CLIENTE", "Faturamento", "Pedidos"]
        rename = {"NOME_CLIENTE": "Cliente", "Faturamento": "Faturamento", "Pedidos": "Pedidos"}
    else:
        top_cli = get_top_clientes_lucro(df_itens, df_fat, top_n=10)
        col_show = ["NOME_CLIENTE", "LUCRO_BRUTO"]
        rename = {"NOME_CLIENTE": "Cliente", "LUCRO_BRUTO": "Lucro Bruto"}
        st.caption(f"{bi('info',13,'#888')} Lucro bruto estimado com custo atual "
                   f"(`COMPPROD.PRECOCUSTO`) — não há custo histórico do item vendido.",
                   unsafe_allow_html=True)

    if top_cli.empty:
        st.info("Sem dados suficientes para o período/filtros selecionados.")
    else:
        t_exib = top_cli[col_show].rename(columns=rename).copy()
        col_valor = "Faturamento" if "Faturamento" in t_exib.columns else "Lucro Bruto"
        fig_top = px.bar(t_exib.sort_values(col_valor), x=col_valor, y="Cliente", orientation="h",
                         color_discrete_sequence=[COR_PRIM])
        fig_top.update_layout(height=360, margin=dict(t=10, b=0))
        st.plotly_chart(fig_top, use_container_width=True)

        t_fmt = t_exib.copy()
        t_fmt[col_valor] = t_fmt[col_valor].apply(fmt_brl)
        st.dataframe(t_fmt, use_container_width=True, hide_index=True)

        st.markdown(f"**{bi('clique',14,COR_PRIM)} Selecione um cliente para ver o histórico de pedidos:**",
                    unsafe_allow_html=True)
        idx_cli = _df_selecionavel(t_fmt, key="cli_top_sel", height=240)
        if selecao_mudou("cli_top_sel", idx_cli):
            sel = top_cli.iloc[idx_cli]
            st.session_state["dlg_ctx_com"] = {
                "cod_cli": sel["CODCLIENTE"], "nome_cli": sel["NOME_CLIENTE"], "df_fat": df_fat_raw,
            }
            dialog_cliente()

    st.divider()
    st.markdown(section_header("Top Produtos", "produto", 4), unsafe_allow_html=True)
    criterio_prod = st.radio("Ordenar por:", ["Faturamento", "Quantidade", "Lucro Bruto (estimado)"],
                             horizontal=True, key="crit_top_prod")
    crit_map = {"Faturamento": "faturamento", "Quantidade": "quantidade", "Lucro Bruto (estimado)": "lucro"}
    top_prod = get_top_produtos(df_itens, crit_map[criterio_prod], top_n=10)
    if top_prod.empty:
        st.info("Sem itens vendidos no período/filtros selecionados.")
    else:
        tp = top_prod.rename(columns={"PRODUTO": "Produto", "Quantidade": "Quantidade",
                                       "Faturamento": "Faturamento", "Lucro_Bruto": "Lucro Bruto"}).copy()
        for col in ("Faturamento", "Lucro Bruto"):
            tp[col] = tp[col].apply(fmt_brl)
        st.dataframe(tp[["Produto", "Quantidade", "Faturamento", "Lucro Bruto"]],
                     use_container_width=True, hide_index=True)

    st.divider()
    col_sem, col_queda = st.columns(2)
    with col_sem:
        st.markdown(section_header("Clientes sem comprar", "alertas", 4), unsafe_allow_html=True)
        faixa_dias = st.selectbox("A partir de quantos dias sem comprar?",
                                  [30, 60, 90, 180], index=0, key="faixa_sem_comprar")
        df_ultima = _carregar_ultima_compra()
        sem_comprar = get_clientes_sem_comprar(df_ultima, faixa_dias)
        st.metric(f"Clientes há +{faixa_dias} dias sem comprar", len(sem_comprar))
        if not sem_comprar.empty:
            sc = sem_comprar[["NOME_CLIENTE", "ULTIMA_COMPRA", "DIAS_SEM_COMPRAR", "TOTAL_HISTORICO"]].head(30).copy()
            sc["ULTIMA_COMPRA"] = sc["ULTIMA_COMPRA"].dt.strftime("%d/%m/%Y")
            sc["TOTAL_HISTORICO"] = sc["TOTAL_HISTORICO"].apply(fmt_brl)
            sc["FAIXA"] = sem_comprar["DIAS_SEM_COMPRAR"].head(30).apply(classifica_faixa_sem_comprar)
            st.dataframe(sc.rename(columns={"NOME_CLIENTE": "Cliente", "ULTIMA_COMPRA": "Última compra",
                "DIAS_SEM_COMPRAR": "Dias", "TOTAL_HISTORICO": "Total histórico", "FAIXA": "Faixa"}),
                use_container_width=True, hide_index=True, height=300)
        else:
            st.success("Nenhum cliente nessa faixa.")

    with col_queda:
        st.markdown(section_header("Clientes com queda de compras", "alertas", 4), unsafe_allow_html=True)
        st.caption("Top 10 — média mensal (6 meses) vs últimos 30 dias")
        queda = _carregar_queda()
        if queda.empty:
            st.info("Sem clientes com queda identificável no histórico disponível.")
        else:
            q = queda[["NOME_CLIENTE", "Media_6m", "Ultimos_30d", "Queda_%", "Valor_Perdido"]].copy()
            for col in ("Media_6m", "Ultimos_30d", "Valor_Perdido"):
                q[col] = q[col].apply(fmt_brl)
            q["Queda_%"] = q["Queda_%"].apply(lambda v: f"{v:.1f}%")
            st.dataframe(q.rename(columns={"NOME_CLIENTE": "Cliente", "Media_6m": "Média 6m",
                "Ultimos_30d": "Últimos 30d", "Queda_%": "Queda", "Valor_Perdido": "Valor perdido (estim.)"}),
                use_container_width=True, hide_index=True, height=300)

    st.divider()
    secoes_cli = {"Top Clientes": top_cli, "Top Produtos": top_prod,
                  "Novos vs Recorrentes": novos_rec["dados"]}
    kpis_cli_exp = {"Clientes atendidos": str(kpis["n_clientes"]),
                    "Clientes novos no período": str(novos_rec["novos"]),
                    "Clientes recorrentes no período": str(novos_rec["recorrentes"])}
    _toolbar_export("Clientes", secoes_cli, kpis_cli_exp, data_ini, data_fim, "clientes")
    _widget_comentario("clientes", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 4 — CONCENTRAÇÃO
# ══════════════════════════════════════════════════════════════════
with aba_conc:
    st.markdown(section_header("Concentração de Faturamento", "comparativo", 4), unsafe_allow_html=True)
    col_cc, col_cp = st.columns(2)

    def _conc_card(perc: float, top_n: int, total_itens: int, dim: str):
        """Renderiza um cartão com o % de concentração nos top N (barra de progresso colorida por faixa de risco)."""
        cor = COR_PERIGO if perc > 60 else (COR_ALERTA if perc > 40 else COR_OK)
        st.markdown(
            f"<div style='background:#f8f9fa;border-radius:8px;padding:12px 14px;margin-bottom:10px'>"
            f"<div style='display:flex;justify-content:space-between;align-items:baseline'>"
            f"<span style='font-size:2rem;font-weight:800;color:{cor};line-height:1'>{perc:.1f}%</span>"
            f"<span style='color:#888;font-size:0.82em'>top {top_n} de {total_itens} {dim}</span></div>"
            f"<div style='margin-top:6px;height:8px;border-radius:4px;background:#e9ecef;overflow:hidden'>"
            f"<div style='width:{min(perc,100):.1f}%;height:100%;background:{cor};border-radius:4px'></div></div>"
            f"<div style='display:flex;justify-content:space-between;margin-top:3px;"
            f"font-size:0.75em;color:#aaa'><span>0%</span><span>100%</span></div>"
            f"</div>",
            unsafe_allow_html=True)

    with col_cc:
        st.markdown("**Por Clientes (Top 10)**")
        cc = get_concentracao_clientes(df_fat, top_n=10)
        if cc["total"] > 0:
            _conc_card(cc["top_perc"], 10, cc["n_clientes"], "clientes")
            top10c = cc["dados"].head(10).copy()
            top10c["Valor"] = top10c["Valor"].apply(fmt_brl)
            st.dataframe(top10c, use_container_width=True, hide_index=True, height=320)
        else:
            st.info("Sem faturamento no período selecionado.")

    with col_cp:
        st.markdown("**Por Produtos (Top 20)**")
        cp = get_concentracao_produtos(df_itens, top_n=20)
        if cp["total"] > 0:
            _conc_card(cp["top_perc"], 20, cp["n_produtos"], "produtos")
            top20p = cp["dados"].head(20).copy()
            top20p["Valor"] = top20p["Valor"].apply(fmt_brl)
            st.dataframe(top20p, use_container_width=True, hide_index=True, height=320)
        else:
            st.info("Sem itens vendidos no período selecionado.")

    st.divider()
    st.markdown(section_header("Classificação ABC (Curva de Pareto)", "comparativo", 4), unsafe_allow_html=True)
    st.caption(
        f"{bi('info',13,'#888')} Classe **A** = itens que somam até 80% do faturamento acumulado, "
        f"**B** = de 80% a 95%, **C** = acima de 95% — referência clássica para priorizar foco "
        f"comercial, reposição de estoque e negociação com fornecedores.",
        unsafe_allow_html=True)
    col_abc_c, col_abc_p = st.columns(2)
    cc_abc = classifica_curva_abc(cc.get("dados", pd.DataFrame()))
    cp_abc = classifica_curva_abc(cp.get("dados", pd.DataFrame()))

    _ABC_CORES = {"A": COR_OK, "B": COR_ALERTA, "C": COR_PERIGO}
    _ABC_BG    = {"A": "#eaf7ea", "B": "#fef3e2", "C": "#fdecea"}

    def _render_abc(resumo: pd.DataFrame, dim_label: str):
        """Renderiza a tabela e o gráfico de barras da curva ABC (resumo já vem calculado em core.domain)."""
        if resumo.empty:
            st.info("Sem dados suficientes para classificação ABC.")
            return
        chart_key = f"abc_chart_{dim_label.lower()}"
        rows = ""
        for _, r in resumo.iterrows():
            cor  = _ABC_CORES.get(r["Classe"], "#888")
            bg   = _ABC_BG.get(r["Classe"], "#fff")
            rows += (
                f"<tr style='background:{bg}'>"
                f"<td style='font-weight:700;color:{cor};padding:6px 10px'>{r['Classe']}</td>"
                f"<td style='padding:6px 10px;text-align:right'>{int(r['Itens'])}</td>"
                f"<td style='padding:6px 10px;text-align:right'>{fmt_brl(r['Valor'])}</td>"
                f"<td style='padding:6px 10px;text-align:right;font-weight:600;color:{cor}'>"
                f"{r['% do Valor']:.1f}%</td></tr>"
            )
        st.markdown(
            f"<table style='width:100%;border-collapse:collapse;font-size:0.88em'>"
            f"<thead><tr style='border-bottom:2px solid #ddd'>"
            f"<th style='padding:6px 10px;text-align:left'>Classe</th>"
            f"<th style='padding:6px 10px;text-align:right'>{dim_label}</th>"
            f"<th style='padding:6px 10px;text-align:right'>Faturamento</th>"
            f"<th style='padding:6px 10px;text-align:right'>% Faturamento</th>"
            f"</tr></thead><tbody>{rows}</tbody></table>",
            unsafe_allow_html=True)
        fig_abc = px.bar(resumo, x="Classe", y="% do Valor", color="Classe",
                         color_discrete_map=_ABC_CORES, text_auto=".1f")
        fig_abc.update_traces(textposition="outside", textfont_size=12)
        fig_abc.update_layout(height=220, margin=dict(t=20, b=0), showlegend=False,
                              yaxis_title="% do faturamento", yaxis_range=[0, 105])
        st.plotly_chart(fig_abc, use_container_width=True, key=chart_key)

    with col_abc_c:
        st.markdown("**Clientes**")
        resumo_cc = resumo_curva_abc(cc_abc)
        _render_abc(resumo_cc, "Clientes")

    with col_abc_p:
        st.markdown("**Produtos**")
        resumo_cp = resumo_curva_abc(cp_abc)
        _render_abc(resumo_cp, "Produtos")

    st.divider()
    secoes_conc = {"Concentração Clientes (ABC)": cc_abc,
                   "Concentração Produtos (ABC)": cp_abc,
                   "Resumo ABC Clientes": resumo_cc,
                   "Resumo ABC Produtos": resumo_cp}
    _toolbar_export("Concentração", secoes_conc, {}, data_ini, data_fim, "concentracao")
    _widget_comentario("concentracao", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 5 — SAZONALIDADE
# ══════════════════════════════════════════════════════════════════
with aba_saz:
    st.markdown(section_header("Sazonalidade — últimos 24 meses", "calendario", 4), unsafe_allow_html=True)
    saz = _carregar_sazonalidade()
    if saz.empty:
        st.info("Sem histórico suficiente para análise de sazonalidade.")
    else:
        fig_saz = go.Figure()
        fig_saz.add_trace(go.Bar(x=saz["MES_ANO"], y=saz["FATURAMENTO"],
                                 marker_color=COR_PRIM, name="Faturamento"))
        fig_saz.update_layout(height=340, margin=dict(t=10, b=0), yaxis_title="R$ Faturamento")
        st.plotly_chart(fig_saz, use_container_width=True)

        st.caption(
            f"{bi('info',13,'#888')} Séries de **compras** e **margem bruta mensal** "
            f"dependem do módulo Compras (ainda não implementado) — ver "
            f"`docs/MODULO_COMERCIAL.md`.",
            unsafe_allow_html=True)

        s_exib = saz[["MES_ANO", "FATURAMENTO", "QTD_PEDIDOS"]].copy()
        s_exib["FATURAMENTO"] = s_exib["FATURAMENTO"].apply(fmt_brl)
        st.dataframe(s_exib.rename(columns={"MES_ANO": "Mês/Ano", "FATURAMENTO": "Faturamento",
            "QTD_PEDIDOS": "Pedidos"}), use_container_width=True, hide_index=True, height=280)

    st.divider()
    secoes_saz = {"Sazonalidade": saz[["MES_ANO", "FATURAMENTO", "QTD_PEDIDOS"]] if not saz.empty else pd.DataFrame()}
    _toolbar_export("Sazonalidade", secoes_saz, {}, data_ini, data_fim, "sazonalidade")
    _widget_comentario("sazonalidade", data_ini, data_fim)


# ══════════════════════════════════════════════════════════════════
#  ABA 6 — CONFIGURAÇÕES
# ══════════════════════════════════════════════════════════════════
with aba_cfg:
    st.markdown(section_header("Meta de Faturamento Mensal", "config", 4), unsafe_allow_html=True)
    st.caption(
        f"{bi('info',13,'#888')} A tabela `METAFATURAMENTOMENSAL` do ERP está vazia neste banco — "
        f"a meta é configurada manualmente aqui e usada como referência até o cliente passar a "
        f"cadastrá-la no sistema.")

    meta_atual = float(get_config("meta_faturamento_mensal", 0) or 0)
    nova_meta = st.number_input("Meta de faturamento do mês (R$)", min_value=0.0,
                                value=meta_atual, step=1000.0, format="%.2f", key="cfg_meta")
    if st.button("💾 Salvar meta", key="salvar_meta"):
        if set_config("meta_faturamento_mensal", str(nova_meta)):
            st.success("Meta salva! Ela será usada como referência sempre que a base do ERP estiver vazia.")
            st.rerun()
        else:
            st.error("Não foi possível salvar a meta. Tente novamente.")
