"""
Widgets compartilhados entre as páginas de módulo (Financeiro, Comercial,
Estoque, Compras), divididos por responsabilidade:

- selecao.py:     df_selecionavel, selecao_mudou — UI pura, sem acesso a dado.
- comentarios.py: make_widget_comentario — UI + persistência de comentários.
- exportacao.py:  make_toolbar_export    — UI + geração de Excel/PDF.

Reexportados aqui para que o import usado nas páginas não precise mudar:

    from components.widgets import df_selecionavel, make_widget_comentario, make_toolbar_export
"""
from components.widgets.selecao import df_selecionavel, selecao_mudou
from components.widgets.comentarios import make_widget_comentario
from components.widgets.exportacao import make_toolbar_export

__all__ = ["df_selecionavel", "selecao_mudou", "make_widget_comentario", "make_toolbar_export"]
