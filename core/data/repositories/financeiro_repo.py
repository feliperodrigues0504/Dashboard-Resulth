"""
Camada de acesso a dados do módulo financeiro.
Só consulta o Firebird (read-only) e devolve DataFrames com tipos coagidos —
nenhuma regra de negócio (faixa de atraso, KPI, alerta) vive aqui. Isso está
em core/domain/financeiro.py, que consome estas funções.
"""
import pandas as pd
from core.data.firebird import fb_query

# ── Contas a Receber ──────────────────────────────────────────────────────────

_SQL_AR = """
SELECT
    TRIM(d.CODCLIENTE)                          AS CODCLIENTE,
    TRIM(d.CODVENDEDOR)                         AS CODVENDEDOR,
    TRIM(d.CODDOCTO)                            AS CODDOCTO,
    TRIM(d.TIPODOCTO)                           AS TIPODOCTO,
    TRIM(d.NUMDOCORIG)                          AS NUMDOCORIG,
    d.DT_VENCIMENTO,
    d.VALORDOCTO,
    COALESCE(d.VALORPAGO, 0)                    AS VALORPAGO,
    (d.VALORDOCTO - COALESCE(d.VALORPAGO, 0))   AS SALDO_ABERTO,
    TRIM(c.NOME)                                AS NOME_CLIENTE,
    TRIM(d.CODEMPRESA)                          AS CODEMPRESA
FROM DOCUREC d
LEFT JOIN CLIENTE c ON TRIM(c.CODCLIENTE) = TRIM(d.CODCLIENTE)
WHERE d.SITUACAO = '1'
ORDER BY d.DT_VENCIMENTO
"""

# ── Contas a Pagar ────────────────────────────────────────────────────────────

_SQL_AP = """
SELECT
    TRIM(d.CODFORNEC)                           AS CODFORNEC,
    TRIM(d.CODDOCTO)                            AS CODDOCTO,
    TRIM(d.TIPODOCTO)                           AS TIPODOCTO,
    d.DT_VENCIMENTO,
    d.VALORDOCTO,
    COALESCE(d.VALORPAGO, 0)                    AS VALORPAGO,
    (d.VALORDOCTO - COALESCE(d.VALORPAGO, 0))   AS SALDO_ABERTO,
    TRIM(f.NOME)                                AS NOME_FORNECEDOR,
    TRIM(d.CODEMPRESA)                          AS CODEMPRESA
FROM DOCUPAG d
LEFT JOIN FORNECE f ON TRIM(f.CODFORNEC) = TRIM(d.CODFORNEC)
WHERE d.SITUACAO = '1'
ORDER BY d.DT_VENCIMENTO
"""

# ── Estoque ao custo ──────────────────────────────────────────────────────────

_SQL_ESTOQUE = """
SELECT
    SUM(COALESCE(c.ESTOQUE, 0) * COALESCE(c.PRECOCUSTO, 0)) AS ESTOQUE_CUSTO,
    SUM(COALESCE(c.ESTOQUE, 0) * COALESCE(p.PRECO,      0)) AS ESTOQUE_VENDA
FROM COMPPROD c
JOIN PRODUTO p ON TRIM(p.CODPROD) = TRIM(c.CODPROD)
WHERE COALESCE(c.ESTOQUE, 0) > 0
  AND TRIM(c.CODEMPRESA) = '00'
"""

# ── Saldo bancário (último saldo por conta via MOVIBAN) ───────────────────────
# Busca os movimentos mais recentes ordenados desc e deduplica em Python para
# pegar o último saldo por conta (Firebird Dialect 1 não tem window function
# para "último por grupo" em uma única query). Testado NOT EXISTS/correlated
# subquery como alternativa a "buscar tudo": sem índice em
# (CODBANCO,CONTA,DATAMOV,NUMORD) — que não podemos criar, o banco é R/O — o
# NOT EXISTS é O(n²) e ficou mais lento que isto na prática (0.195s vs 0.085s
# com 600 linhas). A defesa real contra o crescimento da tabela é o `FIRST N`:
# como há só 1-2 contas bancárias ativas, a linha mais recente de cada conta
# está garantidamente dentro das primeiras ~centenas de registros mais
# recentes do sistema inteiro — nunca precisa varrer o histórico completo.
_SQL_SALDO_BCO = """
SELECT FIRST 2000
    TRIM(m.CODBANCO) AS CODBANCO,
    TRIM(m.CONTA)    AS CONTA,
    m.VLRSALDO       AS SALDO,
    m.DATAMOV        AS DATA_MOV
FROM MOVIBAN m
WHERE (m.ESTORNADO IS NULL OR m.ESTORNADO <> 'S')
ORDER BY m.DATAMOV DESC, m.NUMORD DESC
"""

