"""
Camada de acesso a dados do módulo comercial.
Só consulta o Firebird (read-only) e devolve DataFrames com tipos coagidos —
nenhuma regra de negócio (KPI, ranking, curva ABC) vive aqui. Isso está em
core/domain/comercial.py, que consome estas funções.

Base de faturamento: PEDIDOC (FATURADO='S') — ver docs/MODULO_COMERCIAL.md
para a justificativa da escolha frente a ENCEFAT/NFSAIDC.
"""
import pandas as pd
from core.data.firebird import fb_query

# ── Faturamento (base de tudo) ───────────────────────────────────────────────

_SQL_FATURAMENTO = """
SELECT
    TRIM(p.CODEMPRESA)   AS CODEMPRESA,
    TRIM(p.TIPOPEDIDO)   AS TIPOPEDIDO,
    TRIM(p.CODPEDIDO)    AS CODPEDIDO,
    TRIM(p.CODCLIENTE)   AS CODCLIENTE,
    TRIM(c.NOME)         AS NOME_CLIENTE,
    TRIM(p.CODVENDEDOR)  AS CODVENDEDOR,
    TRIM(v.NOME)         AS NOME_VENDEDOR,
    p.DATAFATURA,
    p.TOTALPEDIDO
FROM PEDIDOC p
LEFT JOIN CLIENTE c ON TRIM(c.CODCLIENTE)  = TRIM(p.CODCLIENTE)
LEFT JOIN VENDEND v ON TRIM(v.CODVENDEDOR) = TRIM(p.CODVENDEDOR)
WHERE TRIM(p.FATURADO) = 'S'
  AND p.DATAFATURA >= CAST(? AS TIMESTAMP)
ORDER BY p.DATAFATURA
"""

_SQL_FUNIL_PEDIDOS = """
SELECT
    TRIM(p.FATURADO)   AS STATUS,
    COUNT(*)           AS QTD,
    SUM(p.TOTALPEDIDO) AS VALOR
FROM PEDIDOC p
WHERE p.DATAPEDIDO >= CAST(? AS TIMESTAMP)
  AND p.DATAPEDIDO <  CAST(? AS TIMESTAMP)
GROUP BY 1
"""

# ── Itens do pedido (lucro bruto / top produtos / drill-down) ───────────────

_SQL_ITENS_PERIODO = """
-- Joins de PEDIDOC/PEDIDOI/PRODUTO usam comparação direta (sem TRIM nas chaves):
-- todas são CHAR de mesmo tamanho, então '=' já compara com padding e usa os
-- índices PEDIDOI_IDX_1/PK_PEDIDOI/PK_PRODUTO. Envolver em TRIM() derruba o uso
-- de índice e troca um seek indexado (~0.2s) por scan completo (~50-100s/mês).
-- COMPPROD é VARCHAR: aplicamos TRIM só do lado de PEDIDOI (probe), mantendo a
-- coluna indexada de COMPPROD "nua" para o otimizador poder usar o índice dela.
SELECT
    TRIM(p.CODCLIENTE)   AS CODCLIENTE,
    TRIM(p.CODVENDEDOR)  AS CODVENDEDOR,
    TRIM(i.CODPROD)      AS CODPROD,
    TRIM(pr.DESCRICAO)   AS PRODUTO,
    i.QUANTIDADE,
    i.TOTALRATEADO,
    COALESCE(i.DESCONTOVLR, 0) AS DESCONTO,
    COALESCE(cp.PRECOCUSTO, 0) AS PRECOCUSTO
FROM PEDIDOC p
JOIN PEDIDOI i  ON i.CODEMPRESA = p.CODEMPRESA
               AND i.TIPOPEDIDO = p.TIPOPEDIDO
               AND i.CODPEDIDO  = p.CODPEDIDO
               AND i.CODCLIENTE = p.CODCLIENTE
LEFT JOIN PRODUTO  pr ON pr.CODPROD = i.CODPROD
LEFT JOIN COMPPROD cp ON cp.CODPROD = TRIM(i.CODPROD)
                     AND cp.CODEMPRESA = TRIM(i.CODEMPRESA)
WHERE TRIM(p.FATURADO) = 'S'
  AND p.DATAFATURA >= CAST(? AS TIMESTAMP)
  AND p.DATAFATURA <  CAST(? AS TIMESTAMP)
"""

_SQL_ITENS_PEDIDO = """
SELECT
    TRIM(i.CODPROD)    AS CODPROD,
    TRIM(pr.DESCRICAO) AS PRODUTO,
    i.QUANTIDADE,
    i.PRECOUNIT,
    COALESCE(i.DESCONTOVLR, 0) AS DESCONTO,
    i.TOTALRATEADO     AS TOTAL
FROM PEDIDOI i
LEFT JOIN PRODUTO pr ON TRIM(pr.CODPROD) = TRIM(i.CODPROD)
WHERE TRIM(i.CODEMPRESA) = ?
  AND TRIM(i.TIPOPEDIDO)  = ?
  AND TRIM(i.CODPEDIDO)   = ?
  AND TRIM(i.CODCLIENTE)  = ?
ORDER BY i.SEQUENCIA
"""

