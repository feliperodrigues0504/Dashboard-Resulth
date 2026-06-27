"""
core/domain/spotlight.py — Perfil consolidado de um cliente ou fornecedor,
cruzando Financeiro/Comercial/Compras em um único lugar. Base da busca
global ("Spotlight") no home: o usuário digita um nome e vê de uma vez só
o que hoje só aparecia espalhado em 3 módulos diferentes.
"""
from __future__ import annotations
import pandas as pd


def perfil_cliente(codcliente: str, nome: str) -> dict:
    """
    Perfil consolidado do cliente: saldo em aberto/vencido (Financeiro),
    última compra e sinais de inatividade/queda (Comercial).
    """
    perfil = {
        "codcliente": codcliente, "nome": nome,
        "total_aberto": 0.0, "total_vencido": 0.0, "titulos_vencidos": 0,
        "dias_atraso_max": 0, "ultima_compra": None, "dias_sem_comprar": None,
        "total_historico": 0.0, "situacao": [],
    }

    try:
        from core.domain.financeiro import get_contas_receber
        df_ar = get_contas_receber()
        if not df_ar.empty:
            do_cliente = df_ar[df_ar["CODCLIENTE"] == codcliente]
            perfil["total_aberto"] = float(do_cliente["SALDO_ABERTO"].sum())
            vencidos = do_cliente[do_cliente["DIAS_ATRASO"] > 0]
            perfil["total_vencido"] = float(vencidos["SALDO_ABERTO"].sum())
            perfil["titulos_vencidos"] = len(vencidos)
            if not vencidos.empty:
                perfil["dias_atraso_max"] = int(vencidos["DIAS_ATRASO"].max())
    except Exception:
        pass

    try:
        from core.domain.comercial import (
            get_ultima_compra_clientes, get_clientes_sem_comprar, get_clientes_queda_compras,
        )
        df_ult = get_ultima_compra_clientes()
        if not df_ult.empty:
            row = df_ult[df_ult["CODCLIENTE"] == codcliente]
            if not row.empty:
                perfil["ultima_compra"] = row.iloc[0]["ULTIMA_COMPRA"]
                perfil["dias_sem_comprar"] = int(row.iloc[0]["DIAS_SEM_COMPRAR"])
                perfil["total_historico"] = float(row.iloc[0]["TOTAL_HISTORICO"])

        sem = get_clientes_sem_comprar(df_ult, 60)
        if not sem.empty and codcliente in sem["CODCLIENTE"].values:
            perfil["situacao"].append("Sem comprar há mais de 60 dias")

        queda = get_clientes_queda_compras(meses_base=6, top_n=10_000)
        if not queda.empty and codcliente in queda["CODCLIENTE"].values:
            perfil["situacao"].append("Em queda de compras nos últimos 30 dias")
    except Exception:
        pass

    return perfil


def perfil_fornecedor(codfornec: str, nome: str) -> dict:
    """
    Perfil consolidado do fornecedor: compras e participação nos últimos 12
    meses (Compras), e estoque parado atribuído a ele (Estoque/Compras).
    """
    perfil = {
        "codfornec": codfornec, "nome": nome,
        "total_comprado_12m": 0.0, "qtd_nf_12m": 0, "participacao_pct": 0.0,
        "estoque_parado_valor": 0.0, "estoque_parado_skus": 0,
    }

    try:
        from core.domain.compras import get_compras_por_fornecedor, get_estoque_parado_por_fornecedor
        hoje = pd.Timestamp.now()
        ini_12m = (hoje - pd.DateOffset(months=12)).strftime("%Y-%m-%d")
        fim = (hoje + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        df_forn = get_compras_por_fornecedor(ini_12m, fim)
        if not df_forn.empty:
            row = df_forn[df_forn["CODFORNEC"] == codfornec]
            if not row.empty:
                r = row.iloc[0]
                perfil["total_comprado_12m"] = float(r["TOTAL_COMPRADO"])
                perfil["qtd_nf_12m"] = int(r["QTD_NF"])
                perfil["participacao_pct"] = float(r["PARTICIPACAO"])

        df_ep = get_estoque_parado_por_fornecedor(90)
        if not df_ep.empty and "FORNECEDOR" in df_ep.columns:
            row = df_ep[df_ep["FORNECEDOR"].str.strip().str.upper() == nome.strip().upper()]
            if not row.empty:
                perfil["estoque_parado_valor"] = float(row.iloc[0]["VALOR_CUSTO"])
                perfil["estoque_parado_skus"] = int(row.iloc[0]["SKUS"])
    except Exception:
        pass

    return perfil
