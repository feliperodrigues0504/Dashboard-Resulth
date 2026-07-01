"""
core/dashboard/widgets_geral.py — widgets cross-módulo do Painel Personalizado
("O que mudou desde ontem", histórico de KPIs, navegação entre módulos).
Busca Global (Spotlight) e o atalho de Relatório Executivo não entraram
aqui: são ferramentas interativas (busca com texto, botão de download), não
widgets de exibição — não fazem sentido como card arrastável de dados, então
ficam como seções fixas em app.py, fora do grid.
"""
from __future__ import annotations
from datetime import date

from core.dashboard import adapters as ad
from core.domain.financeiro import get_contas_receber, get_contas_pagar, get_estoque_custo, get_saldo_bancario, get_kpis
from core.domain.comercial import get_faturamento
from core.sync.snapshot import get_comparativo_diario, get_evolucao_kpis


def _kpis_atuais_e_fat_mes():
    df_ar, df_ap = get_contas_receber(), get_contas_pagar()
    kpis = get_kpis(df_ar, df_ap, get_estoque_custo(), get_saldo_bancario())
    df_fat = get_faturamento(meses_historico=1)
    fat_mes = 0.0
    if not df_fat.empty:
        import pandas as pd
        df_fat["DATAFATURA"] = pd.to_datetime(df_fat["DATAFATURA"], errors="coerce")
        hoje = pd.Timestamp.now()
        ini_mes = pd.Timestamp(hoje.year, hoje.month, 1)
        fat_mes = float(df_fat[df_fat["DATAFATURA"] >= ini_mes]["TOTALPEDIDO"].sum())
    return kpis, fat_mes


def _fetch_delta(chave: str, formatador: str = "brl"):
    def _fetch(data_ini: date, data_fim: date) -> dict:
        kpis, fat_mes = _kpis_atuais_e_fat_mes()
        comparativo = get_comparativo_diario(kpis, fat_mes)
        if comparativo is None:
            return ad.kpi(0, formatador)
        return ad.kpi(comparativo.get(chave, 0), formatador)
    return _fetch


def _fetch_historico_caixa_ar(data_ini: date, data_fim: date) -> dict:
    df = get_evolucao_kpis()
    return ad.multiline_de_df(df, "data", {"vencido_ar": "AR Vencido", "saldo_bco": "Caixa"})


def _fetch_historico_capital(data_ini: date, data_fim: date) -> dict:
    df = get_evolucao_kpis()
    return ad.line_de_df(df, "data", "capital_op", "Capital Operacional")


def _fetch_modulos_nav(data_ini: date, data_fim: date) -> dict:
    return ad.nav([
        {"label": "💰 Financeiro", "href": "/Financeiro"},
        {"label": "📈 Comercial", "href": "/Comercial"},
        {"label": "📦 Estoque", "href": "/Estoque"},
        {"label": "🛒 Compras", "href": "/Compras"},
        {"label": "🔔 Alertas", "href": "/Alertas"},
    ])


WIDGETS_GERAL = [
    {"id": "ger_delta_caixa", "nome": "Variação do Caixa (desde ontem)", "origem": "Home",
     "descricao": "Diferença do saldo bancário desde o snapshot anterior.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_delta("delta_saldo_bco")},
    {"id": "ger_delta_fat", "nome": "Variação do Faturamento (desde ontem)", "origem": "Home",
     "descricao": "Diferença do faturamento do mês desde o snapshot anterior.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_delta("delta_fat_mes")},
    {"id": "ger_delta_ar_vencido", "nome": "Variação do AR Vencido (desde ontem)", "origem": "Home",
     "descricao": "Diferença do AR vencido desde o snapshot anterior.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_delta("delta_vencido_ar")},
    {"id": "ger_delta_capital", "nome": "Variação do Capital Operacional (desde ontem)", "origem": "Home",
     "descricao": "Diferença do capital operacional desde o snapshot anterior.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_delta("delta_capital_op")},
    {"id": "ger_historico_caixa_ar", "nome": "Histórico — AR Vencido vs Caixa", "origem": "Home",
     "descricao": "Evolução diária (snapshots) do AR vencido e do caixa.", "tipo": "line", "w": 6, "h": 4,
     "fetch": _fetch_historico_caixa_ar},
    {"id": "ger_historico_capital", "nome": "Histórico — Capital Operacional", "origem": "Home",
     "descricao": "Evolução diária (snapshots) do capital operacional.", "tipo": "line", "w": 6, "h": 4,
     "fetch": _fetch_historico_capital},
    {"id": "ger_modulos_nav", "nome": "Módulos do Sistema", "origem": "Home",
     "descricao": "Atalhos de navegação para os módulos do sistema.", "tipo": "nav", "w": 3, "h": 4,
     "fetch": _fetch_modulos_nav},
]
