"""
Bootstrap Icons helper for Streamlit.

Usage:
    from components.bi_icons import inject_bi, bi

    inject_bi()          # call once per page at the top
    st.markdown(bi("cash-coin", size=20) + " Financeiro", unsafe_allow_html=True)

Icon names: https://icons.getbootstrap.com/
"""
import streamlit as st

_BI_CDN = (
    '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/'
    'bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">'
)

# Map logical names → Bootstrap Icon class
ICONS = {
    # Navigation / modules
    "home":          "bi-house-door",
    "financeiro":    "bi-cash-coin",
    "comercial":     "bi-cart3",
    "estoque":       "bi-boxes",
    "compras":       "bi-bag",
    "alertas":       "bi-bell",
    # Financial
    "receber":       "bi-arrow-down-circle",
    "pagar":         "bi-arrow-up-circle",
    "fluxo":         "bi-graph-up",
    "caixa":         "bi-bank",
    "calendario":    "bi-calendar3",
    "comparativo":   "bi-bar-chart-line",
    # Actions
    "imprimir":      "bi-printer",
    "excel":         "bi-file-earmark-excel",
    "pdf":           "bi-file-earmark-pdf",
    "atualizar":     "bi-arrow-clockwise",
    "salvar":        "bi-floppy",
    "deletar":       "bi-trash3",
    "busca":         "bi-search",
    "config":        "bi-gear",
    # Status / alerts
    "critico":       "bi-exclamation-circle-fill",
    "urgente":       "bi-exclamation-triangle-fill",
    "atencao":       "bi-info-circle-fill",
    "ok":            "bi-check-circle-fill",
    # Data
    "cliente":       "bi-person",
    "fornecedor":    "bi-truck",
    "produto":       "bi-box-seam",
    "documento":     "bi-file-earmark-text",
    "historico":     "bi-clock-history",
    "comentario":    "bi-chat-left-text",
    "itens":         "bi-list-ul",
    # UI hints
    "clique":        "bi-hand-index",
    "expandir":      "bi-arrows-expand",
    "fechar":        "bi-x-lg",
    "info":          "bi-info-circle",
    "warning":       "bi-exclamation-triangle",
    "error":         "bi-x-octagon",
}


def inject_bi():
    """Inject Bootstrap Icons CDN stylesheet. Call once per page."""
    st.markdown(_BI_CDN, unsafe_allow_html=True)


def bi(name: str, size: int = 16, color: str = "", extra_class: str = "") -> str:
    """
    Return an HTML <i> tag for a Bootstrap Icon.
    name: logical name from ICONS dict, or raw Bootstrap Icons class suffix
          (e.g. 'cash-coin' for bi-cash-coin)
    """
    cls = ICONS.get(name, f"bi-{name}")
    style = f"font-size:{size}px;" + (f"color:{color};" if color else "")
    return f'<i class="{cls} {extra_class}" style="{style}"></i>'


def bi_badge(text: str, icon_name: str, bg: str, border: str,
             text_color: str = "#222") -> str:
    """Render a colored badge with icon + text (for alerts, tags, etc.)."""
    icon_html = bi(icon_name, size=15)
    return (
        f"<span style='background:{bg};border:1px solid {border};"
        f"color:{text_color};border-radius:20px;padding:3px 10px;"
        f"font-size:0.82em;display:inline-flex;align-items:center;gap:5px'>"
        f"{icon_html} {text}</span>"
    )


def section_header(title: str, icon_name: str, level: int = 4) -> str:
    """HTML section header with Bootstrap Icon."""
    icon_html = bi(icon_name, size=18, color="#1f6bb5")
    tag = f"h{level}"
    return (
        f"<{tag} style='display:flex;align-items:center;gap:8px;"
        f"margin:0 0 4px 0;color:#1a1a2e'>{icon_html} {title}</{tag}>"
    )


def render_alerta_cards(alertas: list[dict], max_cards: int = 4):
    """
    Renderiza até `max_cards` alertas em colunas, no padrão visual usado nas
    seções "Alertas rápidos" das páginas de módulo (antes duplicado de forma
    idêntica em pages/01_Financeiro.py e pages/03_Estoque.py).

    `alertas`: lista de dicts com chaves "nivel" ("critico"|"urgente"|"atencao"),
    "titulo" e "detalhe" — mesmo formato padrão usado em core/domain/alertas.py.
    """
    from components.theme import NIVEL_STYLE
    if not alertas:
        return
    cols = st.columns(min(len(alertas), max_cards))
    for i, alerta in enumerate(alertas[:max_cards]):
        bg, borda, icon_name, txt = NIVEL_STYLE.get(
            alerta["nivel"], ("#f0f0f0", "#888", "info", "#333"))
        with cols[i % max_cards]:
            st.markdown(
                f"<div style='background:{bg};border-left:4px solid {borda};"
                f"padding:10px 14px;border-radius:6px;margin-bottom:6px;"
                f"display:flex;gap:10px;align-items:flex-start'>"
                f"<span style='color:{borda};font-size:1.2rem;flex-shrink:0'>"
                f"{bi(icon_name,18,borda)}</span>"
                f"<div><b style='color:{txt}'>{alerta['titulo']}</b><br>"
                f"<small style='color:#666'>{alerta['detalhe']}</small></div>"
                f"</div>",
                unsafe_allow_html=True)