# ── Clientes sem comprar / com queda de compras ─────────────────────────────

_SQL_ULTIMA_COMPRA = """
SELECT
    TRIM(p.CODCLIENTE) AS CODCLIENTE,
    TRIM(c.NOME)       AS NOME_CLIENTE,
    MIN(p.DATAFATURA)  AS PRIMEIRA_COMPRA,
    MAX(p.DATAFATURA)  AS ULTIMA_COMPRA,
    SUM(p.TOTALPEDIDO) AS TOTAL_HISTORICO
FROM PEDIDOC p
LEFT JOIN CLIENTE c ON TRIM(c.CODCLIENTE) = TRIM(p.CODCLIENTE)
WHERE TRIM(p.FATURADO) = 'S'
GROUP BY 1, 2
"""

_SQL_COMPRAS_MENSAIS = """
SELECT
    TRIM(p.CODCLIENTE) AS CODCLIENTE,
    TRIM(c.NOME)       AS NOME_CLIENTE,
    EXTRACT(YEAR  FROM p.DATAFATURA) AS ANO,
    EXTRACT(MONTH FROM p.DATAFATURA) AS MES,
    SUM(p.TOTALPEDIDO) AS TOTAL
FROM PEDIDOC p
LEFT JOIN CLIENTE c ON TRIM(c.CODCLIENTE) = TRIM(p.CODCLIENTE)
WHERE TRIM(p.FATURADO) = 'S'
  AND p.DATAFATURA >= CAST(? AS TIMESTAMP)
GROUP BY 1, 2, 3, 4
"""

_SQL_COMPRAS_30D = """
SELECT TRIM(p.CODCLIENTE) AS CODCLIENTE, SUM(p.TOTALPEDIDO) AS TOTAL_30D
FROM PEDIDOC p
WHERE TRIM(p.FATURADO) = 'S'
  AND p.DATAFATURA >= CAST(? AS TIMESTAMP)
GROUP BY 1
"""

# ── Sazonalidade ─────────────────────────────────────────────────────────────

_SQL_SAZONALIDADE = """
SELECT
    EXTRACT(YEAR  FROM p.DATAFATURA) AS ANO,
    EXTRACT(MONTH FROM p.DATAFATURA) AS MES,
    SUM(p.TOTALPEDIDO) AS FATURAMENTO,
    COUNT(*)           AS QTD_PEDIDOS
FROM PEDIDOC p
WHERE TRIM(p.FATURADO) = 'S'
  AND p.DATAFATURA >= CAST(? AS TIMESTAMP)
GROUP BY 1, 2
ORDER BY 1, 2
"""


# ── Funções de acesso (fetch) ─────────────────────────────────────────────────

def fetch_faturamento(data_ini_str: str) -> pd.DataFrame:
    """Pedidos faturados (PEDIDOC.FATURADO='S') a partir de `data_ini_str`."""
    try:
        return fb_query(_SQL_FATURAMENTO, (data_ini_str,))
    except Exception:
        return pd.DataFrame()


def fetch_meta_mes(mes_ano: str) -> pd.DataFrame:
    """Meta de faturamento do ERP (METAFATURAMENTOMENSAL) para o mês `mes_ano` (formato "MM/AAAA")."""
    # MESANO é VARCHAR(7) (ex.: "06/2026") — sem padding, então comparar
    # direto (sem TRIM na coluna) permite usar índice em MESANO, se existir.
    try:
        return fb_query(
            "SELECT SUM(VALORFATURAMENTO) AS META FROM METAFATURAMENTOMENSAL WHERE MESANO = ?",
            (mes_ano,),
        )
    except Exception:
        return pd.DataFrame()


def fetch_funil_pedidos(ini_str: str, fim_str: str) -> pd.DataFrame:
    """Pedidos criados entre `ini_str` e `fim_str`, agrupados por status de faturamento (S/N/X)."""
    try:
        return fb_query(_SQL_FUNIL_PEDIDOS, (ini_str, fim_str))
    except Exception:
        return pd.DataFrame()


def fetch_itens_periodo(ini_str: str, fim_str: str) -> pd.DataFrame:
    """Itens de pedidos faturados entre `ini_str` e `fim_str`, com custo atual do produto (para lucro bruto)."""
    try:
        return fb_query(_SQL_ITENS_PERIODO, (ini_str, fim_str))
    except Exception:
        return pd.DataFrame()