# ── Evolução do saldo (SALDOST) ───────────────────────────────────────────────

_SQL_EVOLUCAO_SALDO = """
SELECT DATASALDO, SALDO
FROM   SALDOST
WHERE  TRIM(CODEMPRESA) = '01'
ORDER  BY DATASALDO DESC
"""

# ── Comparativos históricos (via MOVIREC liquidações) ────────────────────────

# MOVIREC: liquidações reais de caixa.
# TM='01' para NF é lançamento de emissão (billing), não cash — excluído.
# TM='07' é estorno — excluído. Tudo mais (AV/CO/55 TM='01', NF TM='02'/'04') é caixa.
_SQL_RECEBIMENTOS_MES = """
SELECT
    EXTRACT(YEAR  FROM r.DT_MOVIMENTO) AS ANO,
    EXTRACT(MONTH FROM r.DT_MOVIMENTO) AS MES,
    SUM(r.VALORMOV) AS RECEBIDO
FROM MOVIREC r
WHERE (r.ESTORNADO IS NULL OR r.ESTORNADO <> 'S')
  AND NOT (TRIM(r.TIPOMOV) = '01' AND TRIM(r.TIPODOCTO) = 'NF')
  AND TRIM(r.TIPOMOV) <> '07'
  AND r.DT_MOVIMENTO >= CAST(? AS TIMESTAMP)
GROUP BY 1, 2
ORDER BY 1, 2
"""

# MOVIPAG: TIPOMOV é CHAR(1)='1' (coluna de 1 byte neste ERP).
# Sem filtro de TIPOMOV — todos os registros são liquidações; apenas exclui estornos.
_SQL_PAGAMENTOS_MES = """
SELECT
    EXTRACT(YEAR  FROM p.DT_MOVIMENTO) AS ANO,
    EXTRACT(MONTH FROM p.DT_MOVIMENTO) AS MES,
    SUM(p.VALORMOV) AS PAGO
FROM MOVIPAG p
WHERE (p.ESTORNADO IS NULL OR p.ESTORNADO <> 'S')
  AND p.DT_MOVIMENTO >= CAST(? AS TIMESTAMP)
GROUP BY 1, 2
ORDER BY 1, 2
"""

_SQL_INADIMPLENCIA_MES = """
SELECT
    EXTRACT(YEAR  FROM d.DT_VENCIMENTO) AS ANO,
    EXTRACT(MONTH FROM d.DT_VENCIMENTO) AS MES,
    SUM(d.VALORDOCTO - COALESCE(d.VALORPAGO,0)) AS VENCIDO
FROM DOCUREC d
WHERE d.SITUACAO = '1'
  AND d.DT_VENCIMENTO < CAST(? AS TIMESTAMP)
GROUP BY 1, 2
ORDER BY 1, 2
"""

_SQL_SOMA_RECEBIMENTOS_PERIODO = """
    SELECT SUM(r.VALORMOV) AS TOTAL
    FROM MOVIREC r
    WHERE (r.ESTORNADO IS NULL OR r.ESTORNADO <> 'S')
      AND NOT (TRIM(r.TIPOMOV) = '01' AND TRIM(r.TIPODOCTO) = 'NF')
      AND TRIM(r.TIPOMOV) <> '07'
      AND r.DT_MOVIMENTO >= CAST(? AS TIMESTAMP)
      AND r.DT_MOVIMENTO <= CAST(? AS TIMESTAMP)
"""

_SQL_SOMA_PAGAMENTOS_PERIODO = """
    SELECT SUM(p.VALORMOV) AS TOTAL
    FROM MOVIPAG p
    WHERE (p.ESTORNADO IS NULL OR p.ESTORNADO <> 'S')
      AND p.DT_MOVIMENTO >= CAST(? AS TIMESTAMP)
      AND p.DT_MOVIMENTO <= CAST(? AS TIMESTAMP)
"""

# ── Drill-down: histórico de movimentações de um título ──────────────────────

