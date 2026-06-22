"""
Camada de acesso a dados do módulo Estoque/Produtos.
Fontes: COMPPROD (estoque atual), MVGERAL (movimentações), PRODUTO, GRUPROD
MVGERAL.TIPOMOV: '55'=venda PDV, '01'=entrada NF, '09'=saída consignação/orçamento,
                 '61'=devolução entrada, '05'=devolução venda, '06'/'11'=ajustes
Estoque real: COMPPROD com CODEMPRESA='00' (CODEMPRESA='01' sempre zerada)

Só consulta o Firebird e devolve DataFrames com tipos coagidos — regras de
negócio (curva ABC, giro, estoque parado) vivem em core/domain/estoque.py.
"""
from __future__ import annotations

import pandas as pd
from core.data.firebird import fb_query

_EMP_ESTOQUE = "00"   # empresa que mantém o saldo real de estoque no COMPPROD

# ─────────────────────────────────────────────────────────────────────────────
#  SQL — Estoque geral (COMPPROD × PRODUTO × GRUPROD)
# ─────────────────────────────────────────────────────────────────────────────
_SQL_ESTOQUE_GERAL = """
SELECT
    TRIM(c.CODPROD)         AS CODPROD,
    TRIM(p.DESCRICAO)       AS DESCRICAO,
    TRIM(g.DESCRICAO)       AS GRUPO,
    TRIM(g.CODGRUPO)        AS CODGRUPO,
    c.ESTOQUE               AS QTD,
    c.PRECOCUSTO            AS CUSTO_UNIT,
    p.PRECO                 AS VENDA_UNIT,
    c.ESTMINIMO             AS EST_MINIMO,
    c.ESTMAXIMO             AS EST_MAXIMO,
    TRIM(p.ATIVO)           AS ATIVO,
    p.DATA_ULT_ENT1         AS DT_ULT_ENTRADA,
    p.PR_ULT_ENT1           AS PRECO_ULT_ENTRADA
FROM COMPPROD c
JOIN PRODUTO p ON p.CODPROD = c.CODPROD
LEFT JOIN GRUPROD g ON g.CODGRUPO = p.CODGRUPO
WHERE TRIM(c.CODEMPRESA) = ?
ORDER BY c.ESTOQUE * c.PRECOCUSTO DESC
"""

# ─────────────────────────────────────────────────────────────────────────────
#  SQL — Última venda por produto (para cálculo de estoque parado)
# ─────────────────────────────────────────────────────────────────────────────
_SQL_ULT_VENDA = """
SELECT
    TRIM(m.CODPROD)    AS CODPROD,
    MAX(m.DT_MOVIMENTO) AS ULT_VENDA
FROM MVGERAL m
WHERE TRIM(m.TIPOMOV) = '55'
GROUP BY m.CODPROD
"""

# ─────────────────────────────────────────────────────────────────────────────
#  SQL — Movimentações de um produto (drill-down)
# ─────────────────────────────────────────────────────────────────────────────
_SQL_MOV_PRODUTO = """
SELECT FIRST 200
    m.DT_MOVIMENTO          AS DT_MOVIMENTO,
    TRIM(m.TIPOMOV)         AS TIPOMOV,
    TRIM(m.TIPOAGENTE)      AS TIPOAGENTE,
    TRIM(m.CODIGOAGENTE)    AS CODIGOAGENTE,
    m.QUANTIDADE            AS QUANTIDADE,
    m.PRECOCUSTO            AS CUSTO_UNIT,
    m.PRECOVENDA            AS VENDA_UNIT,
    m.ESTOQANT              AS ESTQ_ANTERIOR
FROM MVGERAL m
WHERE TRIM(m.CODPROD) = ?
ORDER BY m.DT_MOVIMENTO DESC, m.SEQUENCIA DESC
"""

# ─────────────────────────────────────────────────────────────────────────────
#  SQL — Vendas por produto no período (top produtos / giro)
# ─────────────────────────────────────────────────────────────────────────────
_SQL_VENDAS_PERIODO = """
SELECT
    TRIM(m.CODPROD)                     AS CODPROD,
    SUM(m.QUANTIDADE)                   AS QTD_VENDIDA,
    SUM(m.QUANTIDADE * m.PRECOVENDA)    AS FAT_TOTAL
FROM MVGERAL m
WHERE TRIM(m.TIPOMOV) = '55'
  AND m.DT_MOVIMENTO >= CAST(? AS TIMESTAMP)
  AND m.DT_MOVIMENTO <  CAST(? AS TIMESTAMP)
GROUP BY m.CODPROD
"""


def fetch_estoque_geral() -> pd.DataFrame:
    """Todos os produtos com saldo de estoque (COMPPROD×PRODUTO×GRUPROD) da empresa matriz, com VALOR_CUSTO/VALOR_VENDA calculados."""
    try:
        df = fb_query(_SQL_ESTOQUE_GERAL, (_EMP_ESTOQUE,))
        if df.empty:
            return df
        for col in ("QTD", "CUSTO_UNIT", "VENDA_UNIT", "EST_MINIMO", "EST_MAXIMO", "PRECO_ULT_ENTRADA"):
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        df["VALOR_CUSTO"] = df["QTD"] * df["CUSTO_UNIT"]
        df["VALOR_VENDA"] = df["QTD"] * df["VENDA_UNIT"]
        df["DT_ULT_ENTRADA"] = pd.to_datetime(df["DT_ULT_ENTRADA"], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


def fetch_ultima_venda() -> pd.DataFrame:
    """Data da última venda PDV (MVGERAL TIPOMOV='55') de cada produto."""
    try:
        df = fb_query(_SQL_ULT_VENDA)
        if not df.empty:
            df["ULT_VENDA"] = pd.to_datetime(df["ULT_VENDA"], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame(columns=["CODPROD", "ULT_VENDA"])


def fetch_vendas_periodo(data_ini: str, data_fim: str) -> pd.DataFrame:
    """Quantidade vendida e faturamento PDV por produto, entre `data_ini` e `data_fim`."""
    try:
        return fb_query(_SQL_VENDAS_PERIODO, (data_ini, data_fim))
    except Exception:
        return pd.DataFrame()


def fetch_movimentacoes_produto(codprod: str) -> pd.DataFrame:
    """Histórico de movimentações de estoque (MVGERAL) de um produto, mais recentes primeiro."""
    try:
        df = fb_query(_SQL_MOV_PRODUTO, (codprod.strip(),))
        if df.empty:
            return df
        for col in ("QUANTIDADE", "CUSTO_UNIT", "VENDA_UNIT", "ESTQ_ANTERIOR"):
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        df["DT_MOVIMENTO"] = pd.to_datetime(df["DT_MOVIMENTO"], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()
