"""
core/sync/snapshot.py — Snapshots diários para séries históricas.
Salva no DuckDB o estado do dia atual (idempotente — ignora se já gravado).
Chamado pelo agendador em core/sync/agendador.py (diariamente às 08:00).
"""
from __future__ import annotations
from datetime import date
import pandas as pd
from core.data.firebird import fb_query
from core.data.duckdb_store import duck_execute, duck_executemany, duck_query, init_store


# ══════════════════════════════════════════════════════════════════
#  INADIMPLÊNCIA (AR vencido por faixa)
# ══════════════════════════════════════════════════════════════════
_SQL_INADIMP = """
SELECT
    SUM(CASE WHEN (VALORDOCTO - COALESCE(VALORPAGO,0)) > 0
             THEN (VALORDOCTO - COALESCE(VALORPAGO,0)) ELSE 0 END) AS TOTAL_VENCIDO,
    COUNT(*) AS QTD_TITULOS,
    SUM(CASE WHEN (CAST('NOW' AS TIMESTAMP) - DT_VENCIMENTO) BETWEEN 1  AND 30
             THEN (VALORDOCTO - COALESCE(VALORPAGO,0)) ELSE 0 END) AS F_1_30,
    SUM(CASE WHEN (CAST('NOW' AS TIMESTAMP) - DT_VENCIMENTO) BETWEEN 31 AND 60
             THEN (VALORDOCTO - COALESCE(VALORPAGO,0)) ELSE 0 END) AS F_31_60,
    SUM(CASE WHEN (CAST('NOW' AS TIMESTAMP) - DT_VENCIMENTO) BETWEEN 61 AND 90
             THEN (VALORDOCTO - COALESCE(VALORPAGO,0)) ELSE 0 END) AS F_61_90,
    SUM(CASE WHEN (CAST('NOW' AS TIMESTAMP) - DT_VENCIMENTO) > 90
             THEN (VALORDOCTO - COALESCE(VALORPAGO,0)) ELSE 0 END) AS F_90_MAIS
FROM DOCUREC
WHERE SITUACAO = '1'
  AND DT_VENCIMENTO < CAST('NOW' AS TIMESTAMP)
"""


