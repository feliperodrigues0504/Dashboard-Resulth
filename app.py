"""
Tela Inicial — Dashboard Executivo
KPIs consolidados · Alertas · Faturamento recente · Histórico · Módulos
"""
import os
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import date

from components.bi_icons import inject_bi, bi, section_header
from components.print_btn import render_print_css, render_print_button
from components.metrics import fmt_brl, kpi_card
from components.theme import COR_PRIM, COR_OK, COR_ALERTA, COR_PERIGO
from components.freshness import marcar_frescor, rotulo_frescor
from components.sidebar_filtros import carregar_opcoes_filtros
from core.domain.spotlight import perfil_cliente, perfil_fornecedor
from core.data.duckdb_store import init_store, get_preferencia, set_preferencia

st.set_page_config(
    page_title="Cetel — Dashboard Executivo",
    page_icon="🏠",
    layout="wide",
)
init_store()

# ── Agendador de snapshots diários (singleton por processo Streamlit) ─────────
try:
    from core.sync.agendador import iniciar_agendador
    iniciar_agendador()
except Exception:
    pass

render_print_css()
inject_bi()


# ══════════════════════════════════════════════════════════════════
#  CACHE — Dados consolidados para o home
# ══════════════════════════════════════════════════════════════════
@st.cache_data(ttl=600, show_spinner=False)
def _home_financeiro():
    """Carrega AR, AP, saldo bancário e os KPIs consolidados do Financeiro para os cards do home."""
    marcar_frescor("home_financeiro")
    try:
        from core.domain.financeiro import (
            get_contas_receber, get_contas_pagar,
            get_saldo_bancario, get_estoque_custo, get_kpis,
        )
        df_ar   = get_contas_receber()
        df_ap   = get_contas_pagar()
        df_bco  = get_saldo_bancario()
        estoque = get_estoque_custo()
        kpis    = get_kpis(df_ar, df_ap, estoque, df_bco)
        return kpis, df_ar, df_ap, df_bco
    except Exception:
        return {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def _home_faturamento():
    """Carrega o faturamento dos últimos 2 meses, usado nos gráficos rápidos do home."""
    marcar_frescor("home_faturamento")
    try:
        from core.domain.comercial import get_faturamento
        df = get_faturamento(meses_historico=2)
        if not df.empty:
            df["DATAFATURA"] = pd.to_datetime(df["DATAFATURA"], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def _home_estoque():
    """Carrega os KPIs consolidados de estoque para o card do home."""
    marcar_frescor("home_estoque")
    try:
        from core.domain.estoque import get_kpis_estoque
        return get_kpis_estoque()
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def _home_alertas():
    """Carrega todos os alertas ativos (últimos 3 meses + 1 dia futuro) e o resumo por nível/módulo, para o painel de alertas do home."""
    marcar_frescor("home_alertas")
    try:
        from core.domain.alertas import get_todos_alertas, resumo_alertas
        ini  = (pd.Timestamp.now() - pd.DateOffset(months=3)).strftime("%Y-%m-%d")
        fim  = (pd.Timestamp.now() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        todos = get_todos_alertas(ini, fim)
        return todos, resumo_alertas(todos)
    except Exception:
        return [], {"total": 0, "criticos": 0, "urgentes": 0, "atencoes": 0, "por_modulo": {}}


@st.cache_data(ttl=600, show_spinner=False)
def _home_meta():
    """Carrega a meta de faturamento do mês e a projeção de fechamento, para o termômetro de meta do home."""
    marcar_frescor("home_meta")
    try:
        from core.domain.comercial import get_meta_mes, get_projecao_fechamento_mes, get_faturamento
        from core.data.duckdb_store import get_config
        meta_configurada = float(get_config("meta_faturamento_mensal", 0) or 0)
        meta_info = get_meta_mes(meta_configurada)
        df = get_faturamento(meses_historico=1)
        if not df.empty:
            df["DATAFATURA"] = pd.to_datetime(df["DATAFATURA"], errors="coerce")
        proj = get_projecao_fechamento_mes(df)
        return meta_info, proj
    except Exception:
        return ({"meta": 0.0, "fonte": "", "mes_ano": ""},
                {"total_ate_hoje": 0.0, "projecao": 0.0, "dias_passados": 0, "dias_no_mes": 30})


@st.cache_data(ttl=600, show_spinner=False)
def _home_fat_mes():
    """Calcula o faturamento do mês corrente e do mês anterior (para o comparativo do KPI de faturamento no home)."""
    try:
        from core.domain.comercial import get_faturamento
        df = get_faturamento(meses_historico=2)
        if df.empty:
            return 0.0, 0.0
        df["DATAFATURA"] = pd.to_datetime(df["DATAFATURA"], errors="coerce")
        hoje      = pd.Timestamp.now()
        ini_m     = pd.Timestamp(hoje.year, hoje.month, 1)
        ini_m_ant = ini_m - pd.DateOffset(months=1)
        fat_mes = float(df[df["DATAFATURA"] >= ini_m]["TOTALPEDIDO"].sum())
        fat_ant = float(df[(df["DATAFATURA"] >= ini_m_ant) & (df["DATAFATURA"] < ini_m)]["TOTALPEDIDO"].sum())
        return fat_mes, fat_ant
    except Exception:
        return 0.0, 0.0


@st.cache_data(ttl=1800, show_spinner=False)
def _home_historico():
    """Retorna série histórica de KPIs do DuckDB (pode estar vazia no início)."""
    try:
        from core.sync.snapshot import get_evolucao_kpis, get_evolucao_inadimplencia
        df_kpis  = get_evolucao_kpis()
        df_inadimp = get_evolucao_inadimplencia()
        return df_kpis, df_inadimp
    except Exception:
        return pd.DataFrame(), pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def _home_status_snapshot():
    """Verifica se o snapshot diário está em dia ou atrasado (badge na seção Sistema)."""
    try:
        from core.sync.snapshot import status_snapshot
        return status_snapshot()
    except Exception:
        return {"ultima_data": None, "dias_atraso": None, "atrasado": True}


# ── Carrega dados ─────────────────────────────────────────────────
with st.spinner("Carregando painel executivo…"):
    kpis_fin, df_ar, df_ap, df_bco = _home_financeiro()
    df_fat           = _home_faturamento()
    kpis_est         = _home_estoque()
    alertas, res_al  = _home_alertas()
    fat_mes, fat_ant = _home_fat_mes()
    meta_info, proj_meta = _home_meta()
    df_kpis_hist, df_inadimp_hist = _home_historico()
    status_snap      = _home_status_snapshot()

    from core.sync.snapshot import get_comparativo_diario
    comparativo_ontem = get_comparativo_diario(kpis_fin, fat_mes)
    opcoes_busca = carregar_opcoes_filtros()


# ══════════════════════════════════════════════════════════════════
#  SIDEBAR — Preferências
# ══════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(f"### {bi('gear',16,COR_PRIM)} Preferências", unsafe_allow_html=True)
    st.caption("Escolha quais seções exibir na tela inicial.")

    def _pref(key: str, label: str, default: bool = True) -> bool:
        """Renderiza um checkbox de preferência ligado ao DuckDB: lê o valor salvo, grava de volta se o usuário mudar."""
        valor_atual = get_preferencia(key, "true" if default else "false") == "true"
        novo = st.checkbox(label, value=valor_atual, key=f"pref_{key}")
        if novo != valor_atual:
            set_preferencia(key, "true" if novo else "false")
        return novo

    show_busca    = _pref("home_busca",     "Busca Global (Spotlight)")
    show_mudou    = _pref("home_mudou",     "O que mudou desde ontem")
    show_kpis     = _pref("home_kpis",      "KPIs Executivos")
    show_alertas  = _pref("home_alertas",   "Alertas Ativos")
    show_graficos = _pref("home_graficos",  "Gráficos Rápidos")
    show_historico= _pref("home_historico", "Histórico de KPIs", default=True)
    show_modulos  = _pref("home_modulos",   "Módulos do Sistema")
    show_relatorio= _pref("home_relatorio", "Relatório Executivo")

    st.divider()
    st.markdown(f"### {bi('info',16,'#888')} Sistema", unsafe_allow_html=True)
    st.caption(rotulo_frescor("home_financeiro", "home_faturamento", "home_estoque", "home_alertas"))
    st.caption("Banco: Resulth (Firebird 2.5) · R/O")
    st.caption("Store analítico: DuckDB")

    # Badge de saúde do snapshot diário (tentativas via APScheduler às 08:00,
    # 11:00 e 15:00 — ver core/sync/agendador.py) — sinaliza visualmente
    # quando as 3 tentativas falharam por 2+ dias, em vez de só aparecer
    # como uma lacuna no gráfico de Histórico (ver README, seção
    # "Limitações conhecidas").
    if status_snap["ultima_data"] is None:
        st.markdown(
            f"<small style='color:#888'>{bi('clock-history',13,'#888')} "
            f"Snapshot: ainda sem coleta</small>", unsafe_allow_html=True)
    elif status_snap["atrasado"]:
        st.markdown(
            f"<small style='color:{COR_PERIGO};font-weight:600'>"
            f"{bi('exclamation-triangle-fill',13,COR_PERIGO)} "
            f"Snapshot atrasado — {status_snap['dias_atraso']} dias sem coleta "
            f"(última: {status_snap['ultima_data'].strftime('%d/%m')})</small>",
            unsafe_allow_html=True)
    else:
        st.markdown(
            f"<small style='color:{COR_OK}'>{bi('check-circle-fill',13,COR_OK)} "
            f"Snapshot em dia (última: {status_snap['ultima_data'].strftime('%d/%m')}, "
            f"coleta às 08h/11h/15h)</small>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
#  CABEÇALHO
# ══════════════════════════════════════════════════════════════════
col_head, col_print = st.columns([11, 1])
with col_head:
    if res_al["criticos"] > 0:
        badge_cor = COR_PERIGO; badge_txt = f"{res_al['criticos']} crítico(s)"
    elif res_al["urgentes"] > 0:
        badge_cor = COR_ALERTA; badge_txt = f"{res_al['urgentes']} urgente(s)"
    else:
        badge_cor = COR_OK; badge_txt = "Sem alertas críticos"

    st.markdown(
        f"<div style='padding:0 0 8px 0;border-bottom:2px solid {COR_PRIM};margin-bottom:20px'>"
        f"  <h1 style='margin:0;color:#1a1a2e;display:flex;align-items:center;gap:10px'>"
        f"    {bi('house-fill',28,COR_PRIM)} Cetel — Painel Executivo"
        f"  </h1>"
        f"  <p style='margin:4px 0 0;color:#666;font-size:0.88em'>"
        f"    {bi('calendar3',13,'#999')} {rotulo_frescor('home_financeiro','home_faturamento','home_estoque','home_alertas')}"
        f"    &nbsp;·&nbsp;"
        f"    <span style='color:{badge_cor};font-weight:600'>"
        f"      {bi('bell-fill',13,badge_cor)} {badge_txt}"
        f"    </span>"
        f"  </p>"
        f"</div>",
        unsafe_allow_html=True)
with col_print:
    st.markdown("<div style='margin-top:12px'>", unsafe_allow_html=True)
    render_print_button(key="print_home")
    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
#  BUSCA GLOBAL (SPOTLIGHT) — perfil de cliente/fornecedor cruzando módulos
# ══════════════════════════════════════════════════════════════════
if show_busca:
    st.markdown(section_header("Busca Global", "search", 4), unsafe_allow_html=True)

    col_tipo, col_nome = st.columns([2, 6])
    with col_tipo:
        tipo_busca = st.radio("Buscar", ["Cliente", "Fornecedor"], horizontal=True,
                              key="spotlight_tipo", label_visibility="collapsed")
    with col_nome:
        if tipo_busca == "Cliente":
            opcoes_nome = opcoes_busca.get("clientes_df", pd.DataFrame(columns=["COD", "NOME"]))
        else:
            opcoes_nome = opcoes_busca.get("fornecedores_df", pd.DataFrame(columns=["COD", "NOME"]))
        nome_sel = st.selectbox(
            "Nome", opcoes_nome["NOME"].tolist() if not opcoes_nome.empty else [],
            index=None, placeholder=f"Digite o nome do {tipo_busca.lower()}…",
            key="spotlight_nome", label_visibility="collapsed")

    if nome_sel:
        cod_sel = opcoes_nome.loc[opcoes_nome["NOME"] == nome_sel, "COD"].iloc[0]

        if tipo_busca == "Cliente":
            p = perfil_cliente(cod_sel, nome_sel)
            p1, p2, p3, p4 = st.columns(4)
            with p1:
                kpi_card("Saldo em aberto", p["total_aberto"], cor=COR_PRIM)
            with p2:
                kpi_card("Saldo vencido", p["total_vencido"],
                         cor=COR_PERIGO if p["total_vencido"] > 0 else COR_OK)
            with p3:
                kpi_card("Títulos vencidos", p["titulos_vencidos"],
                         cor=COR_PERIGO if p["titulos_vencidos"] > 0 else COR_OK,
                         fmt=lambda v: f"{v:,.0f}")
            with p4:
                ult = p["ultima_compra"].strftime("%d/%m/%Y") if p["ultima_compra"] is not None and pd.notna(p["ultima_compra"]) else "—"
                dias_txt = f" ({p['dias_sem_comprar']}d atrás)" if p["dias_sem_comprar"] else ""
                st.markdown(
                    f"<div style='background:#f8f9fa;border-radius:8px;padding:14px 16px;"
                    f"border-top:4px solid {COR_PRIM};text-align:center'>"
                    f"  <div style='font-size:1.1em;font-weight:700;color:{COR_PRIM}'>{ult}</div>"
                    f"  <div style='color:#666;font-size:0.8em'>Última compra{dias_txt}</div>"
                    f"</div>", unsafe_allow_html=True)
            if p["situacao"]:
                st.warning(" · ".join(f"⚠️ {s}" for s in p["situacao"]))
            st.page_link("pages/01_Financeiro.py", label="Ver títulos no Financeiro →", icon="💰")
            st.page_link("pages/02_Comercial.py", label="Ver histórico no Comercial →", icon="📈")
        else:
            p = perfil_fornecedor(cod_sel, nome_sel)
            f1, f2, f3 = st.columns(3)
            with f1:
                kpi_card("Comprado (12m)", p["total_comprado_12m"], cor=COR_PRIM)
            with f2:
                kpi_card("Participação nas compras", p["participacao_pct"],
                         cor=COR_ALERTA if p["participacao_pct"] >= 25 else COR_PRIM,
                         fmt=lambda v: f"{v:.1f}%")
            with f3:
                kpi_card("Estoque parado (>90d)", p["estoque_parado_valor"],
                         cor=COR_PERIGO if p["estoque_parado_valor"] > 0 else COR_OK)
            st.page_link("pages/04_Compras.py", label="Ver detalhes em Compras →", icon="🛒")

    st.divider()


# ══════════════════════════════════════════════════════════════════
#  SEÇÃO 0 — O QUE MUDOU DESDE ONTEM (deltas do snapshot diário)
# ══════════════════════════════════════════════════════════════════
if show_mudou:
    st.markdown(section_header("O que mudou desde ontem", "arrow-left-right", 4), unsafe_allow_html=True)

    if comparativo_ontem is None:
        st.info("Ainda não há snapshot anterior para comparar — disponível a partir do 2º dia de coleta "
                "(snapshots automáticos às 08h/11h/15h).")
    else:
        ref_str = comparativo_ontem["data_referencia"].strftime("%d/%m")
        rotulo_ref = "ontem" if comparativo_ontem["dias_atras"] == 1 else f"{comparativo_ontem['dias_atras']} dias atrás ({ref_str})"
        st.caption(f"Comparado com {rotulo_ref}")

        def _delta_card(col, label: str, delta: float, bom_se_sobe: bool):
            """Card de variação: seta verde/vermelha conforme o delta for bom ou ruim para o negócio."""
            subiu = delta >= 0
            bom = subiu if bom_se_sobe else not subiu
            cor = COR_OK if bom else COR_PERIGO
            seta = "arrow-up-circle-fill" if subiu else "arrow-down-circle-fill"
            with col:
                st.markdown(
                    f"<div style='background:#f8f9fa;border-radius:8px;padding:12px 14px;"
                    f"border-top:4px solid {cor};text-align:center'>"
                    f"  <div style='font-size:1.3em;font-weight:700;color:{cor}'>"
                    f"    {bi(seta,16,cor)} {fmt_brl(abs(delta))}"
                    f"  </div>"
                    f"  <div style='color:#666;font-size:0.8em'>{label}</div>"
                    f"</div>", unsafe_allow_html=True)

        m1, m2, m3, m4 = st.columns(4)
        _delta_card(m1, "Caixa",          comparativo_ontem["delta_saldo_bco"],  bom_se_sobe=True)
        _delta_card(m2, "Faturamento mês", comparativo_ontem["delta_fat_mes"],    bom_se_sobe=True)
        _delta_card(m3, "AR Vencido",      comparativo_ontem["delta_vencido_ar"], bom_se_sobe=False)
        _delta_card(m4, "Capital Operacional", comparativo_ontem["delta_capital_op"], bom_se_sobe=True)

    st.divider()


# ══════════════════════════════════════════════════════════════════
#  SEÇÃO 1 — KPIs EXECUTIVOS
# ══════════════════════════════════════════════════════════════════
if show_kpis:
    st.markdown(section_header("KPIs Executivos", "bar-chart-fill", 4), unsafe_allow_html=True)

    # ── Termômetro de Meta — visão imediata sem precisar abrir o Comercial ──
    meta_valor = float(meta_info.get("meta", 0) or 0)
    if meta_valor > 0:
        total_hoje = proj_meta.get("total_ate_hoje", 0.0)
        projecao   = proj_meta.get("projecao", 0.0)
        eixo_max   = max(meta_valor * 1.2, projecao * 1.1, 1.0)
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=total_hoje,
            number={"valueformat": ",.0f", "prefix": "R$ "},
            delta={"reference": meta_valor, "valueformat": ",.0f", "increasing": {"color": COR_OK},
                   "decreasing": {"color": COR_PERIGO}},
            gauge={
                "axis": {"range": [0, eixo_max]},
                "bar": {"color": COR_PRIM},
                "steps": [
                    {"range": [0, meta_valor * 0.7], "color": "#fdf0f0"},
                    {"range": [meta_valor * 0.7, meta_valor], "color": "#fef6ed"},
                    {"range": [meta_valor, eixo_max], "color": "#e6f4ea"},
                ],
                "threshold": {"line": {"color": COR_PERIGO, "width": 3}, "thickness": 0.85, "value": meta_valor},
            },
            title={"text": (f"Meta do mês ({meta_info.get('mes_ano','')}) — "
                            f"projeção de fechamento: {fmt_brl(projecao)}"),
                   "font": {"size": 13}},
        ))
        fig_gauge.update_layout(height=200, margin=dict(l=30, r=30, t=55, b=10))
        st.plotly_chart(fig_gauge, use_container_width=True)
    else:
        st.caption(f"{bi('info',13,'#888')} Meta de faturamento ainda não configurada — "
                   f"defina em Comercial → Meta & Indicadores.", unsafe_allow_html=True)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    al_cor = COR_PERIGO if res_al["criticos"] > 0 else (COR_ALERTA if res_al["urgentes"] > 0 else COR_OK)
    with c1:
        st.markdown(
            f"<div style='background:#f8f9fa;border-radius:8px;padding:14px 16px;"
            f"border-top:4px solid {al_cor};text-align:center'>"
            f"  <div style='font-size:1.8em;font-weight:700;color:{al_cor}'>{res_al['total']}</div>"
            f"  <div style='color:#666;font-size:0.8em'>{bi('bell-fill',13,al_cor)} Alertas</div>"
            f"  <div style='font-size:0.75em;color:{al_cor};margin-top:2px'>"
            f"    {res_al['criticos']}C · {res_al['urgentes']}U · {res_al['atencoes']}A"
            f"  </div>"
            f"</div>", unsafe_allow_html=True)
    with c2:
        kpi_card("A Receber", kpis_fin.get("total_ar", 0), cor=COR_OK)
    with c3:
        kpi_card("Vencido AR", kpis_fin.get("vencido_ar", 0), cor=COR_PERIGO)
    with c4:
        kpi_card("Caixa", kpis_fin.get("saldo_bco", 0), cor=COR_OK)
    with c5:
        delta_fat = (fat_mes - fat_ant) if fat_ant > 0 else None
        delta_lbl = f"({(fat_mes - fat_ant) / fat_ant * 100:+.1f}% vs mês ant.)" if fat_ant > 0 else ""
        kpi_card("Fat. Mês", fat_mes, delta=delta_fat, delta_label=delta_lbl,
                 negativo_ruim=False, cor=COR_PRIM)
    with c6:
        kpi_card("Estoque Custo", kpis_est.get("valor_custo", 0), cor=COR_PRIM)

    st.markdown("<br>", unsafe_allow_html=True)
    s1, s2, s3, s4, s5, s6 = st.columns(6)
    with s1:
        kpi_card("AR a Vencer", kpis_fin.get("a_vencer_ar", 0), cor=COR_OK)
    with s2:
        kpi_card("A Pagar", kpis_fin.get("total_ap", 0), cor=COR_ALERTA)
    with s3:
        kpi_card("Vencido AP", kpis_fin.get("vencido_ap", 0), cor=COR_PERIGO)
    with s4:
        kpi_card("Capital Op.", kpis_fin.get("capital_op", 0), negativo_ruim=True, cor=COR_PRIM)
    with s5:
        kpi_card("SKUs em estoque", kpis_est.get("skus_com_estoque", 0),
                 cor=COR_PRIM, fmt=lambda v: f"{v:,.0f}")
    with s6:
        n_inat = 0
        try:
            from core.domain.comercial import get_ultima_compra_clientes, get_clientes_sem_comprar
            n_inat = len(get_clientes_sem_comprar(get_ultima_compra_clientes(), 60))
        except Exception:
            pass
        kpi_card("Clientes inat. 60d", n_inat,
                 cor=COR_ALERTA if n_inat > 0 else COR_OK, fmt=lambda v: f"{v:,.0f}")

    st.divider()


# ══════════════════════════════════════════════════════════════════
#  SEÇÃO 2 — ALERTAS ATIVOS
# ══════════════════════════════════════════════════════════════════
if show_alertas:
    _COR_AL = {"critico": COR_PERIGO, "urgente": COR_ALERTA, "atencao": "#f0b429"}
    _BG_AL  = {"critico": "#fdf0f0",  "urgente": "#fef6ed",  "atencao": "#fffbea"}
    _ICO_AL = {"critico": "exclamation-octagon-fill",
               "urgente": "exclamation-triangle-fill",
               "atencao": "info-circle-fill"}
    _LBL_AL = {"critico": "CRÍTICO", "urgente": "URGENTE", "atencao": "ATENÇÃO"}

    col_alh, col_all = st.columns([8, 2])
    with col_alh:
        st.markdown(section_header("Alertas Ativos", "bell-fill", 4), unsafe_allow_html=True)
    with col_all:
        st.markdown("<div style='margin-top:16px'>", unsafe_allow_html=True)
        st.page_link("pages/05_Alertas.py", label="Ver todos →", icon="🔔")
        st.markdown("</div>", unsafe_allow_html=True)

    if not alertas:
        st.success("✅ Nenhum alerta ativo. Todos os indicadores dentro dos parâmetros.")
    else:
        prioridade = [a for a in alertas if a["nivel"] in ("critico", "urgente")][:6]
        if not prioridade:
            prioridade = alertas[:4]
        col_al1, col_al2 = st.columns(2)
        for idx, a in enumerate(prioridade):
            n = a["nivel"]; cor = _COR_AL[n]; bg = _BG_AL[n]
            col = col_al1 if idx % 2 == 0 else col_al2
            with col:
                vstr = ""
                if a.get("valor") is not None and abs(a["valor"]) >= 1:
                    vstr = (f"<span style='float:right;color:{cor};font-weight:700'>"
                            f"{fmt_brl(abs(a['valor']))}</span>")
                st.markdown(
                    f"<div style='background:{bg};border-left:5px solid {cor};"
                    f"border-radius:6px;padding:12px 14px;margin-bottom:8px'>"
                    f"  <div style='display:flex;justify-content:space-between'>"
                    f"    <span style='font-size:0.78em;font-weight:700;color:{cor}'>"
                    f"      {bi(_ICO_AL[n],12,cor)} {_LBL_AL[n]} · {a['modulo']}"
                    f"    </span>{vstr}"
                    f"  </div>"
                    f"  <div style='font-weight:600;margin:3px 0;font-size:0.9em'>{a['titulo']}</div>"
                    f"  <div style='color:#666;font-size:0.82em'>{a['detalhe']}</div>"
                    f"</div>", unsafe_allow_html=True)
        if len(alertas) > len(prioridade):
            st.caption(f"+ {len(alertas) - len(prioridade)} alerta(s) de atenção — veja na página de Alertas.")

    st.divider()


# ══════════════════════════════════════════════════════════════════
#  SEÇÃO 3 — GRÁFICOS RÁPIDOS
# ══════════════════════════════════════════════════════════════════
if show_graficos:
    st.markdown(section_header("Visão Rápida", "graph-up", 4), unsafe_allow_html=True)
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown(f"**{bi('graph-up-arrow',14,COR_PRIM)} Faturamento — últimos 30 dias**",
                    unsafe_allow_html=True)
        if not df_fat.empty and "DATAFATURA" in df_fat.columns:
            corte = pd.Timestamp.now() - pd.Timedelta(days=30)
            df_30 = df_fat[df_fat["DATAFATURA"] >= corte].copy()
            if not df_30.empty:
                df_30["DIA"] = df_30["DATAFATURA"].dt.date
                fat_dia = (df_30.groupby("DIA")["TOTALPEDIDO"].sum()
                           .reset_index().rename(columns={"DIA": "Data", "TOTALPEDIDO": "Fat"}))
                fig = go.Figure(go.Bar(
                    x=fat_dia["Data"], y=fat_dia["Fat"],
                    marker_color=COR_PRIM,
                    text=fat_dia["Fat"].apply(lambda x: fmt_brl(x) if x > 0 else ""),
                    textposition="outside", textfont=dict(size=9),
                ))
                fig.update_layout(
                    title=f"Total 30d: {fmt_brl(fat_dia['Fat'].sum())}",
                    xaxis_title="", yaxis_title="R$", height=300,
                    margin=dict(l=5, r=5, t=40, b=5))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sem faturamento nos últimos 30 dias.")
        else:
            st.info("Dados de faturamento indisponíveis.")

    with col_g2:
        st.markdown(f"**{bi('financeiro',14,COR_PRIM)} Posição Financeira (AR vs AP)**",
                    unsafe_allow_html=True)
        t_ar  = kpis_fin.get("total_ar", 0)
        v_ar  = kpis_fin.get("vencido_ar", 0)
        av_ar = kpis_fin.get("a_vencer_ar", 0)
        t_ap  = kpis_fin.get("total_ap", 0)
        v_ap  = kpis_fin.get("vencido_ap", 0)
        av_ap = t_ap - v_ap
        if t_ar > 0 or t_ap > 0:
            fig2 = go.Figure()
            for lbl, x, y, cor in [
                ("AR Vencido", "A Receber", v_ar, COR_PERIGO),
                ("AR a Vencer", "A Receber", av_ar, "#5ba3d4"),
                ("AP Vencido", "A Pagar", v_ap, "#d6804f"),
                ("AP a Vencer", "A Pagar", av_ap, "#8fbf8f"),
            ]:
                fig2.add_trace(go.Bar(
                    name=lbl, x=[x], y=[y], marker_color=cor,
                    text=[fmt_brl(y)], textposition="inside",
                    textfont=dict(size=10, color="white")))
            fig2.update_layout(
                barmode="stack",
                title=f"Caixa: {fmt_brl(kpis_fin.get('saldo_bco', 0))}",
                yaxis_title="R$", height=300,
                margin=dict(l=5, r=5, t=40, b=5),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Dados financeiros indisponíveis.")

    st.divider()


# ══════════════════════════════════════════════════════════════════
#  SEÇÃO 4 — HISTÓRICO DE KPIs (snapshots diários)
# ══════════════════════════════════════════════════════════════════
if show_historico:
    st.markdown(section_header("Histórico de KPIs", "clock-history", 4), unsafe_allow_html=True)

    MIN_PONTOS = 3  # mínimo de dias para exibir gráfico histórico

    if df_kpis_hist.empty or len(df_kpis_hist) < MIN_PONTOS:
        n_dias = len(df_kpis_hist)
        st.info(
            f"📊 **Dados históricos sendo coletados.** "
            f"{'Primeiro snapshot gravado hoje.' if n_dias == 1 else f'{n_dias} dia(s) coletados até agora.'} "
            f"O gráfico aparecerá a partir de {MIN_PONTOS} dias de dados. "
            f"Os snapshots são gravados automaticamente (tentativas às 08h, 11h e 15h).")
    else:
        df_kpis_hist["data"] = pd.to_datetime(df_kpis_hist["data"])
        col_h1, col_h2 = st.columns(2)

        with col_h1:
            st.markdown("**Evolução — AR Vencido vs Caixa**")
            fh = go.Figure()
            fh.add_trace(go.Scatter(
                x=df_kpis_hist["data"], y=df_kpis_hist["vencido_ar"],
                name="AR Vencido", mode="lines+markers",
                line=dict(color=COR_PERIGO, width=2)))
            fh.add_trace(go.Scatter(
                x=df_kpis_hist["data"], y=df_kpis_hist["saldo_bco"],
                name="Caixa", mode="lines+markers",
                line=dict(color=COR_PRIM, width=2)))
            fh.update_layout(
                height=280, margin=dict(l=5, r=5, t=10, b=5),
                yaxis_title="R$",
                legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fh, use_container_width=True)

        with col_h2:
            st.markdown("**Evolução — Capital Operacional**")
            fh2 = go.Figure()
            fh2.add_trace(go.Scatter(
                x=df_kpis_hist["data"], y=df_kpis_hist["capital_op"],
                name="Capital Op.", mode="lines+markers",
                fill="tozeroy",
                line=dict(color=COR_OK if df_kpis_hist["capital_op"].iloc[-1] > 0 else COR_PERIGO, width=2)))
            fh2.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="Zero")
            fh2.update_layout(
                height=280, margin=dict(l=5, r=5, t=10, b=5),
                yaxis_title="R$", showlegend=False)
            st.plotly_chart(fh2, use_container_width=True)

    # Evolução de inadimplência (snap_inadimplencia)
    if not df_inadimp_hist.empty and len(df_inadimp_hist) >= MIN_PONTOS:
        st.markdown("**Evolução da Inadimplência (AR vencido por faixa)**")
        df_inadimp_hist["data"] = pd.to_datetime(df_inadimp_hist["data"])
        fi = go.Figure()
        for col_snap, label, cor in [
            ("faixa_1_30",  "1–30d", "#f0b429"),
            ("faixa_31_60", "31–60d", COR_ALERTA),
            ("faixa_61_90", "61–90d", "#c0392b"),
            ("faixa_90_mais","90d+",  COR_PERIGO),
        ]:
            if col_snap in df_inadimp_hist.columns:
                fi.add_trace(go.Bar(
                    x=df_inadimp_hist["data"], y=df_inadimp_hist[col_snap],
                    name=label, marker_color=cor))
        fi.update_layout(
            barmode="stack", height=280,
            yaxis_title="R$",
            margin=dict(l=5, r=5, t=10, b=5),
            legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fi, use_container_width=True)

    st.divider()


# ══════════════════════════════════════════════════════════════════
#  SEÇÃO 5 — MÓDULOS DO SISTEMA
# ══════════════════════════════════════════════════════════════════
if show_modulos:
    st.markdown(section_header("Módulos do Sistema", "grid", 4), unsafe_allow_html=True)

    MODULOS = [
        {
            "icone": "cash-coin", "nome": "Financeiro",
            "desc": "AR · AP · Fluxo de Caixa · PMR/PMP · Saldo Bancário · Drill-down completo",
            "link": "pages/01_Financeiro.py",
            "badge": (f"{fmt_brl(kpis_fin.get('vencido_ar',0))} vencido AR"
                      if kpis_fin.get("vencido_ar", 0) > 0 else None),
        },
        {
            "icone": "graph-up-arrow", "nome": "Comercial",
            "desc": "Faturamento · Metas · Ranking Vendedores · Funil · ABC Clientes · Sazonalidade",
            "link": "pages/02_Comercial.py",
            "badge": (f"Fat. mês: {fmt_brl(fat_mes)}" if fat_mes > 0 else None),
        },
        {
            "icone": "box-seam", "nome": "Estoque",
            "desc": "Top Produtos · Curva ABC · Estoque Parado · Giro por Grupo · Ruptura",
            "link": "pages/03_Estoque.py",
            "badge": (f"{kpis_est.get('skus_com_estoque',0):,} SKUs em estoque"
                      if kpis_est.get("skus_com_estoque", 0) > 0 else None),
        },
        {
            "icone": "cart", "nome": "Compras",
            "desc": "Evolução · Top Fornecedores · Dependência · Rentabilidade · Alertas",
            "link": "pages/04_Compras.py",
            "badge": None,
        },
        {
            "icone": "bell-fill", "nome": "Alertas",
            "desc": "Painel consolidado — Crítico / Urgente / Atenção — todos os módulos",
            "link": "pages/05_Alertas.py",
            "badge": (f"{res_al['criticos']} crítico(s)"
                      if res_al["criticos"] > 0 else f"{res_al['total']} alerta(s)"),
        },
    ]

    cols = st.columns(3)
    for i, mod in enumerate(MODULOS):
        badge_html = ""
        if mod["badge"]:
            badge_html = (
                f"<div style='margin-top:8px'>"
                f"<span style='background:#e6f4ea;color:{COR_OK};border-radius:4px;"
                f"padding:2px 8px;font-size:0.78em;font-weight:600'>{mod['badge']}</span></div>")
        with cols[i % 3]:
            st.markdown(
                f"<div style='border:1px solid #d0e3f5;border-radius:10px;padding:18px 16px;"
                f"margin-bottom:14px;background:#f0f7ff;"
                f"box-shadow:0 1px 4px rgba(31,107,181,0.08)'>"
                f"  <div style='display:flex;align-items:center;gap:10px;margin-bottom:6px'>"
                f"    {bi(mod['icone'],24,COR_PRIM)}"
                f"    <strong style='font-size:1.05em;color:#1a1a2e'>{mod['nome']}</strong>"
                f"  </div>"
                f"  <p style='color:#555;margin:0;font-size:0.88em;line-height:1.45'>{mod['desc']}</p>"
                f"  {badge_html}"
                f"</div>", unsafe_allow_html=True)
            st.page_link(mod["link"], label=f"Abrir {mod['nome']}", icon="▶️")

    st.divider()


# ══════════════════════════════════════════════════════════════════
#  SEÇÃO 6 — RELATÓRIO EXECUTIVO CONSOLIDADO
# ══════════════════════════════════════════════════════════════════
if show_relatorio:
    st.markdown(section_header("Relatório Executivo", "file-earmark-pdf", 4), unsafe_allow_html=True)
    st.caption("PDF consolidado — Financeiro, Comercial, Estoque e Alertas críticos. "
               "Gerado automaticamente toda segunda-feira às 07:00, ou a qualquer momento abaixo.")

    from core.domain.relatorio_executivo import gerar_relatorio_executivo, ultimo_relatorio

    col_rel1, col_rel2 = st.columns(2)
    with col_rel1:
        if st.button("🔄 Gerar agora", key="gerar_relatorio_agora"):
            with st.spinner("Consolidando dados dos 4 módulos…"):
                pdf_bytes = gerar_relatorio_executivo()
            st.download_button(
                "📄 Baixar relatório gerado agora", data=bytes(pdf_bytes),
                file_name=f"relatorio_executivo_{date.today()}.pdf",
                mime="application/pdf", key="download_relatorio_agora")
    with col_rel2:
        ultimo = ultimo_relatorio()
        if ultimo:
            st.download_button(
                f"📄 Baixar último relatório automático ({ultimo['data']})",
                data=ultimo["bytes"],
                file_name=os.path.basename(ultimo["caminho"]),
                mime="application/pdf", key="download_ultimo_relatorio")
        else:
            st.caption("Nenhum relatório automático gravado ainda — o primeiro sai na próxima segunda-feira às 07h.")

    st.divider()


# ══════════════════════════════════════════════════════════════════
#  RODAPÉ
# ══════════════════════════════════════════════════════════════════
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"<small style='color:#888'>{bi('database',13,COR_PRIM)} "
                f"Resulth · Firebird 2.5 · Somente leitura</small>", unsafe_allow_html=True)
with c2:
    n_snaps = len(df_kpis_hist)
    st.markdown(f"<small style='color:#888'>{bi('arrow-clockwise',13,COR_PRIM)} "
                f"Cache: 5–10 min · {n_snaps} snapshot(s) coletados</small>", unsafe_allow_html=True)
with c3:
    st.markdown(f"<small style='color:#888'>{bi('gear',13,COR_PRIM)} "
                f"Python · Streamlit · DuckDB · Plotly · APScheduler</small>", unsafe_allow_html=True)
with c4:
    st.markdown(f"<small style='color:#888'>{bi('info',13,COR_PRIM)} "
                f"v{date.today().strftime('%Y.%m')} · Felipe Rodrigues</small>", unsafe_allow_html=True)
