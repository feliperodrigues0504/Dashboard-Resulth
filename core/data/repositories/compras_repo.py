"""
Camada de acesso a dados do módulo Compras.
Fontes: NFENTRC (NF entrada cabeçalho), NFENTRI (itens), FORNECE, RELPRFO.
Só consulta o Firebird e devolve DataFrames — regras de negócio (rentabilidade
por fornecedor, produtos sem giro) vivem em core/domain/compras.py.
"""
from __future__ import annotations

import pandas as pd
from core.data.firebird import fb_query

# ─────────────────────────────────────────────────────────────────────────────
#  SQL — Histórico de compras por mês
# ─────────────────────────────────────────────────────────────────────────────
_SQL_HISTORICO_MENSAL = """
SELECT
    EXTRACT(YEAR  FROM n.DT_ENTRADA) AS ANO,
    EXTRACT(MONTH FROM n.DT_ENTRADA) AS MES,
    COUNT(DISTINCT n.NUMERONF)       AS QTD_NF,
    COUNT(DISTINCT TRIM(n.CODFORNEC)) AS QTD_FORNEC,
    SUM(n.TOTALNF)                   AS TOTAL_COMPRADO
FROM NFENTRC n
WHERE n.DT_ENTRADA >= CAST(? AS TIMESTAMP)
GROUP BY ANO, MES
ORDER BY ANO DESC, MES DESC
"""

# ─────────────────────────────────────────────────────────────────────────────
#  SQL — Compras por fornecedor no período
# ─────────────────────────────────────────────────────────────────────────────
_SQL_COMPRAS_FORNECEDOR = """
SELECT
    TRIM(n.CODFORNEC)               AS CODFORNEC,
    TRIM(f.NOME)                    AS FORNECEDOR,
    TRIM(f.NOMEFANTASIA)            AS FANTASIA,
    COUNT(DISTINCT n.NUMERONF)      AS QTD_NF,
    SUM(n.TOTALNF)                  AS TOTAL_COMPRADO
FROM NFENTRC n
LEFT JOIN FORNECE f ON f.CODFORNEC = n.CODFORNEC
WHERE n.DT_ENTRADA >= CAST(? AS TIMESTAMP)
  AND n.DT_ENTRADA <  CAST(? AS TIMESTAMP)
GROUP BY n.CODFORNEC, f.NOME, f.NOMEFANTASIA
ORDER BY TOTAL_COMPRADO DESC
"""

# ─────────────────────────────────────────────────────────────────────────────
#  SQL — NFs de um fornecedor (drill-down nível 1)
# ─────────────────────────────────────────────────────────────────────────────
_SQL_NFS_FORNECEDOR = """
SELECT
    TRIM(n.NUMERONF)    AS NUMERONF,
    n.DT_ENTRADA        AS DT_ENTRADA,
    n.DT_EMISSAO        AS DT_EMISSAO,
    n.TOTALNF           AS TOTAL_NF,
    n.DESCPERC          AS DESC_PERC,
    n.TOTALIPI          AS TOTAL_IPI
FROM NFENTRC n
WHERE TRIM(n.CODFORNEC) = ?
  AND n.DT_ENTRADA >= CAST(? AS TIMESTAMP)
  AND n.DT_ENTRADA <  CAST(? AS TIMESTAMP)
ORDER BY n.DT_ENTRADA DESC
"""

# ─────────────────────────────────────────────────────────────────────────────
#  SQL — Itens de uma NF (drill-down nível 2)
# ─────────────────────────────────────────────────────────────────────────────
_SQL_ITENS_NF = """
SELECT FIRST 500
    TRIM(i.CODPROD)     AS CODPROD,
    TRIM(p.DESCRICAO)   AS PRODUTO,
    TRIM(g.DESCRICAO)   AS GRUPO,
    i.QUANTIDADE        AS QUANTIDADE,
    i.PRECONF           AS CUSTO_UNIT,
    i.DESCVLR           AS DESCONTO,
    i.QUANTIDADE * i.PRECONF  AS TOTAL_ITEM
FROM NFENTRI i
LEFT JOIN PRODUTO p ON p.CODPROD = i.CODPROD
LEFT JOIN GRUPROD g ON g.CODGRUPO = p.CODGRUPO
WHERE TRIM(i.CODFORNEC) = ?
  AND TRIM(i.NUMERONF)  = ?
ORDER BY i.SEQUENCIADIGITACAO
"""

# ─────────────────────────────────────────────────────────────────────────────
#  SQL — Itens comprados no período (para análise de sem-giro)
# ─────────────────────────────────────────────────────────────────────────────
_SQL_ITENS_PERIODO = """
SELECT
    TRIM(i.CODPROD)     AS CODPROD,
    TRIM(i.CODFORNEC)   AS CODFORNEC,
    SUM(i.QUANTIDADE)   AS QTD_COMPRADA,
    SUM(i.QUANTIDADE * i.PRECONF) AS VALOR_COMPRADO
FROM NFENTRI i
JOIN NFENTRC n ON n.CODEMPRESA = i.CODEMPRESA
               AND n.NUMERONF  = i.NUMERONF
               AND n.CODFORNEC = i.CODFORNEC
WHERE n.DT_ENTRADA >= CAST(? AS TIMESTAMP)
  AND n.DT_ENTRADA <  CAST(? AS TIMESTAMP)
GROUP BY i.CODPROD, i.CODFORNEC
"""