def gravar_snapshot_inadimplencia():
    """Grava snapshot de inadimplência de hoje (idempotente)."""
    hoje = date.today()
    if _ja_existe("snap_inadimplencia", hoje):
        return

    try:
        df = fb_query(_SQL_INADIMP)
    except Exception as e:
        print(f"[snapshot_inadimplencia] erro ao consultar Firebird: {e}")
        return
    if df.empty:
        return
    r = df.iloc[0]
    try:
        duck_execute("""
            INSERT INTO snap_inadimplencia
                (data, valor_vencido, qtd_titulos,
                 faixa_1_30, faixa_31_60, faixa_61_90, faixa_90_mais)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            str(hoje),
            float(r["TOTAL_VENCIDO"] or 0),
            int(r["QTD_TITULOS"]    or 0),
            float(r["F_1_30"]       or 0),
            float(r["F_31_60"]      or 0),
            float(r["F_61_90"]      or 0),
            float(r["F_90_MAIS"]    or 0),
        ])
    except Exception as e:
        print(f"[snapshot_inadimplencia] erro ao gravar no DuckDB: {e}")


# ══════════════════════════════════════════════════════════════════
#  SALDO BANCÁRIO
# ══════════════════════════════════════════════════════════════════
def gravar_snapshot_saldo_bancario():
    """Grava saldo bancário total de hoje (idempotente).
    Reutiliza get_saldo_bancario() do financeiro (deduplica em Python).
    """
    hoje = date.today()
    try:
        existe = duck_query(
            "SELECT COUNT(*) AS n FROM snap_saldo_bancario WHERE data = ?",
            [str(hoje)]
        )
    except Exception as e:
        print(f"[snapshot_saldo_bancario] erro ao checar idempotência: {e}")
        return
    if not existe.empty and int(existe.iloc[0]["n"]) > 0:
        return

    from core.domain.financeiro import get_saldo_bancario
    df = get_saldo_bancario()
    if df.empty:
        return

    # 1 conexão para todas as contas (id_conta = índice sequencial), em vez
    # de abrir/fechar uma conexão por linha dentro do loop.
    linhas = [
        [str(hoje), i, float(row["SALDO"] or 0)]
        for i, (_, row) in enumerate(df.iterrows())
    ]
    try:
        duck_executemany(
            "INSERT INTO snap_saldo_bancario (data, id_conta, saldo) VALUES (?, ?, ?)",
            linhas,
        )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
#  KPIs DIÁRIOS (AR / AP / Caixa / Estoque / Faturamento mês)
# ══════════════════════════════════════════════════════════════════
def gravar_snapshot_kpis():
    """Grava KPIs executivos do dia (idempotente)."""
    hoje = date.today()
    if _ja_existe("snap_kpis_diario", hoje):
        return

    try:
        from core.domain.financeiro import (
            get_contas_receber, get_contas_pagar,
            get_saldo_bancario, get_estoque_custo, get_kpis,
        )
        from core.domain.comercial import get_faturamento

        df_ar   = get_contas_receber()
        df_ap   = get_contas_pagar()
        df_bco  = get_saldo_bancario()
        estoque = get_estoque_custo()
        kpis    = get_kpis(df_ar, df_ap, estoque, df_bco)

        # Faturamento do mês corrente
        df_fat = get_faturamento(meses_historico=1)
        fat_mes = 0.0
        if not df_fat.empty:
            df_fat["DATAFATURA"] = pd.to_datetime(df_fat["DATAFATURA"], errors="coerce")
            ini_mes = pd.Timestamp(hoje.year, hoje.month, 1)
            fat_mes = float(df_fat[df_fat["DATAFATURA"] >= ini_mes]["TOTALPEDIDO"].sum())

        duck_execute("""
            INSERT INTO snap_kpis_diario
                (data, total_ar, vencido_ar, total_ap, vencido_ap,
                 saldo_bco, capital_op, estoque_custo, fat_mes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            str(hoje),
            float(kpis.get("total_ar",     0)),
            float(kpis.get("vencido_ar",   0)),
            float(kpis.get("total_ap",     0)),
            float(kpis.get("vencido_ap",   0)),
            float(kpis.get("saldo_bco",    0)),
            float(kpis.get("capital_op",   0)),
            float(kpis.get("estoque_custo",0)),
            fat_mes,
        ])
    except Exception as e:
        print(f"[snapshot_kpis] erro: {e}")


# ══════════════════════════════════════════════════════════════════
#  LEITURAS HISTÓRICAS
# ══════════════════════════════════════════════════════════════════
def get_evolucao_inadimplencia() -> pd.DataFrame:
    """Lê do DuckDB o histórico diário de inadimplência (snap_inadimplencia), ordenado por data."""
    try:
        return duck_query(
            "SELECT * FROM snap_inadimplencia ORDER BY data"
        )
    except Exception as e:
        print(f"[get_evolucao_inadimplencia] erro: {e}")
        return pd.DataFrame()


# Alias para compatibilidade com código anterior
get_evolucao_snapshot = get_evolucao_inadimplencia


def get_evolucao_saldo_bancario() -> pd.DataFrame:
    """Lê do DuckDB o histórico diário de saldo bancário total (soma de todas as contas por dia)."""
    try:
        return duck_query("""
            SELECT data, SUM(saldo) AS saldo_total
            FROM snap_saldo_bancario
            GROUP BY data ORDER BY data
        """)
    except Exception as e:
        print(f"[get_evolucao_saldo_bancario] erro: {e}")
        return pd.DataFrame()


def get_evolucao_kpis() -> pd.DataFrame:
    """Lê do DuckDB o histórico diário de KPIs executivos (snap_kpis_diario), ordenado por data."""
    try:
        return duck_query(
            "SELECT * FROM snap_kpis_diario ORDER BY data"
        )
    except Exception as e:
        print(f"[get_evolucao_kpis] erro: {e}")
        return pd.DataFrame()


