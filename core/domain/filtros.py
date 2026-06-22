"""
Aplicação dos filtros globais a um DataFrame — lógica de negócio pura
(sem renderização). A UI da sidebar que produz o dict de filtros está em
components/sidebar_filtros.py.
"""
from __future__ import annotations
from datetime import date
import streamlit as st
import pandas as pd


def aplicar(df: pd.DataFrame, filtros: dict,
            mapa: dict[str, str]) -> pd.DataFrame:
    """
    Aplica os filtros ativos ao dataframe.
    mapa: ex. {'empresa': 'CODEMPRESA', 'vendedor': 'CODVENDEDOR'}
    Apenas colunas presentes no df e com valor != 'Todos'/'Todas' são filtradas.
    """
    if df.empty:
        return df

    resultado = df.copy()
    opcoes_df = _get_opcoes_df()

    # Período — sempre aplicado se a coluna de data existir
    data_ini = pd.Timestamp(filtros.get("data_ini", date(2000, 1, 1)))
    data_fim = pd.Timestamp(filtros.get("data_fim", date(2099, 12, 31))) + pd.Timedelta(days=1)
    col_data = mapa.get("periodo")
    if col_data and col_data in resultado.columns:
        resultado = resultado[
            (resultado[col_data] >= data_ini) &
            (resultado[col_data] <  data_fim)
        ]

    # Demais filtros
    for chave_filtro, col_df in mapa.items():
        if chave_filtro == "periodo":
            continue
        valor = filtros.get(chave_filtro, "Todos")
        if valor in ("Todos", "Todas", None, ""):
            continue
        if col_df not in resultado.columns:
            continue

        # Converte o nome selecionado para o código correspondente
        cod = _nome_para_cod(chave_filtro, valor, opcoes_df)
        if cod:
            resultado = resultado[resultado[col_df].astype(str).str.strip() == str(cod).strip()]

    return resultado.reset_index(drop=True)


# ── helpers internos ──────────────────────────────────────────────

def _get_opcoes_df() -> dict:
    """Retorna os dataframes de cadastro do session_state (se já carregados)."""
    return st.session_state.get("opcoes_cadastros", {})


def _nome_para_cod(chave: str, nome: str, opcoes_df: dict) -> str | None:
    """Converte o nome selecionado no selectbox para o código do cadastro."""
    mapa_df = {
        "empresa":    "empresas_df",
        "vendedor":   "vendedores_df",
        "cliente":    "clientes_df",
        "fornecedor": "fornecedores_df",
        "grupo":      "grupos_df",
        "marca":      "marcas_df",
    }
    key = mapa_df.get(chave)
    if not key or key not in opcoes_df:
        return None
    df = opcoes_df[key]
    match = df[df["NOME"] == nome]
    if match.empty:
        return None
    return str(match.iloc[0]["COD"]).strip()