_SQL_HIST_AR = """
SELECT
    TRIM(r.TIPOMOV)              AS TIPOMOV,
    r.DT_MOVIMENTO,
    r.VALORMOV,
    COALESCE(r.VALORDESC,   0)   AS VALORDESC,
    COALESCE(r.JUROSMULTA,  0)   AS JUROSMULTA,
    TRIM(r.CODFORMAPGTO)         AS FORMAPGTO,
    TRIM(r.USUARIO)              AS USUARIO
FROM MOVIREC r
WHERE TRIM(r.CODEMPRESA)  = ?
  AND TRIM(r.TIPODOCTO)   = ?
  AND TRIM(r.CODDOCTO)    = ?
  AND TRIM(r.CODCLIENTE)  = ?
  AND (r.ESTORNADO IS NULL OR r.ESTORNADO <> 'S')
ORDER BY r.DT_MOVIMENTO
"""

_SQL_HIST_AP = """
SELECT
    TRIM(p.TIPOMOV)              AS TIPOMOV,
    p.DT_MOVIMENTO,
    p.VALORMOV,
    COALESCE(p.VALORDESC,   0)   AS VALORDESC,
    COALESCE(p.JUROSMULTA,  0)   AS JUROSMULTA,
    TRIM(p.CODFORMAPGTO)         AS FORMAPGTO,
    TRIM(p.USUARIO)              AS USUARIO
FROM MOVIPAG p
WHERE TRIM(p.CODEMPRESA)  = ?
  AND TRIM(p.TIPODOCTO)   = ?
  AND TRIM(p.CODDOCTO)    = ?
  AND TRIM(p.CODFORNEC)   = ?
  AND (p.ESTORNADO IS NULL OR p.ESTORNADO <> 'S')
ORDER BY p.DT_MOVIMENTO
"""

# ── Drill-down: itens de NF associada ao título ───────────────────────────────

_SQL_ITENS_NF = """
SELECT FIRST 100
    TRIM(i.CODPROD)            AS CODPROD,
    TRIM(p.DESCRICAO)          AS PRODUTO,
    i.QUANTIDADE,
    i.PRECOUNIT                AS PRECO_UNIT,
    COALESCE(i.DESCONTOVLR, 0) AS DESCONTO,
    i.TOTALRATEADO             AS TOTAL
FROM NFSAIDI i
LEFT JOIN PRODUTO p ON TRIM(p.CODPROD) = TRIM(i.CODPROD)
WHERE TRIM(i.CODEMPRESA) = ?
  AND CAST(i.NUMNF AS INTEGER) = ?
ORDER BY i.CODPROD
"""

# ── Drill-down: itens de pedido AV vinculado ao título ───────────────────────

_SQL_ITENS_PEDIDO_AV = """
SELECT FIRST 200
    TRIM(i.CODPROD)            AS CODPROD,
    TRIM(p.DESCRICAO)          AS PRODUTO,
    i.QUANTIDADE,
    i.PRECOUNIT                AS PRECO_UNIT,
    COALESCE(i.DESCONTOVLR, 0) AS DESCONTO,
    i.TOTALRATEADO             AS TOTAL
FROM PEDIDOI i
LEFT JOIN PRODUTO p ON TRIM(p.CODPROD) = TRIM(i.CODPROD)
WHERE TRIM(i.CODEMPRESA) = ?
  AND TRIM(i.TIPOPEDIDO)  = ?
  AND TRIM(i.CODPEDIDO)   = ?
ORDER BY i.SEQUENCIA
"""

# ── PMR e PMP ─────────────────────────────────────────────────────────────────

# PMR: apenas NF com TM='04' (liquidação confirmada). AV/CO são à vista — não têm prazo.
# JOIN sem TRIM nas chaves: CODEMPRESA/TIPODOCTO/CODDOCTO/CODCLIENTE são CHAR
# de mesmo tamanho em DOCUREC e MOVIREC (confirmado via RDB$FIELDS) — TRIM()
# nas duas pontas do JOIN impede o otimizador de usar índice (mesmo problema
# já documentado em core/data/repositories/comercial_repo.py::_SQL_ITENS_PERIODO).
# Validado: mesmo resultado, ~2x mais rápido (0.073s -> 0.039s em 117 linhas/mês de teste).
_SQL_LIQUIDACOES_AR = """
SELECT d.DT_VENCIMENTO, r.DT_MOVIMENTO, r.VALORMOV
FROM   DOCUREC d
JOIN   MOVIREC r ON r.CODEMPRESA = d.CODEMPRESA
                AND r.TIPODOCTO  = d.TIPODOCTO
                AND r.CODDOCTO   = d.CODDOCTO
                AND r.CODCLIENTE = d.CODCLIENTE
WHERE  TRIM(d.TIPODOCTO) = 'NF'
  AND  TRIM(r.TIPOMOV) = '04'
  AND (r.ESTORNADO IS NULL OR r.ESTORNADO <> 'S')
  AND  r.DT_MOVIMENTO >= CAST(? AS TIMESTAMP)
"""

