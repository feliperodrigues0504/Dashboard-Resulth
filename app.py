"""
Tela Inicial — Painel Executivo Personalizável.
Escolha os indicadores que quiser (entre os já existentes em Financeiro/
Comercial/Estoque/Compras/Alertas) e organize-os num grid arrastável e
redimensionável. O arranjo fica salvo para a próxima visita.

Busca Global (Spotlight) e Relatório Executivo ficam como seções fixas,
fora do grid: usam componentes nativos do Streamlit (selectbox, download
button) que não funcionam dentro do grid arrastável — ver nota em
core/dashboard/widgets_geral.py.
"""
import os
import json
import streamlit as st
import pandas as pd
from datetime import date

from streamlit_elements import elements, dashboard, mui, sync

from components.bi_icons import inject_bi, bi, section_header
from components.print_btn import render_print_css, render_print_button
from components.metrics import kpi_card
from components.theme import COR_PRIM, COR_OK, COR_ALERTA, COR_PERIGO
from components.freshness import marcar_frescor, rotulo_frescor
from components.sidebar_filtros import carregar_opcoes_filtros
from components.painel.render import RENDER_POR_TIPO
from core.domain.spotlight import perfil_cliente, perfil_fornecedor
from core.domain.relatorio_executivo import gerar_relatorio_executivo, ultimo_relatorio
from core.data.duckdb_store import init_store, get_preferencia, set_preferencia
from core.dashboard.registry import get_widget, widgets_por_origem

st.set_page_config(page_title="Cetel — Dashboard Executivo", page_icon="🏠", layout="wide")
init_store()

# ── Agendador de snapshots diários (singleton por processo Streamlit) ─────────
try:
    from core.sync.agendador import iniciar_agendador
    iniciar_agendador()
except Exception:
    pass

render_print_css()
inject_bi()

_KEY_SELECAO = "painel_widgets_selecionados"
_KEY_LAYOUT = "painel_layout_salvo"
_DEFAULT_W, _DEFAULT_H = 4, 3
_COLS = 12

# Conjunto de indicadores que aparece na primeira visita (e sempre que a
# seleção ficar vazia) — sem isso a Home começaria em branco, pedindo pro
# usuário montar tudo do zero antes de ver qualquer dado.
_WIDGETS_PADRAO = [
    "ger_modulos_nav", "alr_total", "alr_criticos", "com_meta_progresso",
    "fin_saldo_bco", "fin_total_ar", "fin_vencido_ar", "fin_total_ap",
    "fin_vencido_ap", "fin_capital_op", "est_valor_custo",
    "ger_delta_caixa", "ger_delta_fat", "ger_delta_ar_vencido", "ger_delta_capital",
    "com_faturamento_periodo", "fin_aging_faixa", "alr_lista",
    "ger_historico_caixa_ar", "ger_historico_capital",
]


# ══════════════════════════════════════════════════════════════════
#  PERSISTÊNCIA (DuckDB — preferencias_home)
# ══════════════════════════════════════════════════════════════════
def _carregar_selecao() -> list[str]:
    """Lê os ids de widgets escolhidos; cai nos padrão se nunca foi customizado ou ficou vazio."""
    bruto = get_preferencia(_KEY_SELECAO, "[]")
    try:
        ids = [i for i in json.loads(bruto) if get_widget(i) is not None]
    except Exception:
        ids = []
    return ids if ids else list(_WIDGETS_PADRAO)


def _salvar_selecao(ids: list[str]):
    set_preferencia(_KEY_SELECAO, json.dumps(ids))


def _carregar_layout() -> dict[str, dict]:
    bruto = get_preferencia(_KEY_LAYOUT, "{}")
    try:
        return json.loads(bruto)
    except Exception:
        return {}


def _salvar_layout(layout_lista: list[dict]):
    mapa = {item["i"]: item for item in layout_lista}
    set_preferencia(_KEY_LAYOUT, json.dumps(mapa))


