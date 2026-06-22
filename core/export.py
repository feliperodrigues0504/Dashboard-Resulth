"""
Módulo de exportação: Excel e PDF para todos os dashboards.
Uso:
    from core.export import gerar_excel, gerar_pdf
"""
from __future__ import annotations
import io
from datetime import date, datetime
from typing import Any

import pandas as pd
from fpdf import FPDF

# Caracteres Unicode fora do range latin-1 do Helvetica
_SUBS = {
    '—': '--', '–': '-', '’': "'", '‘': "'",
    '“': '"',  '”': '"', '…': '...', '→': '->',
    '←': '<-', 'é': 'e', 'ç': 'c', 'ã': 'a',
    'õ': 'o',  'â': 'a', 'ê': 'e', 'ô': 'o',
    'í': 'i',  'ú': 'u', 'ó': 'o', 'á': 'a',
    'É': 'E',  'Ç': 'C', 'Ã': 'A', 'Õ': 'O',
}


def _pdf_safe(text: str) -> str:
    """Converte texto para latin-1 seguro para o Helvetica do fpdf2."""
    if not isinstance(text, str):
        text = str(text)
    for src, dst in _SUBS.items():
        text = text.replace(src, dst)
    # Remove qualquer restante fora do latin-1
    return text.encode('latin-1', errors='replace').decode('latin-1')


# ── Excel ─────────────────────────────────────────────────────────────────────

def gerar_excel(secoes: dict[str, pd.DataFrame],
                titulo: str = "Relatório",
                periodo_ini: date | None = None,
                periodo_fim: date | None = None,
                comentario: str = "") -> bytes:
    """
    Gera um Excel com uma aba por seção.
    secoes: {'Nome da Aba': dataframe, ...}
    """
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # Aba de capa
        meta = pd.DataFrame({
            "Campo": ["Relatório", "Gerado em", "Período de", "Período até", "Comentário"],
            "Valor": [
                titulo,
                datetime.now().strftime("%d/%m/%Y %H:%M"),
                periodo_ini.strftime("%d/%m/%Y") if periodo_ini else "—",
                periodo_fim.strftime("%d/%m/%Y") if periodo_fim else "—",
                comentario or "—",
            ]
        })
        meta.to_excel(writer, sheet_name="Capa", index=False)

        for nome_aba, df in secoes.items():
            if df is not None and not df.empty:
                aba = nome_aba[:31]  # Excel limita a 31 chars
                df.to_excel(writer, sheet_name=aba, index=False)

    return buf.getvalue()


# ── PDF ───────────────────────────────────────────────────────────────────────

