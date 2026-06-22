"""
Módulo Alertas — Painel Consolidado
Agrega sinais de todos os módulos (Financeiro, Comercial, Estoque, Compras)
em uma única tela de gestão por exceção.
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import date

from components.bi_icons import inject_bi, bi, section_header
from components.sidebar_filtros import render_sidebar
from components.print_btn import render_print_css, render_print_button
from components.metrics import fmt_brl
from components.theme import NIVEL_STYLE, NIVEL_LABEL
from core.data.repositories.cadastros_repo import fetch_opcoes_filtros
from core.data.duckdb_store import init_store
from core.domain.alertas import get_todos_alertas, resumo_alertas, CFG

st.set_page_config(page_title="Alertas", page_icon="🚨", layout="wide")
init_store()
render_print_css()
inject_bi()

# ── Paleta de cores por nível (fonte única: components/theme.py) ─────────────
_BG   = {k: v[0] for k, v in NIVEL_STYLE.items()}
_COR  = {k: v[1] for k, v in NIVEL_STYLE.items()}
_ICON = {k: v[2] for k, v in NIVEL_STYLE.items()}
_LABEL = NIVEL_LABEL

# ── Ícones por módulo ─────────────────────────────────────────────────────────
_MOD_ICON = {
    "Financeiro": "cash-coin",
    "Comercial":  "graph-up-arrow",
    "Estoque":    "box-seam",
    "Compras":    "cart",
}
_MOD_URL = {
    "Financeiro": "Financeiro",
    "Comercial":  "Comercial",
    "Estoque":    "Estoque",
    "Compras":    "Compras",
}


# ══════════════════════════════════════════════════════════════════
#  CACHE
# ══════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner="Verificando alertas…")
def _carregar_alertas(ini: str, fim: str):
    """Avalia todas as regras de alerta (Financeiro, Comercial, Estoque, Compras) para o período informado."""
    return get_todos_alertas(ini, fim)

@st.cache_data(ttl=3600, show_spinner=False)
def _carregar_opcoes():
    """Carrega as opções de filtro (cadastros) e as deixa em session_state para components.sidebar_filtros usar."""
    opc = fetch_opcoes_filtros()
    st.session_state["opcoes_cadastros"] = opc
    return opc


try:
    opcoes = _carregar_opcoes()
except Exception as e:
    st.error(f"Erro ao conectar ao banco: {e}"); st.stop()

# ── Sidebar ───────────────────────────────────────────────────────
filtros  = render_sidebar(opcoes)
data_ini: date = filtros["data_ini"]
data_fim: date = filtros["data_fim"]

_ini_str = data_ini.strftime("%Y-%m-%d")
_fim_str = (pd.Timestamp(data_fim) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

# ── Carregar alertas ──────────────────────────────────────────────
with st.spinner("Analisando indicadores…"):
    alertas = _carregar_alertas(_ini_str, _fim_str)

resumo = resumo_alertas(alertas)

# ── Cabeçalho ─────────────────────────────────────────────────────
col_titulo, col_print = st.columns([9, 1])
with col_titulo:
    st.markdown(
        f"<h1 style='margin:0;display:flex;align-items:center;gap:10px'>"
        f"{bi('bell-fill',28,'#d62728')} Alertas</h1>"
        f"<p style='margin:2px 0 0;color:#888;font-size:0.88em'>"
        f"Gestão por exceção — todos os módulos · "
        f"{pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}</p>",
        unsafe_allow_html=True)
with col_print:
    st.markdown("<div style='margin-top:12px'>", unsafe_allow_html=True)
    render_print_button(key="print_alertas")
    st.markdown("</div>", unsafe_allow_html=True)

# ── KPI Cards por nível ────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1:
    cor_tot = "#d62728" if resumo["criticos"] > 0 else ("#e67e22" if resumo["urgentes"] > 0 else "#2ca02c")
    st.markdown(
        f"<div style='background:#f8f9fa;border-radius:8px;padding:16px;text-align:center;"
        f"border-top:4px solid {cor_tot}'>"
        f"<div style='font-size:2.2em;font-weight:700;color:{cor_tot}'>{resumo['total']}</div>"
        f"<div style='color:#666;font-size:0.85em'>Total de alertas</div>"
        f"</div>", unsafe_allow_html=True)
with c2:
    cor = "#d62728" if resumo["criticos"] > 0 else "#aaa"
    st.markdown(
        f"<div style='background:#fdf0f0;border-radius:8px;padding:16px;text-align:center;"
        f"border-top:4px solid {cor}'>"
        f"<div style='font-size:2.2em;font-weight:700;color:{cor}'>{resumo['criticos']}</div>"
        f"<div style='color:#666;font-size:0.85em'>{bi('exclamation-octagon-fill',13,cor)} Críticos</div>"
        f"</div>", unsafe_allow_html=True)
with c3:
    cor = "#e67e22" if resumo["urgentes"] > 0 else "#aaa"
    st.markdown(
        f"<div style='background:#fef6ed;border-radius:8px;padding:16px;text-align:center;"
        f"border-top:4px solid {cor}'>"
        f"<div style='font-size:2.2em;font-weight:700;color:{cor}'>{resumo['urgentes']}</div>"
        f"<div style='color:#666;font-size:0.85em'>{bi('exclamation-triangle-fill',13,cor)} Urgentes</div>"
        f"</div>", unsafe_allow_html=True)
with c4:
    cor = "#f0b429" if resumo["atencoes"] > 0 else "#aaa"
    st.markdown(
        f"<div style='background:#fffbea;border-radius:8px;padding:16px;text-align:center;"
        f"border-top:4px solid {cor}'>"
        f"<div style='font-size:2.2em;font-weight:700;color:{cor}'>{resumo['atencoes']}</div>"
        f"<div style='color:#666;font-size:0.85em'>{bi('info-circle-fill',13,cor)} Atenção</div>"
        f"</div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

if resumo["total"] == 0:
    st.success("✅ Nenhum alerta ativo no momento. Todos os indicadores dentro dos parâmetros.")
    st.stop()

# ══════════════════════════════════════════════════════════════════
#  ABAS
# ══════════════════════════════════════════════════════════════════
aba_todos, aba_fin, aba_com, aba_est, aba_cmp, aba_cfg = st.tabs([
    f"🔔 Todos ({resumo['total']})",
    f"💰 Financeiro ({resumo['por_modulo'].get('Financeiro', 0)})",
    f"📈 Comercial ({resumo['por_modulo'].get('Comercial', 0)})",
    f"📦 Estoque ({resumo['por_modulo'].get('Estoque', 0)})",
    f"🛒 Compras ({resumo['por_modulo'].get('Compras', 0)})",
    "⚙️ Configurações",
])


def _render_card(alerta: dict):
    """Renderiza um card de alerta individual."""
    n     = alerta["nivel"]
    cor   = _COR[n]
    bg    = _BG[n]
    icone = alerta.get("icone", _ICON[n])
    mod   = alerta["modulo"]
    mod_ic = _MOD_ICON.get(mod, "bell")

    valor_str = ""
    if alerta.get("valor") is not None:
        v = alerta["valor"]
        if abs(v) >= 1:
            valor_str = (
                f"<span style='float:right;font-weight:600;color:{cor};font-size:1.05em'>"
                f"{fmt_brl(abs(v))}</span>"
            )

    st.markdown(
        f"<div style='background:{bg};border-radius:8px;padding:14px 18px;"
        f"border-left:5px solid {cor};margin-bottom:10px'>"
        f"  <div style='display:flex;align-items:flex-start;gap:10px'>"
        f"    <div style='padding-top:2px'>{bi(icone, 20, cor)}</div>"
        f"    <div style='flex:1'>"
        f"      <div style='display:flex;justify-content:space-between;align-items:center'>"
        f"        <span style='font-weight:700;color:{cor};font-size:0.88em'>"
        f"          {_LABEL[n]}"
        f"          &nbsp;·&nbsp;"
        f"          {bi(mod_ic,13,cor)} {mod}"
        f"        </span>"
        f"        {valor_str}"
        f"      </div>"
        f"      <div style='font-weight:600;margin:3px 0;color:#1a1a1a'>{alerta['titulo']}</div>"
        f"      <div style='color:#555;font-size:0.88em'>{alerta['detalhe']}</div>"
        f"    </div>"
        f"  </div>"
        f"</div>",
        unsafe_allow_html=True)


def _render_lista(lst: list[dict]):
    """Renderiza uma lista de alertas agrupada visualmente por nível (crítico → urgente → atenção)."""
    if not lst:
        st.info("Nenhum alerta neste módulo.")
        return
    # Agrupar por nível para separação visual
    for nivel in ("critico", "urgente", "atencao"):
        grupo = [a for a in lst if a["nivel"] == nivel]
        if grupo:
            cor = _COR[nivel]
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:8px;margin:16px 0 6px'>"
                f"{bi(_ICON[nivel],16,cor)}"
                f"<span style='font-weight:700;color:{cor};font-size:0.95em'>{_LABEL[nivel]} ({len(grupo)})</span>"
                f"</div>",
                unsafe_allow_html=True)
            for a in grupo:
                _render_card(a)


# ── Aba: Todos ────────────────────────────────────────────────────
with aba_todos:
    # Filtros rápidos
    col_f1, col_f2, _ = st.columns([2, 2, 4])
    with col_f1:
        filtro_nivel = st.multiselect(
            "Nível:", ["critico", "urgente", "atencao"],
            default=["critico", "urgente", "atencao"],
            format_func=lambda x: _LABEL[x],
            key="f_nivel_todos")
    with col_f2:
        modulos_disponiveis = list(resumo["por_modulo"].keys())
        filtro_modulo = st.multiselect(
            "Módulo:", modulos_disponiveis, default=modulos_disponiveis,
            key="f_mod_todos")

    filtrados = [
        a for a in alertas
        if a["nivel"] in filtro_nivel and a["modulo"] in filtro_modulo
    ]

    if not filtrados:
        st.info("Nenhum alerta para os filtros selecionados.")
    else:
        _render_lista(filtrados)

    # Gráfico distribuição
    st.divider()
    st.markdown(section_header("Distribuição por Módulo", "bell", 5), unsafe_allow_html=True)

    if resumo["por_modulo"]:
        modulos = list(resumo["por_modulo"].keys())
        counts  = list(resumo["por_modulo"].values())
        cores   = ["#1f6bb5", "#2ca02c", "#e67e22", "#9467bd", "#6c757d"]  # 5ª cor: módulo "Sistema"

        col_pizza, col_barra = st.columns(2)
        with col_pizza:
            fig_p = go.Figure(go.Pie(
                labels=modulos, values=counts,
                marker_colors=cores[:len(modulos)],
                hole=0.4,
                textinfo="percent+label",
            ))
            fig_p.update_layout(showlegend=False, height=280,
                                 margin=dict(l=5, r=5, t=10, b=5))
            st.plotly_chart(fig_p, use_container_width=True)

        with col_barra:
            # Barras empilhadas por nível
            niveis = ["critico", "urgente", "atencao"]
            fig_b = go.Figure()
            for niv in niveis:
                vals = [
                    len([a for a in alertas if a["modulo"] == m and a["nivel"] == niv])
                    for m in modulos
                ]
                fig_b.add_trace(go.Bar(
                    name=_LABEL[niv], x=modulos, y=vals,
                    marker_color=_COR[niv],
                ))
            fig_b.update_layout(
                barmode="stack", height=280,
                margin=dict(l=5, r=5, t=10, b=5),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig_b, use_container_width=True)


# ── Abas por módulo ────────────────────────────────────────────────
with aba_fin:
    st.caption(
        f"{bi('info',13,'#888')} Alertas baseados em AR, AP, Fluxo de Caixa e Posição Bancária.",
        unsafe_allow_html=True)
    _render_lista([a for a in alertas if a["modulo"] == "Financeiro"])
    if resumo["por_modulo"].get("Financeiro", 0) > 0:
        st.markdown("---")
        st.page_link("pages/01_Financeiro.py", label="Ir para o módulo Financeiro →", icon="💰")

with aba_com:
    st.caption(
        f"{bi('info',13,'#888')} Alertas baseados em clientes ativos, queda de compras e concentração.",
        unsafe_allow_html=True)
    _render_lista([a for a in alertas if a["modulo"] == "Comercial"])
    if resumo["por_modulo"].get("Comercial", 0) > 0:
        st.markdown("---")
        st.page_link("pages/02_Comercial.py", label="Ir para o módulo Comercial →", icon="📈")

with aba_est:
    st.caption(
        f"{bi('info',13,'#888')} Alertas baseados em estoque parado, ruptura e controle de mínimos.",
        unsafe_allow_html=True)
    _render_lista([a for a in alertas if a["modulo"] == "Estoque"])
    if resumo["por_modulo"].get("Estoque", 0) > 0:
        st.markdown("---")
        st.page_link("pages/03_Estoque.py", label="Ir para o módulo Estoque →", icon="📦")

with aba_cmp:
    st.caption(
        f"{bi('info',13,'#888')} Alertas baseados em dependência de fornecedores, sem giro e estoque parado.",
        unsafe_allow_html=True)
    _render_lista([a for a in alertas if a["modulo"] == "Compras"])
    if resumo["por_modulo"].get("Compras", 0) > 0:
        st.markdown("---")
        st.page_link("pages/04_Compras.py", label="Ir para o módulo Compras →", icon="🛒")


# ══════════════════════════════════════════════════════════════════
#  ABA CONFIGURAÇÕES — Parâmetros dos thresholds
# ══════════════════════════════════════════════════════════════════
with aba_cfg:
    st.markdown(section_header("Parâmetros dos Alertas", "gear", 4), unsafe_allow_html=True)
    st.info(
        "Os thresholds abaixo definem quando cada condição gera um alerta. "
        "Para ajustar, edite o dicionário `CFG` em `core/domain/alertas.py`.")

    cfg_data = [
        ("Financeiro", "Piso mínimo de caixa (7d)",       f"{fmt_brl(CFG['piso_caixa'])}"),
        ("Financeiro", "Capital operacional mínimo",       f"{fmt_brl(CFG['capital_minimo'])}"),
        ("Financeiro", "Horas p/ AP urgente",              f"{CFG['ap_horas_urgente']}h"),
        ("Financeiro", "Dias de atraso crítico (AR)",      f"{CFG['ar_dias_critico']} dias"),
        ("Financeiro", "% AR vencido p/ alerta",           f"{CFG['ar_vencido_pct']}%"),
        ("Financeiro", "PMR acima de (atenção)",           f"{CFG['pmr_atencao']} dias"),
        ("Financeiro", "Saldo desatualizado p/ alerta",    f"{CFG['saldo_defasagem_dias']} dias"),
        ("Comercial",  "Clientes sem comprar (dias)",      f"{CFG['clientes_sem_comprar_dias']} dias"),
        ("Comercial",  "Queda de compra p/ alerta",        f"{CFG['clientes_queda_pct']}%"),
        ("Comercial",  "Concentração top 3 p/ alerta",     f"{CFG['concentracao_top3_pct']}%"),
        ("Estoque",    "Estoque parado — dias",            f"{CFG['parado_dias']} dias"),
        ("Estoque",    "Estoque parado — valor mínimo",    f"{fmt_brl(CFG['parado_valor_min'])}"),
        ("Estoque",    "Sem venda — dias",                 f"{CFG['sem_venda_dias']} dias"),
        ("Estoque",    "Sem venda — valor mínimo",         f"{fmt_brl(CFG['sem_venda_valor_min'])}"),
        ("Compras",    "Dependência top 1 p/ alerta",      f"{CFG['dep_fornec_top1_pct']}%"),
        ("Compras",    "Dependência top 3 p/ alerta",      f"{CFG['dep_fornec_top3_pct']}%"),
        ("Compras",    "Sem giro — valor mínimo",          f"{fmt_brl(CFG['sem_giro_valor_min'])}"),
        ("Compras",    "Estoque parado forn. — valor min", f"{fmt_brl(CFG['parado_forn_valor_min'])}"),
    ]

    df_cfg = pd.DataFrame(cfg_data, columns=["Módulo", "Parâmetro", "Valor atual"])
    st.dataframe(df_cfg, use_container_width=True, hide_index=True, height=520)

    st.divider()
    st.markdown("#### Sobre o painel de alertas")
    st.markdown(
        "- **Atualização:** os alertas são recalculados a cada **5 minutos** (cache TTL=300s)\n"
        "- **Escopo de compras:** usa o período filtrado na sidebar para alertas de compras\n"
        "- **Escopo financeiro/estoque:** usa dados atuais (sem filtro de período)\n"
        "- **Nível Crítico:** ação imediata necessária — risco financeiro ou operacional\n"
        "- **Nível Urgente:** ação necessária em breve — prazo curto ou tendência negativa\n"
        "- **Nível Atenção:** monitorar — ainda controlável, mas requer acompanhamento")