def _posicao_default(indice: int) -> tuple[int, int]:
    por_linha = max(_COLS // _DEFAULT_W, 1)
    return (indice % por_linha) * _DEFAULT_W, (indice // por_linha) * _DEFAULT_H


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_widget_cached(widget_id: str, data_ini_str: str, data_fim_str: str) -> dict:
    """Cache por (widget, período) — sem isso, todo rerun da página (qualquer clique) refaria a busca de TODOS os widgets selecionados no Firebird."""
    w = get_widget(widget_id)
    if w is None:
        return {}
    return w["fetch"](date.fromisoformat(data_ini_str), date.fromisoformat(data_fim_str))


# ══════════════════════════════════════════════════════════════════
#  DADOS DAS SEÇÕES FIXAS (Busca Global, cabeçalho)
# ══════════════════════════════════════════════════════════════════
@st.cache_data(ttl=600, show_spinner=False)
def _home_alertas_resumo():
    marcar_frescor("home_alertas")
    try:
        from core.domain.alertas import get_todos_alertas, resumo_alertas
        ini = (pd.Timestamp.now() - pd.DateOffset(months=3)).strftime("%Y-%m-%d")
        fim = (pd.Timestamp.now() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        todos = get_todos_alertas(ini, fim)
        return resumo_alertas(todos)
    except Exception:
        return {"total": 0, "criticos": 0, "urgentes": 0, "atencoes": 0, "por_modulo": {}}


@st.cache_data(ttl=600, show_spinner=False)
def _home_status_snapshot():
    try:
        from core.sync.snapshot import status_snapshot
        return status_snapshot()
    except Exception:
        return {"ultima_data": None, "dias_atraso": None, "atrasado": True}


with st.spinner("Carregando…"):
    res_al = _home_alertas_resumo()
    status_snap = _home_status_snapshot()
    opcoes_busca = carregar_opcoes_filtros()


# ══════════════════════════════════════════════════════════════════
#  SIDEBAR — Sistema
# ══════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(f"### {bi('info',16,'#888')} Sistema", unsafe_allow_html=True)
    st.caption(rotulo_frescor("home_financeiro", "home_faturamento", "home_estoque", "home_alertas"))
    st.caption("Banco: Resulth (Firebird 2.5) · R/O")
    st.caption("Store analítico: DuckDB")

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
#  BUSCA GLOBAL (SPOTLIGHT) — seção fixa (usa selectbox nativo)
# ══════════════════════════════════════════════════════════════════
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
#  PERÍODO — aplica-se aos widgets do grid que dependem de período
# ══════════════════════════════════════════════════════════════════
col_per1, col_per2, _ = st.columns([2, 2, 8])
with col_per1:
    data_ini = st.date_input("Período de", value=date(date.today().year, 1, 1),
                             format="DD/MM/YYYY", key="painel_data_ini")
with col_per2:
    data_fim = st.date_input("até", value=date.today(),
                             format="DD/MM/YYYY", key="painel_data_fim")
st.caption("Aplica-se aos indicadores que dependem de período (Financeiro/Comercial/Compras). "
           "KPIs de estado atual (ex.: estoque, alertas) não usam este filtro.")


# ══════════════════════════════════════════════════════════════════
#  SELETOR DE WIDGETS
# ══════════════════════════════════════════════════════════════════
st.session_state.setdefault(_KEY_SELECAO, _carregar_selecao())


def _toggle_widget(widget_id: str):
    """Aplica a seleção imediatamente (ao vivo) e já persiste no DuckDB."""
    marcado = st.session_state[f"chk_widget_{widget_id}"]
    atual = list(st.session_state[_KEY_SELECAO])
    if marcado and widget_id not in atual:
        atual.append(widget_id)
    elif not marcado and widget_id in atual:
        atual.remove(widget_id)
    st.session_state[_KEY_SELECAO] = atual
    _salvar_selecao(atual)


selecionados = st.session_state[_KEY_SELECAO]

with st.expander(f"➕ Personalizar meus indicadores ({len(selecionados)} no painel)", expanded=False):
    st.caption("Marque um indicador para ele aparecer imediatamente no painel, abaixo. "
               "Desmarque para remover.")
    grupos = widgets_por_origem()
    for origem, widgets_do_grupo in grupos.items():
        st.markdown(f"**{origem}**")
        cols = st.columns(3)
        for idx, w in enumerate(widgets_do_grupo):
            with cols[idx % 3]:
                st.checkbox(
                    w["nome"], value=w["id"] in selecionados,
                    help=f"{w['descricao']} (origem: {origem})",
                    key=f"chk_widget_{w['id']}",
                    on_change=_toggle_widget, args=(w["id"],))

    if st.button("🔄 Restaurar painel padrão", key="restaurar_padrao"):
        st.session_state[_KEY_SELECAO] = list(_WIDGETS_PADRAO)
        _salvar_selecao(list(_WIDGETS_PADRAO))
        set_preferencia(_KEY_LAYOUT, "{}")
        st.rerun()

selecionados = st.session_state[_KEY_SELECAO]


# ══════════════════════════════════════════════════════════════════
#  GRID ARRASTÁVEL / REDIMENSIONÁVEL
# ══════════════════════════════════════════════════════════════════
if not selecionados:
    st.info("Nenhum indicador selecionado — abra \"➕ Personalizar meus indicadores\" acima.")
else:
    layout_salvo = _carregar_layout()
    layout = []
    for idx, widget_id in enumerate(selecionados):
        pos = layout_salvo.get(widget_id)
        if pos:
            layout.append(dashboard.Item(widget_id, pos["x"], pos["y"], pos["w"], pos["h"]))
        else:
            x, y = _posicao_default(idx)
            layout.append(dashboard.Item(widget_id, x, y, _DEFAULT_W, _DEFAULT_H))

    col_save, _ = st.columns([2, 8])
    with col_save:
        if st.button("💾 Salvar arranjo (posição/tamanho)", key="salvar_layout_painel"):
            novo_layout = st.session_state.get("painel_layout_atual")
            if novo_layout:
                _salvar_layout(novo_layout)
                st.success("Arranjo salvo.")
            else:
                st.info("Arraste ou redimensione algum card antes de salvar.")

    with elements("painel_home_grid"):
        with dashboard.Grid(layout, draggableHandle=".painel-drag-handle",
                            onLayoutChange=sync("painel_layout_atual")):
            for widget_id in selecionados:
                w = get_widget(widget_id)
                if w is None:
                    continue
                with mui.Card(key=widget_id, sx={"width": "100%", "height": "100%"}):
                    mui.CardHeader(
                        title=w["nome"], subheader=w["origem"],
                        className="painel-drag-handle",
                        sx={"cursor": "move", "backgroundColor": "#f0f7ff", "py": 1},
                    )
                    with mui.CardContent():
                        try:
                            dado = _fetch_widget_cached(widget_id, str(data_ini), str(data_fim))
                            RENDER_POR_TIPO[w["tipo"]](dado)
                        except Exception as e:
                            mui.Typography(f"Erro ao carregar: {e}", variant="body2", sx={"color": "error.main"})

st.divider()


# ══════════════════════════════════════════════════════════════════
#  RELATÓRIO EXECUTIVO — seção fixa (usa download_button nativo)
# ══════════════════════════════════════════════════════════════════
st.markdown(section_header("Relatório Executivo", "file-earmark-pdf", 4), unsafe_allow_html=True)
st.caption("PDF consolidado — Financeiro, Comercial, Estoque e Alertas críticos. "
           "Gerado automaticamente toda segunda-feira às 07:00, ou a qualquer momento abaixo.")

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


# ══════════════════════════════════════════════════════════════════
#  RODAPÉ
# ══════════════════════════════════════════════════════════════════
st.divider()
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"<small style='color:#888'>{bi('database',13,COR_PRIM)} "
                f"Resulth · Firebird 2.5 · Somente leitura</small>", unsafe_allow_html=True)
with c2:
    st.markdown(f"<small style='color:#888'>{bi('arrow-clockwise',13,COR_PRIM)} "
                f"Cache: 5 min</small>", unsafe_allow_html=True)
with c3:
    st.markdown(f"<small style='color:#888'>{bi('gear',13,COR_PRIM)} "
                f"Python · Streamlit · DuckDB · streamlit-elements · APScheduler</small>", unsafe_allow_html=True)
with c4:
    st.markdown(f"<small style='color:#888'>{bi('info',13,COR_PRIM)} "
                f"v{date.today().strftime('%Y.%m')} · Felipe Rodrigues</small>", unsafe_allow_html=True)