def get_comparativo_diario(kpis_atual: dict, fat_mes_atual: float) -> dict | None:
    """
    Compara os KPIs de AGORA (passados pelo chamador, já calculados ao vivo)
    com o snapshot diário mais recente anterior a hoje (snap_kpis_diario) —
    base do card "O que mudou desde ontem" do home.

    Usa o snapshot mais recente < hoje (não necessariamente "ontem" literal)
    para não quebrar em fins de semana/feriados sem coleta. Retorna None se
    ainda não há nenhum snapshot anterior a hoje (app recém-instalado).
    """
    try:
        r = duck_query(
            "SELECT * FROM snap_kpis_diario WHERE data < ? ORDER BY data DESC LIMIT 1",
            [str(date.today())],
        )
    except Exception as e:
        print(f"[get_comparativo_diario] erro: {e}")
        return None
    if r.empty:
        return None

    ref = r.iloc[0]
    data_ref = pd.Timestamp(ref["data"]).date()
    return {
        "data_referencia": data_ref,
        "dias_atras": (date.today() - data_ref).days,
        "delta_saldo_bco":  float(kpis_atual.get("saldo_bco", 0))    - float(ref["saldo_bco"]),
        "delta_vencido_ar": float(kpis_atual.get("vencido_ar", 0))   - float(ref["vencido_ar"]),
        "delta_capital_op": float(kpis_atual.get("capital_op", 0))   - float(ref["capital_op"]),
        "delta_fat_mes":    float(fat_mes_atual)                    - float(ref["fat_mes"]),
    }


def status_snapshot() -> dict:
    """
    Verifica a saúde do snapshot diário (agendado para 08:00 — ver
    core/sync/agendador.py): compara a data do snapshot mais recente em
    snap_kpis_diario com hoje. O job grava o snapshot do dia só depois das
    08:00, então 1 dia de atraso é esperado (ainda não rodou hoje) — só
    classificamos como "atrasado" a partir de 2+ dias sem coleta, ou se
    nunca houve nenhum snapshot.

    Retorna {'ultima_data': date|None, 'dias_atraso': int|None, 'atrasado': bool}.
    """
    try:
        r = duck_query("SELECT MAX(data) AS ultima FROM snap_kpis_diario")
    except Exception as e:
        print(f"[status_snapshot] erro: {e}")
        return {"ultima_data": None, "dias_atraso": None, "atrasado": True}

    if r.empty or pd.isna(r.iloc[0]["ultima"]):
        return {"ultima_data": None, "dias_atraso": None, "atrasado": True}

    ultima_data = pd.Timestamp(r.iloc[0]["ultima"]).date()
    dias_atraso = (date.today() - ultima_data).days
    return {
        "ultima_data": ultima_data,
        "dias_atraso": dias_atraso,
        "atrasado": dias_atraso >= 2,
    }


# ══════════════════════════════════════════════════════════════════
#  ORQUESTRADOR
# ══════════════════════════════════════════════════════════════════
def gravar_todos():
    """Grava todos os snapshots de hoje (chamado pelo agendador)."""
    init_store()
    try:
        gravar_snapshot_inadimplencia()
    except Exception as e:
        print(f"[snapshot] inadimplência: {e}")
    try:
        gravar_snapshot_saldo_bancario()
    except Exception as e:
        print(f"[snapshot] saldo_bancario: {e}")
    try:
        gravar_snapshot_kpis()
    except Exception as e:
        print(f"[snapshot] kpis_diario: {e}")


# ── Helper ────────────────────────────────────────────────────────
def _ja_existe(tabela: str, hoje: date) -> bool:
    """Verifica se já existe snapshot de `hoje` em `tabela` (idempotência — `tabela` é sempre um literal interno, nunca entrada do usuário)."""
    try:
        r = duck_query(
            f"SELECT COUNT(*) AS n FROM {tabela} WHERE data = ?",
            [str(hoje)]
        )
        return not r.empty and int(r.iloc[0]["n"]) > 0
    except Exception:
        return False


if __name__ == "__main__":
    gravar_todos()
    print("Todos os snapshots concluídos.")