# ─────────────────────────────────────────────────────────────────────────────
#  SQL — Vendas PDV no período por produto (para rentabilidade)
# ─────────────────────────────────────────────────────────────────────────────
_SQL_VENDAS_PROD = """
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

# ─────────────────────────────────────────────────────────────────────────────
#  SQL — Relação produto-fornecedor
# ─────────────────────────────────────────────────────────────────────────────
_SQL_RELPRFO = """
SELECT
    TRIM(r.CODPROD)    AS CODPROD,
    TRIM(r.CODFORNEC)  AS CODFORNEC,
    TRIM(r.PRINCIPAL)  AS PRINCIPAL
FROM RELPRFO r
"""

# ─────────────────────────────────────────────────────────────────────────────
#  SQL — Estoque atual por produto (para cruzar com fornecedor)
# ─────────────────────────────────────────────────────────────────────────────
_SQL_ESTOQUE_PROD = """
SELECT
    TRIM(c.CODPROD)                 AS CODPROD,
    c.ESTOQUE                       AS QTD,
    c.PRECOCUSTO                    AS CUSTO_UNIT,
    c.ESTOQUE * c.PRECOCUSTO        AS VALOR_CUSTO
FROM COMPPROD c
WHERE TRIM(c.CODEMPRESA) = '00'
  AND c.ESTOQUE > 0
"""

_SQL_KPIS_COMPRAS = """
    SELECT COUNT(DISTINCT TRIM(n.CODFORNEC)) AS QTD_FORNEC,
           COUNT(DISTINCT n.NUMERONF)        AS QTD_NF,
           SUM(n.TOTALNF)                    AS TOTAL_COMPRADO
    FROM NFENTRC n
    WHERE n.DT_ENTRADA >= CAST(? AS TIMESTAMP)
      AND n.DT_ENTRADA <  CAST(? AS TIMESTAMP)
"""

_SQL_FORNECEDORES_BASICO = """
    SELECT TRIM(CODFORNEC) AS CODFORNEC, TRIM(NOME) AS FORNECEDOR,
           TRIM(NOMEFANTASIA) AS FANTASIA FROM FORNECE
"""


def fetch_historico_mensal(corte_str: str) -> pd.DataFrame:
    """Compras mensais (NFENTRC) desde `corte_str`, agrupadas por ano/mês."""
    try:
        return fb_query(_SQL_HISTORICO_MENSAL, (corte_str,))
    except Exception:
        return pd.DataFrame()


def fetch_compras_fornecedor(data_ini: str, data_fim: str) -> pd.DataFrame:
    """Compras agregadas por fornecedor entre `data_ini` e `data_fim`, ordenadas por total comprado."""
    try:
        return fb_query(_SQL_COMPRAS_FORNECEDOR, (data_ini, data_fim))
    except Exception:
        return pd.DataFrame()


def fetch_nfs_fornecedor(codfornec: str, data_ini: str, data_fim: str) -> pd.DataFrame:
    """NFs de entrada de um fornecedor específico no período (drill-down nível 1)."""
    try:
        return fb_query(_SQL_NFS_FORNECEDOR, (codfornec.strip(), data_ini, data_fim))
    except Exception:
        return pd.DataFrame()


def fetch_itens_nf_entrada(codfornec: str, numeronf: str) -> pd.DataFrame:
    """Itens de uma NF de entrada específica (drill-down nível 2)."""
    try:
        return fb_query(_SQL_ITENS_NF, (codfornec.strip(), numeronf.strip()))
    except Exception:
        return pd.DataFrame()


def fetch_relprfo() -> pd.DataFrame:
    """Relação produto-fornecedor (RELPRFO) completa — quem é o fornecedor principal de cada produto."""
    try:
        return fb_query(_SQL_RELPRFO)
    except Exception:
        return pd.DataFrame(columns=["CODPROD", "CODFORNEC", "PRINCIPAL"])


def fetch_estoque_prod() -> pd.DataFrame:
    """Estoque atual (COMPPROD) de cada produto com saldo > 0, com VALOR_CUSTO já calculado."""
    try:
        df = fb_query(_SQL_ESTOQUE_PROD)
        if not df.empty:
            for col in ("QTD", "CUSTO_UNIT", "VALOR_CUSTO"):
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        return df
    except Exception:
        return pd.DataFrame(columns=["CODPROD", "QTD", "CUSTO_UNIT", "VALOR_CUSTO"])


def fetch_itens_periodo(data_ini: str, data_fim: str) -> pd.DataFrame:
    """Itens comprados (NFENTRI) entre `data_ini` e `data_fim`, agrupados por produto/fornecedor."""
    try:
        return fb_query(_SQL_ITENS_PERIODO, (data_ini, data_fim))
    except Exception:
        return pd.DataFrame()


def fetch_vendas_prod(data_ini: str, data_fim: str) -> pd.DataFrame:
    """Quantidade vendida e faturamento PDV por produto, entre `data_ini` e `data_fim` (para rentabilidade)."""
    try:
        return fb_query(_SQL_VENDAS_PROD, (data_ini, data_fim))
    except Exception:
        return pd.DataFrame()


def fetch_fornecedores_basico() -> pd.DataFrame:
    """Cadastro básico de fornecedores (código, nome, fantasia) — sem filtro de período."""
    try:
        return fb_query(_SQL_FORNECEDORES_BASICO)
    except Exception:
        return pd.DataFrame(columns=["CODFORNEC", "FORNECEDOR", "FANTASIA"])


def fetch_kpis_compras_raw(data_ini: str, data_fim: str) -> pd.DataFrame:
    """Contagem de fornecedores/NFs e total comprado no período (linha única, para os KPIs de Compras)."""
    try:
        return fb_query(_SQL_KPIS_COMPRAS, (data_ini, data_fim))
    except Exception:
        return pd.DataFrame()
