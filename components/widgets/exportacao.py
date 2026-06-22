"""Barra de exportação Excel + PDF (com comentários gerenciais embutidos) — uma fábrica por módulo."""
from __future__ import annotations
from datetime import date

import streamlit as st

from core.data.duckdb_store import get_comentarios
from core.export import gerar_excel, gerar_pdf


def make_toolbar_export(modulo: str):
    """Fábrica da barra de exportação Excel + PDF para um módulo."""
    def _toolbar_export(titulo: str, secoes: dict, kpis_export: dict,
                        periodo_ini: date, periodo_fim: date, indicador: str):
        """Renderiza os botões de download Excel e PDF, embutindo os comentários gerenciais salvos no relatório."""
        comentarios_df = get_comentarios(modulo, indicador, periodo_ini, periodo_fim)
        comentario_txt = "\n\n".join(comentarios_df["texto"].tolist()) if not comentarios_df.empty else ""

        col1, col2, col3 = st.columns([1, 1, 6])
        with col1:
            xlsx = gerar_excel(secoes, titulo, periodo_ini, periodo_fim, comentario_txt)
            st.download_button(
                "📊 Excel", data=xlsx,
                file_name=f"{titulo.lower().replace(' ','_')}_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Baixar esta seção como planilha Excel",
                key=f"xls_{indicador}")
        with col2:
            pdf_bytes = gerar_pdf(titulo, kpis_export, secoes,
                                  periodo_ini, periodo_fim, comentario_txt)
            st.download_button(
                "📄 PDF", data=bytes(pdf_bytes),
                file_name=f"{titulo.lower().replace(' ','_')}_{date.today()}.pdf",
                mime="application/pdf",
                help="Baixar esta seção como relatório PDF",
                key=f"pdf_{indicador}")
    return _toolbar_export
