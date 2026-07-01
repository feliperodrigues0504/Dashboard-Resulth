"""
components/painel/render.py — renderizadores genéricos dos widgets do Painel
Personalizado, usando MUI/Nivo (streamlit_elements) em vez de Plotly/AgGrid —
dentro de um dashboard.Item arrastável só dá pra usar elementos da própria
lib (ver decisão registrada na auditoria: st.plotly_chart/st.dataframe não
ficam presos ao card). Cada função recebe o dict já adaptado por
core/dashboard/adapters.py — nenhuma lógica de negócio aqui, só desenho.
"""
from __future__ import annotations
from streamlit_elements import mui, nivo
from components.metrics import fmt_brl

_FORMATADORES = {
    "brl": fmt_brl,
    "int": lambda v: f"{v:,.0f}".replace(",", "."),
    "pct": lambda v: f"{v:.1f}%",
    "raw": lambda v: str(v),
}

_SEM_DADOS_SX = {"color": "text.secondary", "fontStyle": "italic"}


def _sem_dados(msg: str = "Sem dados no período."):
    mui.Typography(msg, variant="body2", sx=_SEM_DADOS_SX)


def render_kpi(dado: dict):
    """Widget tipo KPI: um número grande formatado."""
    formatador = _FORMATADORES.get(dado.get("formatador", "raw"), str)
    try:
        texto = formatador(dado.get("valor", 0))
    except Exception:
        texto = str(dado.get("valor", "-"))
    mui.Typography(texto, variant="h5", sx={"fontWeight": 700})


def render_progresso(dado: dict):
    """Widget tipo progresso: barra de % (usada no lugar de gauge — Nivo não tem gauge nativo)."""
    pct = max(0, min(100, dado.get("pct", 0)))
    mui.LinearProgress(variant="determinate", value=pct, sx={"height": 10, "borderRadius": 5, "mb": 1})
    mui.Typography(f"{pct:.0f}% {dado.get('detalhe', '')}", variant="body2")


def render_bar(dado: dict):
    """Widget tipo gráfico de barras (Nivo Bar)."""
    if not dado.get("data"):
        _sem_dados(); return
    with mui.Box(sx={"height": 200}):
        nivo.Bar(
            data=dado["data"], keys=dado["keys"], indexBy=dado["index_by"],
            margin={"top": 10, "right": 10, "bottom": 40, "left": 50},
            padding=0.3, colors={"scheme": "blues"},
            axisBottom={"tickRotation": -30}, enableLabel=False,
        )


def render_line(dado: dict):
    """Widget tipo gráfico de linha (Nivo Line) — suporta 1 ou várias séries."""
    serie = dado.get("data", [])
    if not serie or not any(s.get("data") for s in serie):
        _sem_dados(); return
    with mui.Box(sx={"height": 200}):
        nivo.Line(
            data=serie, margin={"top": 10, "right": 20, "bottom": 40, "left": 50},
            xScale={"type": "point"}, axisBottom={"tickRotation": -30},
            colors={"scheme": "blues"}, pointSize=6, useMesh=True,
        )


def render_pie(dado: dict):
    """Widget tipo gráfico de pizza (Nivo Pie)."""
    if not dado.get("data"):
        _sem_dados(); return
    with mui.Box(sx={"height": 200}):
        nivo.Pie(
            data=dado["data"], margin={"top": 10, "right": 10, "bottom": 30, "left": 10},
            innerRadius=0.5, padAngle=0.5, cornerRadius=3, colors={"scheme": "blues"},
        )


def render_tabela(dado: dict):
    """Widget tipo tabela (MUI Table) — só as colunas/linhas já recortadas pelo adapter."""
    if not dado.get("linhas"):
        _sem_dados("Sem dados."); return
    with mui.Table(size="small"):
        with mui.TableHead():
            with mui.TableRow():
                for c in dado["colunas"]:
                    mui.TableCell(c)
        with mui.TableBody():
            for linha in dado["linhas"]:
                with mui.TableRow():
                    for v in linha:
                        mui.TableCell(v)


def render_lista_alertas(dado: dict):
    """Widget tipo lista (alertas ativos)."""
    itens = dado.get("itens", [])
    if not itens:
        _sem_dados("Sem alertas ativos."); return
    with mui.List(dense=True):
        for it in itens[:8]:
            with mui.ListItem(disableGutters=True):
                mui.ListItemText(primary=it["titulo"], secondary=f"{it['modulo']} · {it['nivel'].upper()}")


def render_nav(dado: dict):
    """Widget tipo navegação: botões de atalho para os módulos do sistema."""
    itens = dado.get("itens", [])
    if not itens:
        _sem_dados("Sem módulos configurados."); return
    with mui.Stack(spacing=1):
        for it in itens:
            mui.Button(
                it["label"], href=it["href"], variant="outlined", fullWidth=True,
                sx={"justifyContent": "flex-start", "textTransform": "none"})


RENDER_POR_TIPO = {
    "kpi": render_kpi,
    "progresso": render_progresso,
    "bar": render_bar,
    "line": render_line,
    "pie": render_pie,
    "tabela": render_tabela,
    "lista_alertas": render_lista_alertas,
    "nav": render_nav,
}
