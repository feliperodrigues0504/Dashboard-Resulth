"""Componentes reutilizáveis de KPI para Streamlit."""
import streamlit as st
from components.theme import COR_PRIM as _COR_PRIM, COR_OK as _COR_OK, COR_PERIGO as _COR_RUIM


def fmt_brl(valor: float) -> str:
    """Formata float como moeda brasileira: R$ 1.234,56"""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(valor: float, decimais: int = 1) -> str:
    """Formata float como percentual: 12,3%"""
    return f"{valor:.{decimais}f}%".replace(".", ",")


def kpi_card(label: str, valor: float, delta: float | None = None,
             delta_label: str = "", negativo_ruim: bool = True,
             cor: str = _COR_PRIM, fmt=fmt_brl):
    """
    Card KPI com fundo, borda de destaque e delta colorido com seta.
    `cor`: cor da borda esquerda de destaque (default azul primário).
           Use as constantes de components.theme (COR_OK/COR_ALERTA/COR_PERIGO)
           para sinalizar contexto (ex.: valores vencidos/críticos em vermelho).
    `fmt`: função de formatação do valor principal e do delta (default fmt_brl).
           Passe `lambda v: f"{v:,.0f}"` para KPIs de contagem (não-monetários).
    """
    delta_html = ""
    if delta is not None:
        piora = (delta > 0) if negativo_ruim else (delta < 0)
        cor_delta = _COR_RUIM if piora else _COR_OK
        seta = "▲" if delta >= 0 else "▼"
        sinal = "+" if delta >= 0 else ""
        delta_html = (
            f"<div style='font-size:0.78em;color:{cor_delta};font-weight:600;"
            f"margin-top:3px'>{seta} {sinal}{fmt(delta)} {delta_label}</div>"
        )
    st.markdown(
        f"<div style='background:#f8f9fa;border-radius:10px;padding:12px 14px;"
        f"border-left:4px solid {cor};height:100%'>"
        f"<div style='font-size:0.76em;color:#666;font-weight:600;"
        f"text-transform:uppercase;letter-spacing:0.3px;margin-bottom:4px;"
        f"white-space:nowrap;overflow:hidden;text-overflow:ellipsis' title='{label}'>{label}</div>"
        f"<div style='font-size:1.45em;font-weight:700;color:#1a1a2e;line-height:1.15'>"
        f"{fmt(valor)}</div>"
        f"{delta_html}"
        f"</div>",
        unsafe_allow_html=True,
    )
