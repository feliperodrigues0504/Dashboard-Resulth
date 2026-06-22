"""
Botão de impressão centralizado.
Uso:
    from components.print_btn import render_print_css, render_print_button
    render_print_css()          # uma vez por página, no topo
    render_print_button()       # onde quiser colocar o botão
"""
import streamlit as st
import streamlit.components.v1 as components


# CSS aplicado quando o navegador imprime (Ctrl+P ou botão de imprimir)
_PRINT_CSS = """
<style>
@media print {
    /* Oculta elementos de navegação e controles */
    section[data-testid="stSidebar"],
    div[data-testid="stToolbar"],
    div[data-testid="stDecoration"],
    div[data-testid="stStatusWidget"],
    #MainMenu,
    footer,
    .stButton,
    .stDownloadButton,
    .stAlert { display: none !important; }

    /* Remove padding excessivo */
    .block-container { padding: 0 1rem !important; max-width: 100% !important; }
    .main .block-container { padding-top: 0.5rem !important; }

    /* Garante que gráficos e tabelas não cortam entre páginas */
    .stPlotlyChart, .stDataFrame, .stAgGrid { page-break-inside: avoid; }

    /* Fonte menor para caber mais conteúdo */
    body { font-size: 11pt !important; }

    /* Cabeçalho de impressão */
    body::before {
        content: attr(data-print-header);
        display: block;
        font-size: 14pt;
        font-weight: bold;
        text-align: center;
        margin-bottom: 8px;
        border-bottom: 2px solid #1f6bb5;
        padding-bottom: 6px;
    }
}
</style>
"""


def render_print_css():
    """Injeta o CSS de impressão na página. Chamar uma vez por página."""
    st.markdown(_PRINT_CSS, unsafe_allow_html=True)


def render_print_button(label: str = "🖨️ Imprimir", key: str = "print_btn"):
    """
    Renderiza o botão de impressão.
    Ao clicar, abre o diálogo de impressão do navegador com a página formatada.
    """
    if st.button(label, key=key):
        # Aciona window.print() no contexto da janela pai (o Streamlit inteiro)
        components.html(
            "<script>window.parent.print();</script>",
            height=0,
        )