# PMP: MOVIPAG.TIPOMOV é CHAR(1)='1' neste ERP — sem filtro de TIPOMOV.
# Mesma otimização de JOIN sem TRIM (CODEMPRESA/TIPODOCTO/CODDOCTO/CODFORNEC
# são CHAR de mesmo tamanho em DOCUPAG e MOVIPAG).
_SQL_LIQUIDACOES_AP = """
SELECT d.DT_VENCIMENTO, p.DT_MOVIMENTO, p.VALORMOV
FROM   DOCUPAG d
JOIN   MOVIPAG p ON p.CODEMPRESA = d.CODEMPRESA
                AND p.TIPODOCTO  = d.TIPODOCTO
                AND p.CODDOCTO   = d.CODDOCTO
                AND p.CODFORNEC  = d.CODFORNEC
WHERE (p.ESTORNADO IS NULL OR p.ESTORNADO <> 'S')
  AND  p.DT_MOVIMENTO >= CAST(? AS TIMESTAMP)
"""


# ── Funções de acesso (fetch) ─────────────────────────────────────────────────

def fetch_contas_receber() -> pd.DataFrame:
    """Busca todos os títulos de Contas a Receber em aberto (DOCUREC), com DT_VENCIMENTO já como datetime."""
    try:
        df = fb_query(_SQL_AR)
    except Exception:
        return pd.DataFrame()
    if not df.empty:
        df['DT_VENCIMENTO'] = pd.to_datetime(df['DT_VENCIMENTO'])
    return df


def fetch_contas_pagar() -> pd.DataFrame:
    """Busca todos os títulos de Contas a Pagar em aberto (DOCUPAG), com DT_VENCIMENTO já como datetime."""
    try:
        df = fb_query(_SQL_AP)
    except Exception:
        return pd.DataFrame()
    if not df.empty:
        df['DT_VENCIMENTO'] = pd.to_datetime(df['DT_VENCIMENTO'])
    return df


def fetch_estoque_custo() -> dict:
    """Retorna o valor total do estoque da matriz (empresa '00') a custo e a preço de venda."""
    try:
        df = fb_query(_SQL_ESTOQUE)
    except Exception:
        return {'custo': 0.0, 'venda': 0.0}
    if df.empty:
        return {'custo': 0.0, 'venda': 0.0}
    return {
        'custo': float(df.iloc[0]['ESTOQUE_CUSTO'] or 0),
        'venda': float(df.iloc[0]['ESTOQUE_VENDA'] or 0),
    }


def fetch_saldo_bancario() -> pd.DataFrame:
    """Retorna o saldo mais recente de cada conta bancária (ver nota de performance acima sobre _SQL_SALDO_BCO)."""
    try:
        df = fb_query(_SQL_SALDO_BCO)
        # Mantém apenas o registro mais recente por conta (já ordenado DESC)
        return df.drop_duplicates(subset=['CODBANCO', 'CONTA'], keep='first')
    except Exception:
        return pd.DataFrame(columns=['CODBANCO', 'CONTA', 'SALDO', 'DATA_MOV'])


def fetch_evolucao_saldo() -> pd.DataFrame:
    """Histórico de saldo de estoque (SALDOST) da filial, ordenado por data."""
    try:
        df = fb_query(_SQL_EVOLUCAO_SALDO)
        df['DATASALDO'] = pd.to_datetime(df['DATASALDO'])
        return df.sort_values('DATASALDO')
    except Exception:
        return pd.DataFrame(columns=['DATASALDO', 'SALDO'])


def fetch_recebimentos_mes(data_ini_str: str) -> pd.DataFrame:
    """Recebimentos liquidados (MOVIREC), agrupados por ano/mês, a partir de `data_ini_str`."""
    try:
        return fb_query(_SQL_RECEBIMENTOS_MES, (data_ini_str,))
    except Exception:
        return pd.DataFrame()


def fetch_pagamentos_mes(data_ini_str: str) -> pd.DataFrame:
    """Pagamentos liquidados (MOVIPAG), agrupados por ano/mês, a partir de `data_ini_str`."""
    try:
        return fb_query(_SQL_PAGAMENTOS_MES, (data_ini_str,))
    except Exception:
        return pd.DataFrame()


