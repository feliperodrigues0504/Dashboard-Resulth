"""
Renderização dos filtros globais na sidebar — UI pura.
A aplicação dos filtros a um DataFrame (lógica de negócio, sem Streamlit)
está em core/domain/filtros.py.

Uso em qualquer módulo:

    from components.sidebar_filtros import render_sidebar, carregar_opcoes_filtros
    from core.domain.filtros import aplicar
    opcoes  = carregar_opcoes_filtros()
    filtros = render_sidebar(opcoes, visiveis=['periodo','empresa','vendedor','cliente'])
    df_ar   = aplicar(df_ar,  filtros, mapa={'empresa':'CODEMPRESA','vendedor':'CODVENDEDOR','cliente':'CODCLIENTE'})
    df_ap   = aplicar(df_ap,  filtros, mapa={'empresa':'CODEMPRESA','fornecedor':'CODFORNEC'})
"""
from __future__ import annotations
from datetime import date
import streamlit as st

from core.data.repositories.cadastros_repo import fetch_opcoes_filtros

# Todos os filtros disponíveis e a ordem em que aparecem
_TODOS = ["periodo", "empresa", "vendedor", "cliente", "fornecedor", "grupo", "marca"]

# Chave no session_state onde os filtros ficam persistidos entre páginas
_KEY = "filtros_globais"


def _estado_inicial() -> dict:
    """Valores padrão dos filtros globais (período = ano corrente, demais = 'Todos'/'Todas')."""
    return {
        "data_ini":    date(date.today().year, 1, 1),
        "data_fim":    date.today(),
        "empresa":     "Todas",
        "vendedor":    "Todos",
        "cliente":     "Todos",
        "fornecedor":  "Todos",
        "grupo":       "Todos",
        "marca":       "Todas",
    }


def render_sidebar(opcoes: dict,
                   visiveis: list[str] | None = None,
                   titulo: str = "Filtros") -> dict:
    """
    Renderiza os filtros na sidebar.
    - opcoes: dict retornado por fetch_opcoes_filtros()
    - visiveis: lista dos filtros a exibir (None = todos)
    Retorna o dict de filtros ativos (persiste em session_state).
    """
    if _KEY not in st.session_state:
        st.session_state[_KEY] = _estado_inicial()

    f = st.session_state[_KEY]
    show = set(visiveis or _TODOS)

    with st.sidebar:
        st.title(titulo)

        # ── Período ───────────────────────────────────────────────
        if "periodo" in show:
            st.markdown("**Período de vencimento**")
            col1, col2 = st.columns(2)
            with col1:
                f["data_ini"] = st.date_input("De", value=f["data_ini"],
                                               format="DD/MM/YYYY", key="sb_data_ini")
            with col2:
                f["data_fim"] = st.date_input("Até", value=f["data_fim"],
                                               format="DD/MM/YYYY", key="sb_data_fim")

        # ── Empresa ───────────────────────────────────────────────
        if "empresa" in show:
            emps = ["Todas"] + opcoes.get("empresas", [])
            idx  = emps.index(f["empresa"]) if f["empresa"] in emps else 0
            f["empresa"] = st.selectbox("Empresa", emps, index=idx, key="sb_empresa")

        # ── Vendedor ──────────────────────────────────────────────
        if "vendedor" in show:
            vends = ["Todos"] + opcoes.get("vendedores", [])
            idx   = vends.index(f["vendedor"]) if f["vendedor"] in vends else 0
            f["vendedor"] = st.selectbox("Vendedor", vends, index=idx, key="sb_vendedor")

        # ── Cliente ───────────────────────────────────────────────
        if "cliente" in show:
            clis = ["Todos"] + opcoes.get("clientes", [])
            idx  = clis.index(f["cliente"]) if f["cliente"] in clis else 0
            f["cliente"] = st.selectbox("Cliente", clis, index=idx, key="sb_cliente")

        # ── Fornecedor ────────────────────────────────────────────
        if "fornecedor" in show:
            forns = ["Todos"] + opcoes.get("fornecedores", [])
            idx   = forns.index(f["fornecedor"]) if f["fornecedor"] in forns else 0
            f["fornecedor"] = st.selectbox("Fornecedor", forns, index=idx, key="sb_fornecedor")

        # ── Grupo de Produto ──────────────────────────────────────
        if "grupo" in show:
            grps = ["Todos"] + opcoes.get("grupos", [])
            idx  = grps.index(f["grupo"]) if f["grupo"] in grps else 0
            f["grupo"] = st.selectbox("Grupo de Produto", grps, index=idx, key="sb_grupo")

        # ── Marca (Fabricante) ────────────────────────────────────
        if "marca" in show:
            marcas = ["Todas"] + opcoes.get("marcas", [])
            idx    = marcas.index(f["marca"]) if f["marca"] in marcas else 0
            f["marca"] = st.selectbox("Marca", marcas, index=idx, key="sb_marca")

        st.divider()
        if st.button("🔄 Atualizar dados", key="sb_atualizar"):
            st.cache_data.clear()
            st.rerun()
        st.caption("Cache: 15 min")

    st.session_state[_KEY] = f
    return dict(f)


def get_filtros() -> dict:
    """Retorna os filtros ativos sem renderizar nada (para usar em outros contextos)."""
    return dict(st.session_state.get(_KEY, _estado_inicial()))


@st.cache_data(ttl=3600, show_spinner=False)
def carregar_opcoes_filtros() -> dict:
    """
    Carrega as opções de filtro (cadastros: empresas, vendedores, clientes,
    fornecedores, grupos, marcas) e as deixa em session_state para
    render_sidebar() usar. Antes desta consolidação, esta função era
    copiada de forma idêntica nas 5 páginas (Financeiro, Comercial, Estoque,
    Compras, Alertas) — cada uma com seu próprio cache, refazendo a mesma
    busca. Compartilhada aqui, o cache também passa a ser compartilhado.
    """
    opc = fetch_opcoes_filtros()
    st.session_state["opcoes_cadastros"] = opc
    return opc
