"""
core/dashboard/adapters.py — converte a saída das funções de core/domain/*
(DataFrames/dicts comuns) em estruturas JSON-prontas para os widgets do
Painel Personalizado (Nivo/MUI). Nenhuma dependência de Streamlit aqui —
só transformação de dados, igual ao resto de core/domain.
"""
from __future__ import annotations
import pandas as pd


def filtra_periodo(df: pd.DataFrame, col: str, data_ini, data_fim) -> pd.DataFrame:
    """Filtra `df` pela coluna de data `col` entre data_ini/data_fim (inclusive) — usado pelos widgets que recebem período do painel."""
    if df is None or df.empty or col not in df.columns:
        return df
    ini = pd.Timestamp(data_ini)
    fim = pd.Timestamp(data_fim) + pd.Timedelta(days=1)
    return df[(df[col] >= ini) & (df[col] < fim)].reset_index(drop=True)


def kpi(valor, formatador: str = "brl") -> dict:
    """Widget tipo KPI: um único número grande, com seu formatador (brl/int/pct/raw)."""
    return {"valor": valor, "formatador": formatador}


def progresso(pct: float, detalhe: str = "") -> dict:
    """Widget tipo progresso (barra de % — usado no lugar de gauge, ver nota da Fase 5)."""
    return {"pct": float(pct or 0), "detalhe": detalhe}


def bar_de_df(df: pd.DataFrame, index_col: str, value_col: str, serie_nome: str | None = None) -> dict:
    """Widget tipo gráfico de barras (Nivo Bar) a partir de um DataFrame com 1 série."""
    if df is None or df.empty:
        return {"data": [], "keys": [], "index_by": "x"}
    serie_nome = serie_nome or value_col
    data = [{"x": str(row[index_col]), serie_nome: float(row[value_col] or 0)} for _, row in df.iterrows()]
    return {"data": data, "keys": [serie_nome], "index_by": "x"}


def line_de_df(df: pd.DataFrame, x_col: str, y_col: str, serie_nome: str = "Valor") -> dict:
    """Widget tipo gráfico de linha (Nivo Line) a partir de um DataFrame com 1 série."""
    if df is None or df.empty:
        return {"data": [{"id": serie_nome, "data": []}]}
    pontos = [{"x": str(row[x_col]), "y": float(row[y_col] or 0)} for _, row in df.iterrows()]
    return {"data": [{"id": serie_nome, "data": pontos}]}


def pie_de_df(df: pd.DataFrame, label_col: str, value_col: str) -> dict:
    """Widget tipo gráfico de pizza (Nivo Pie) a partir de um DataFrame."""
    if df is None or df.empty:
        return {"data": []}
    data = [{"id": str(row[label_col]), "label": str(row[label_col]), "value": float(row[value_col] or 0)}
            for _, row in df.iterrows()]
    return {"data": data}


def tabela_de_df(df: pd.DataFrame, colunas: list[str] | None = None, max_linhas: int = 8) -> dict:
    """Widget tipo tabela (MUI Table) — limita colunas/linhas para caber num card pequeno."""
    if df is None or df.empty:
        return {"colunas": [], "linhas": []}
    colunas = colunas or list(df.columns)[:5]
    colunas = [c for c in colunas if c in df.columns]
    linhas = df[colunas].head(max_linhas).astype(str).values.tolist()
    return {"colunas": [str(c) for c in colunas], "linhas": linhas}


def lista_alertas(alertas: list[dict] | None) -> dict:
    """Widget tipo lista (alertas ativos)."""
    alertas = alertas or []
    return {"itens": [{"titulo": a["titulo"], "modulo": a["modulo"], "nivel": a["nivel"]} for a in alertas]}


def multiline_de_df(df: pd.DataFrame, x_col: str, series_map: dict[str, str]) -> dict:
    """Widget tipo linha com várias séries (Nivo Line) — series_map: {coluna_do_df: nome_da_série}."""
    if df is None or df.empty:
        return {"data": [{"id": nome, "data": []} for nome in series_map.values()]}
    series = []
    for col, nome in series_map.items():
        if col not in df.columns:
            continue
        pontos = [{"x": str(row[x_col]), "y": float(row[col] or 0)} for _, row in df.iterrows()]
        series.append({"id": nome, "data": pontos})
    return {"data": series}


def nav(itens: list[dict]) -> dict:
    """Widget tipo navegação: lista de {label, href} para os módulos do sistema."""
    return {"itens": itens or []}