class _PDF(FPDF):
    """
    Subclasse de FPDF com layout próprio do Cetel: cabeçalho com título e
    período, rodapé com numeração de página, e helpers de alto nível
    (seção, linha de KPI, tabela, comentário) para montar o relatório sem
    repetir chamadas de fonte/cor em cada página de export.
    """

    def __init__(self, titulo: str, periodo: str):
        """Inicializa o PDF guardando título e período (já sanitizados) para uso em cada `header()`."""
        super().__init__()
        self._titulo  = _pdf_safe(titulo)
        self._periodo = _pdf_safe(periodo)
        self.set_auto_page_break(auto=True, margin=12)

    def header(self):
        """Callback do FPDF: desenha título, período e data de emissão no topo de cada página."""
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 8, self._titulo, ln=True, align="C")
        self.set_font("Helvetica", "", 9)
        self.cell(0, 5, self._periodo, ln=True, align="C")
        self.set_font("Helvetica", "", 8)
        self.cell(0, 4,
                  f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                  ln=True, align="R")
        self.ln(3)
        self.set_draw_color(31, 107, 181)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        """Callback do FPDF: desenha o número da página no rodapé de cada página."""
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 5, "Pagina " + str(self.page_no()) + " - Cetel Dashboards Resulth", align="C")
        self.set_text_color(0, 0, 0)

    def secao(self, titulo: str):
        """Desenha um cabeçalho de seção (faixa cinza com o título em negrito)."""
        self.set_font("Helvetica", "B", 10)
        self.set_fill_color(240, 244, 248)
        self.cell(0, 7, "  " + _pdf_safe(titulo), ln=True, fill=True)
        self.ln(2)

    def kpi_linha(self, label: str, valor: str, destaque: bool = False):
        """Desenha uma linha label/valor (ex.: um KPI), com o valor sempre em negrito."""
        self.set_font("Helvetica", "B" if destaque else "", 9)
        self.cell(90, 6, "  " + _pdf_safe(label))
        self.set_font("Helvetica", "B", 9)
        self.cell(0, 6, _pdf_safe(valor), ln=True)
        self.set_font("Helvetica", "", 9)

    def tabela(self, df: pd.DataFrame, col_widths: list[float] | None = None):
        """Desenha um DataFrame como tabela com cabeçalho azul e linhas zebradas, quebrando página quando necessário."""
        if df.empty:
            self.set_font("Helvetica", "I", 8)
            self.cell(0, 5, "  Sem dados.", ln=True)
            self.ln(2)
            return

        colunas = list(df.columns)
        n = len(colunas)
        largura_util = 190
        widths = col_widths or [largura_util / n] * n

        # Cabeçalho
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(31, 107, 181)
        self.set_text_color(255, 255, 255)
        for col, w in zip(colunas, widths):
            self.cell(w, 6, _pdf_safe(str(col))[:22], border=0, fill=True)
        self.ln()
        self.set_text_color(0, 0, 0)

        # Linhas
        self.set_font("Helvetica", "", 7)
        fill = False
        for _, row in df.iterrows():
            if self.get_y() > 270:
                self.add_page()
            self.set_fill_color(248, 250, 252) if fill else self.set_fill_color(255, 255, 255)
            for val, w in zip(row, widths):
                self.cell(w, 5, _pdf_safe(str(val))[:28], border=0, fill=True)
            self.ln()
            fill = not fill
        self.ln(3)

    def comentario(self, texto: str):
        """Desenha o bloco de comentário gerencial (fundo amarelo claro), se houver texto."""
        if not texto.strip():
            return
        self.ln(4)
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(255, 249, 219)
        self.cell(0, 6, "  Comentario Gerencial", fill=True, ln=True)
        self.set_font("Helvetica", "", 8)
        self.multi_cell(0, 5, "  " + _pdf_safe(texto))
        self.ln(2)


def gerar_pdf(titulo: str,
              kpis: dict[str, Any],
              secoes: dict[str, pd.DataFrame],
              periodo_ini: date | None = None,
              periodo_fim: date | None = None,
              comentario: str = "") -> bytes:
    """
    Gera um PDF formatado com KPIs, tabelas e comentário gerencial.
    kpis: {'Label': 'Valor formatado', ...}
    secoes: {'Título da seção': dataframe, ...}
    """
    periodo_str = ""
    if periodo_ini and periodo_fim:
        periodo_str = (f"Período: {periodo_ini.strftime('%d/%m/%Y')} "
                       f"a {periodo_fim.strftime('%d/%m/%Y')}")
    elif periodo_ini:
        periodo_str = f"A partir de {periodo_ini.strftime('%d/%m/%Y')}"
    elif periodo_fim:
        periodo_str = f"Até {periodo_fim.strftime('%d/%m/%Y')}"

    pdf = _PDF(titulo=titulo, periodo=periodo_str)
    pdf.add_page()

    # KPIs
    if kpis:
        pdf.secao("Indicadores Gerais")
        for label, valor in kpis.items():
            pdf.kpi_linha(label, str(valor))
        pdf.ln(2)

    # Tabelas de seções
    for nome_secao, df in secoes.items():
        if df is not None and not df.empty:
            pdf.secao(nome_secao)
            pdf.tabela(df)

    # Comentário gerencial
    if comentario.strip():
        pdf.comentario(comentario)

    return pdf.output()
