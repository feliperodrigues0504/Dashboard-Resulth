"""
Painel Personalizado — dashboard configurável pelo usuário.
Tela ADITIVA: não substitui a Home (app.py) nem nenhuma página existente —
é um novo espaço onde o usuário escolhe quais indicadores (já existentes nos
módulos Financeiro/Comercial/Estoque/Compras/Alertas) quer ver, e organiza
livremente num grid arrastável/redimensionável (streamlit_elements).

Trade-off técnico (ver auditoria): dentro do grid arrastável não é possível
usar st.plotly_chart/st.dataframe/AgGrid — só componentes MUI/Nivo da própria
lib. Por isso os widgets aqui usam gráficos Nivo e tabelas/KPIs em MUI, com
um visual um pouco diferente do resto do app (que usa Plotly/AgGrid).
"""
import json
from datetime import date

import streamlit as st
from streamlit_elements import elements, dashboard, mui, sync

from components.bi_icons import inject_bi, bi
from components.print_btn import render_print_css
from components.painel.render import RENDER_POR_TIPO
from components.theme import COR_PRIM
from core.data.duckdb_store import init_store, get_preferencia, set_preferencia
from core.dashboard.registry import get_widget, widgets_por_origem

st.set_page_config(page_title="Painel Personalizado", page_icon="🧩", layout="wide")
init_store()
render_print_css()
inject_bi()

_KEY_SELECAO = "painel_widgets_selecionados"
_KEY_LAYOUT = "painel_layout_salvo"
_DEFAULT_W, _DEFAULT_H = 4, 3
_COLS = 12


# ══════════════════════════════════════════════════════════════════
#  PERSISTÊNCIA (DuckDB — mesma tabela preferencias_home já usada pelo home)
# ══════════════════════════════════════════════════════════════════
def _carregar_selecao() -> list[str]:
    """Lê os ids de widgets escolhidos pelo usuário (JSON salvo no DuckDB)."""
    bruto = get_preferencia(_KEY_SELECAO, "[]")
    try:
        ids = json.loads(bruto)
        return [i for i in ids if get_widget(i) is not None]
    except Exception:
        return []


def _salvar_selecao(ids: list[str]):
    set_preferencia(_KEY_SELECAO, json.dumps(ids))


def _carregar_layout() -> dict[str, dict]:
    """Lê o layout salvo (posições/tamanhos por widget id)."""
    bruto = get_preferencia(_KEY_LAYOUT, "{}")
    try:
        return json.loads(bruto)
    except Exception:
        return {}


def _salvar_layout(layout_lista: list[dict]):
    mapa = {item["i"]: item for item in layout_lista}
    set_preferencia(_KEY_LAYOUT, json.dumps(mapa))


def _posicao_default(indice: int) -> tuple[int, int]:
    """Posição padrão para um widget recém-adicionado (empilha em linhas de _DEFAULT_W)."""
    por_linha = max(_COLS // _DEFAULT_W, 1)
    return (indice % por_linha) * _DEFAULT_W, (indice // por_linha) * _DEFAULT_H


# ══════════════════════════════════════════════════════════════════
#  CABEÇALHO
# ══════════════════════════════════════════════════════════════════
st.markdown(
    f"<h1 style='margin:0;display:flex;align-items:center;gap:10px'>"
    f"{bi('grid-3x3-gap-fill', 28, COR_PRIM)} Painel Personalizado</h1>"
    f"<p style='margin:4px 0 16px;color:#666;font-size:0.9em'>"
    f"Escolha os indicadores que quiser e organize-os arrastando e "
    f"redimensionando os cards. O arranjo fica salvo para a próxima visita.</p>",
    unsafe_allow_html=True)

col_per1, col_per2, _ = st.columns([2, 2, 8])
with col_per1:
    data_ini = st.date_input("Período de", value=date(date.today().year, 1, 1),
                             format="DD/MM/YYYY", key="painel_data_ini")
with col_per2:
    data_fim = st.date_input("até", value=date.today(),
                             format="DD/MM/YYYY", key="painel_data_fim")
st.caption("O período acima se aplica a todos os widgets que dependem de período "
           "(Financeiro/Comercial/Compras). KPIs de estado atual (ex.: estoque, alertas) não usam este filtro.")


# ══════════════════════════════════════════════════════════════════
#  SELETOR DE WIDGETS
# ══════════════════════════════════════════════════════════════════
selecionados = st.session_state.setdefault(_KEY_SELECAO, _carregar_selecao())

with st.expander(f"➕ Escolher indicadores ({len(selecionados)} selecionado(s))", expanded=not selecionados):
    st.caption("Cada indicador abaixo já existe em um módulo do sistema — aqui você só escolhe quais "
               "quer ver consolidados neste painel.")
    grupos = widgets_por_origem()
    novos_selecionados = list(selecionados)
    for origem, widgets_do_grupo in grupos.items():
        st.markdown(f"**{origem}**")
        cols = st.columns(3)
        for idx, w in enumerate(widgets_do_grupo):
            with cols[idx % 3]:
                marcado = st.checkbox(
                    w["nome"], value=w["id"] in selecionados,
                    help=f"{w['descricao']} (origem: {origem})",
                    key=f"chk_widget_{w['id']}")
                if marcado and w["id"] not in novos_selecionados:
                    novos_selecionados.append(w["id"])
                elif not marcado and w["id"] in novos_selecionados:
                    novos_selecionados.remove(w["id"])

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("💾 Salvar seleção", key="salvar_selecao_painel"):
            st.session_state[_KEY_SELECAO] = novos_selecionados
            _salvar_selecao(novos_selecionados)
            st.success("Seleção salva.")
            st.rerun()
    with col_btn2:
        if st.button("🧹 Limpar painel", key="limpar_painel"):
            st.session_state[_KEY_SELECAO] = []
            _salvar_selecao([])
            set_preferencia(_KEY_LAYOUT, "{}")
            st.rerun()

selecionados = st.session_state[_KEY_SELECAO]


# ══════════════════════════════════════════════════════════════════
#  GRID ARRASTÁVEL / REDIMENSIONÁVEL
# ══════════════════════════════════════════════════════════════════
if not selecionados:
    st.info("Nenhum indicador selecionado ainda — abra \"➕ Escolher indicadores\" acima para montar seu painel.")
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

    with elements("painel_personalizado_grid"):
        with dashboard.Grid(layout, draggableHandle=".painel-drag-handle",
                            onLayoutChange=sync("painel_layout_atual"),
                            style={"backgroundColor": "transparent"}):
            for widget_id in selecionados:
                w = get_widget(widget_id)
                if w is None:
                    continue
                with mui.Card(key=widget_id, sx={
                    "display": "flex", "flexDirection": "column", "height": "100%",
                    "overflow": "auto", "border": "1px solid #d0e3f5",
                }):
                    mui.CardHeader(
                        title=w["nome"], subheader=w["origem"],
                        className="painel-drag-handle",
                        sx={"cursor": "move", "backgroundColor": "#f0f7ff", "py": 1},
                        titleTypographyProps={"variant": "subtitle2", "sx": {"fontWeight": 700}},
                        subheaderTypographyProps={"variant": "caption"},
                    )
                    with mui.CardContent(sx={"flex": 1, "overflow": "auto"}):
                        try:
                            dado = w["fetch"](data_ini, data_fim)
                            RENDER_POR_TIPO[w["tipo"]](dado)
                        except Exception as e:
                            mui.Typography(f"Erro ao carregar: {e}", variant="body2", sx={"color": "error.main"})
