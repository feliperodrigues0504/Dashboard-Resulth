"""Widget de comentários gerenciais persistentes (DuckDB) — uma fábrica por módulo."""
from __future__ import annotations
import html
from datetime import date

import pandas as pd
import streamlit as st

from core.data.duckdb_store import get_comentarios, salvar_comentario, deletar_comentario


def make_widget_comentario(modulo: str,
                           placeholder: str = "Digite uma observação sobre este indicador..."):
    """Fábrica do widget de comentários gerenciais persistentes para um módulo."""
    def _widget_comentario(indicador: str, periodo_ini: date, periodo_fim: date):
        """Renderiza a lista de comentários de `indicador` no período e o formulário para adicionar/excluir um novo."""
        with st.expander("💬 Comentário Gerencial", expanded=False):
            comentarios = get_comentarios(modulo, indicador, periodo_ini, periodo_fim)
            if not comentarios.empty:
                for _, row in comentarios.iterrows():
                    col_txt, col_del = st.columns([9, 1])
                    with col_txt:
                        ts = pd.Timestamp(row["criado_em"]).strftime("%d/%m/%Y %H:%M")
                        # Escapa o texto do comentário antes de injetar no HTML —
                        # é texto livre digitado pelo usuário (st.text_area), e
                        # sem isso um comentário como "<script>...</script>"
                        # seria executado no navegador de quem visualizar a
                        # tela (XSS armazenado via unsafe_allow_html=True).
                        texto_seguro = html.escape(str(row["texto"])).replace("\n", "<br>")
                        st.markdown(
                            f"<div style='background:#fffbea;padding:8px 12px;border-radius:6px;"
                            f"border-left:3px solid #f0b429;margin-bottom:6px'>"
                            f"<small style='color:#888'>{ts}</small><br>{texto_seguro}</div>",
                            unsafe_allow_html=True)
                    with col_del:
                        if st.button("🗑️", key=f"del_{row['id']}",
                                     help="Excluir este comentário"):
                            if deletar_comentario(int(row["id"])):
                                st.rerun()
                            else:
                                st.error("Não foi possível excluir o comentário. Tente novamente.")

            novo = st.text_area(
                "Novo comentário: *", height=80,
                placeholder=placeholder,
                help="Campo obrigatório para salvar",
                key=f"novo_{indicador}")
            if st.button("💾 Salvar comentário", key=f"salvar_{indicador}"):
                if novo.strip():
                    if salvar_comentario(modulo, indicador, periodo_ini, periodo_fim, novo):
                        st.success("Comentário salvo!")
                        st.rerun()
                    else:
                        st.error("Não foi possível salvar o comentário. Tente novamente.")
                else:
                    st.warning("⚠️ Digite algo antes de salvar — este campo é obrigatório.")
    return _widget_comentario