def fetch_itens_pedido(codempresa: str, tipopedido: str, codpedido: str, codcliente: str) -> pd.DataFrame:
    """Itens de um pedido específico (drill-down Cliente → Pedido → Itens)."""
    try:
        return fb_query(_SQL_ITENS_PEDIDO, (
            codempresa.strip(), tipopedido.strip(), codpedido.strip(), codcliente.strip(),
        ))
    except Exception:
        return pd.DataFrame()


def fetch_ultima_compra_clientes() -> pd.DataFrame:
    """Primeira e última compra de cada cliente, em toda a base histórica (sem filtro de período)."""
    try:
        return fb_query(_SQL_ULTIMA_COMPRA)
    except Exception:
        return pd.DataFrame()


def fetch_compras_mensais(data_ini_str: str) -> pd.DataFrame:
    """Total comprado por cliente, agrupado por ano/mês, a partir de `data_ini_str`."""
    try:
        return fb_query(_SQL_COMPRAS_MENSAIS, (data_ini_str,))
    except Exception:
        return pd.DataFrame()


def fetch_compras_30d(data_corte_str: str) -> pd.DataFrame:
    """Total comprado por cliente desde `data_corte_str` (usado para detectar queda de compras nos últimos 30 dias)."""
    try:
        return fb_query(_SQL_COMPRAS_30D, (data_corte_str,))
    except Exception:
        return pd.DataFrame()


def fetch_sazonalidade(data_ini_str: str) -> pd.DataFrame:
    """Faturamento e quantidade de pedidos por ano/mês, a partir de `data_ini_str` (série de sazonalidade)."""
    try:
        return fb_query(_SQL_SAZONALIDADE, (data_ini_str,))
    except Exception:
        return pd.DataFrame()


# ── Forma de pagamento — base para rateio proporcional por pedido ────────────
# PEDIDOC não tem forma de pagamento. O dado real está em MOVIREC, ligado ao
# título (DOCUREC) via (CODEMPRESA,TIPODOCTO,CODDOCTO,CODCLIENTE) — e o título
# liga ao pedido via DOCUREC.NUMDOCORIG, decodificado em Python (ver
# core/domain/comercial.py::get_faturamento_por_forma_pgto e
# core/domain/financeiro.py::numdocorig_to_numnf/get_itens_av, que já
# resolvem esse mesmo encoding para o drill-down de itens).
# TIPOMOV='01' = liquidação real (recebimento) — os demais tipos (02/04/05/06/
# 07/08) são movimentos derivados (ex.: compensação de cheque) e contariam o
# mesmo valor em dobro se incluídos.
_SQL_LIQUIDACOES_NF_AV = """
SELECT
    TRIM(d.CODEMPRESA)   AS CODEMPRESA,
    TRIM(d.TIPODOCTO)    AS TIPODOCTO,
    TRIM(d.NUMDOCORIG)   AS NUMDOCORIG,
    TRIM(mr.CODFORMAPGTO) AS CODFORMAPGTO,
    SUM(mr.VALORMOV)     AS VALOR_LIQUIDADO
FROM DOCUREC d
JOIN MOVIREC mr ON TRIM(mr.CODEMPRESA)  = TRIM(d.CODEMPRESA)
               AND TRIM(mr.TIPODOCTO)   = TRIM(d.TIPODOCTO)
               AND TRIM(mr.CODDOCTO)    = TRIM(d.CODDOCTO)
               AND TRIM(mr.CODCLIENTE)  = TRIM(d.CODCLIENTE)
WHERE TRIM(d.TIPODOCTO) IN ('NF', 'AV')
  AND TRIM(mr.TIPOMOV) = '01'
  AND (mr.ESTORNADO IS NULL OR mr.ESTORNADO <> 'S')
GROUP BY 1, 2, 3, 4
"""

_SQL_NF_PEDIDO_MAP = """
SELECT TRIM(CODEMPRESA) AS CODEMPRESA, NUMNF,
       TRIM(CODPEDIDO) AS CODPEDIDO, TRIM(TIPOPEDIDO) AS TIPOPEDIDO
FROM NFSAIDC
"""


def fetch_liquidacoes_nf_av() -> pd.DataFrame:
    """Liquidações reais (TIPOMOV='01') de todos os títulos NF/AV — base do rateio de forma de pagamento por pedido."""
    try:
        return fb_query(_SQL_LIQUIDACOES_NF_AV)
    except Exception:
        return pd.DataFrame()


def fetch_nf_pedido_map() -> pd.DataFrame:
    """Mapa NUMNF → (CODPEDIDO, TIPOPEDIDO) de toda a base (NFSAIDC) — usado para decodificar títulos do tipo NF."""
    try:
        return fb_query(_SQL_NF_PEDIDO_MAP)
    except Exception:
        return pd.DataFrame()