def fetch_inadimplencia_mes(data_ref_str: str) -> pd.DataFrame:
    """Saldo em aberto de DOCUREC vencido antes de `data_ref_str`, agrupado por ano/mês de vencimento."""
    try:
        return fb_query(_SQL_INADIMPLENCIA_MES, (data_ref_str,))
    except Exception:
        return pd.DataFrame()


def fetch_soma_recebimentos_periodo(data_ini_str: str, data_fim_str: str) -> pd.DataFrame:
    """Soma de recebimentos liquidados (MOVIREC) entre `data_ini_str` e `data_fim_str` (linha única, coluna TOTAL)."""
    try:
        return fb_query(_SQL_SOMA_RECEBIMENTOS_PERIODO, (data_ini_str, data_fim_str))
    except Exception:
        return pd.DataFrame()


def fetch_soma_pagamentos_periodo(data_ini_str: str, data_fim_str: str) -> pd.DataFrame:
    """Soma de pagamentos liquidados (MOVIPAG) entre `data_ini_str` e `data_fim_str` (linha única, coluna TOTAL)."""
    try:
        return fb_query(_SQL_SOMA_PAGAMENTOS_PERIODO, (data_ini_str, data_fim_str))
    except Exception:
        return pd.DataFrame()


def fetch_historico_ar(codempresa: str, tipodocto: str,
                        coddocto: str, codcliente: str) -> pd.DataFrame:
    """Histórico de movimentações (MOVIREC) de um título AR específico, com DT_MOVIMENTO já como datetime."""
    try:
        df = fb_query(_SQL_HIST_AR, (
            codempresa.strip(), tipodocto.strip(),
            coddocto.strip(), codcliente.strip(),
        ))
    except Exception:
        return pd.DataFrame()
    if not df.empty:
        df['DT_MOVIMENTO'] = pd.to_datetime(df['DT_MOVIMENTO'])
    return df


def fetch_historico_ap(codempresa: str, tipodocto: str,
                        coddocto: str, codfornec: str) -> pd.DataFrame:
    """Histórico de movimentações (MOVIPAG) de um título AP específico, com DT_MOVIMENTO já como datetime."""
    try:
        df = fb_query(_SQL_HIST_AP, (
            codempresa.strip(), tipodocto.strip(),
            coddocto.strip(), codfornec.strip(),
        ))
    except Exception:
        return pd.DataFrame()
    if not df.empty:
        df['DT_MOVIMENTO'] = pd.to_datetime(df['DT_MOVIMENTO'])
    return df


def fetch_itens_nf(codempresa: str, numnf: int) -> pd.DataFrame:
    """Itens de produto (NFSAIDI) de uma NF de saída, identificada pelo número inteiro `numnf`."""
    try:
        df = fb_query(_SQL_ITENS_NF, (codempresa.strip(), numnf))
        if not df.empty:
            df["QUANTIDADE"] = pd.to_numeric(df["QUANTIDADE"], errors="coerce")
            df["PRECO_UNIT"] = pd.to_numeric(df["PRECO_UNIT"], errors="coerce")
            df["TOTAL"]      = pd.to_numeric(df["TOTAL"],      errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


def fetch_itens_pedido_av(codempresa: str, tipopedido: str, codpedido: str) -> pd.DataFrame:
    """Itens de produto (PEDIDOI) de um pedido AV, identificado por tipo + código de pedido."""
    try:
        df = fb_query(_SQL_ITENS_PEDIDO_AV, (codempresa.strip(), tipopedido, codpedido))
        if not df.empty:
            for c in ("QUANTIDADE", "PRECO_UNIT", "DESCONTO", "TOTAL"):
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        return df
    except Exception:
        return pd.DataFrame()


def fetch_liquidacoes_ar(data_corte_str: str) -> pd.DataFrame:
    """Liquidações de NF (DOCUREC ⋈ MOVIREC, TIPOMOV='04') desde `data_corte_str` — base do cálculo de PMR."""
    try:
        return fb_query(_SQL_LIQUIDACOES_AR, (data_corte_str,))
    except Exception:
        return pd.DataFrame()


def fetch_liquidacoes_ap(data_corte_str: str) -> pd.DataFrame:
    """Liquidações de AP (DOCUPAG ⋈ MOVIPAG) desde `data_corte_str` — base do cálculo de PMP."""
    try:
        return fb_query(_SQL_LIQUIDACOES_AP, (data_corte_str,))
    except Exception:
        return pd.DataFrame()
