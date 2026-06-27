"""
core/dashboard/widgets_financeiro.py — widgets do Painel Personalizado
originados do módulo Financeiro. Cada `fetch` chama as MESMAS funções de
core/domain/financeiro.py já usadas por pages/01_Financeiro.py — nenhuma
lógica nova, só reuso + adaptação de formato (ver core/dashboard/adapters.py).
"""
from __future__ import annotations
from datetime import date
import pandas as pd

from core.dashboard import adapters as ad
from core.domain import financeiro as fin


def _base_financeiro():
    """Carrega AR/AP/saldo/estoque uma vez — todos os widgets financeiros derivam dela."""
    df_ar = fin.get_contas_receber()
    df_ap = fin.get_contas_pagar()
    df_bco = fin.get_saldo_bancario()
    estoque = fin.get_estoque_custo()
    kpis = fin.get_kpis(df_ar, df_ap, estoque, df_bco)
    return df_ar, df_ap, df_bco, kpis


def _fetch_kpi_financeiro(chave: str, formatador: str = "brl"):
    """Fábrica: widget de KPI simples lendo uma chave do dict get_kpis()."""
    def _fetch(data_ini: date, data_fim: date) -> dict:
        _, _, _, kpis = _base_financeiro()
        return ad.kpi(kpis.get(chave, 0), formatador)
    return _fetch


def _fetch_evolucao_saldo(data_ini: date, data_fim: date) -> dict:
    df = fin.get_evolucao_saldo()
    if df.empty:
        return ad.line_de_df(pd.DataFrame(), "DATASALDO", "SALDO")
    return ad.line_de_df(df.sort_values("DATASALDO").tail(30), "DATASALDO", "SALDO", "Saldo")


def _fetch_fluxo_projetado(data_ini: date, data_fim: date) -> dict:
    df_ar, df_ap, _, _ = _base_financeiro()
    df = fin.fluxo_projetado(df_ar, df_ap)
    return ad.bar_de_df(df, "Horizonte", "Líquido", "Líquido")


def _fetch_aging_ar_faixa(data_ini: date, data_fim: date) -> dict:
    df_ar, _, _, _ = _base_financeiro()
    serie = fin.aging_totais(df_ar)
    if serie.empty:
        return ad.pie_de_df(pd.DataFrame(), "FAIXA", "SALDO_ABERTO")
    df = serie.reset_index()
    df.columns = ["FAIXA", "SALDO_ABERTO"]
    return ad.pie_de_df(df, "FAIXA", "SALDO_ABERTO")


def _fetch_aging_ar_cliente(data_ini: date, data_fim: date) -> dict:
    df_ar, _, _, _ = _base_financeiro()
    df = fin.aging_por_cliente(df_ar)
    cols = ["NOME_CLIENTE", "TOTAL"] if "TOTAL" in df.columns else list(df.columns)[:3]
    return ad.tabela_de_df(df, cols)


def _fetch_ap_fornecedor(data_ini: date, data_fim: date) -> dict:
    _, df_ap, _, _ = _base_financeiro()
    df = fin.ap_por_fornecedor(df_ap)
    return ad.tabela_de_df(df, ["Fornecedor", "Total"])


def _fetch_comparativo_recebimentos(data_ini: date, data_fim: date) -> dict:
    df = fin.get_comparativo_recebimentos(13)
    return ad.bar_de_df(df, "MES_ANO", "RECEBIDO", "Recebido")


def _fetch_comparativo_pagamentos(data_ini: date, data_fim: date) -> dict:
    df = fin.get_comparativo_pagamentos(13)
    return ad.bar_de_df(df, "MES_ANO", "PAGO", "Pago")


def _fetch_evolucao_inadimplencia(data_ini: date, data_fim: date) -> dict:
    df = fin.get_evolucao_inadimplencia()
    return ad.bar_de_df(df, "MES_ANO", "VENCIDO", "Inadimplência")


def _fetch_acumulado_ano(data_ini: date, data_fim: date) -> dict:
    d = fin.get_acumulado_ano()
    if not d:
        return ad.bar_de_df(pd.DataFrame(), "x", "y")
    df = pd.DataFrame({
        "Categoria": [f"Recebido {d['ano']}", f"Recebido {d['ano_ant']}",
                      f"Pago {d['ano']}", f"Pago {d['ano_ant']}"],
        "Valor": [d["recebido_ano"], d["recebido_ano_ant"], d["pago_ano"], d["pago_ano_ant"]],
    })
    return ad.bar_de_df(df, "Categoria", "Valor", "Valor")


def _fetch_pmr_pmp(data_ini: date, data_fim: date) -> dict:
    d = fin.get_pmr_pmp()
    pmr = d.get("pmr") or 0
    pmp = d.get("pmp") or 0
    return ad.kpi(f"PMR {pmr:.0f}d / PMP {pmp:.0f}d", "raw")


def _fetch_concentracao_inadimplencia(data_ini: date, data_fim: date) -> dict:
    df_ar, _, _, _ = _base_financeiro()
    d = fin.get_concentracao_inadimplencia(df_ar)
    return ad.kpi(d.get("top3_perc", 0), "pct")


def _fetch_projecao_acumulada(data_ini: date, data_fim: date) -> dict:
    df_ar, df_ap, df_bco, _ = _base_financeiro()
    saldo_inicial = float(df_bco["SALDO"].sum()) if not df_bco.empty else 0.0
    df = fin.get_projecao_acumulada(df_ar, df_ap, saldo_inicial, dias=60)
    return ad.line_de_df(df, "Data", "Saldo", "Saldo projetado")


WIDGETS_FINANCEIRO = [
    {"id": "fin_saldo_bco", "nome": "Saldo Bancário", "origem": "Financeiro",
     "descricao": "Saldo bancário consolidado (MOVIBAN).", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_kpi_financeiro("saldo_bco")},
    {"id": "fin_total_ar", "nome": "Total a Receber", "origem": "Financeiro",
     "descricao": "Saldo total em aberto de Contas a Receber.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_kpi_financeiro("total_ar")},
    {"id": "fin_vencido_ar", "nome": "AR Vencido", "origem": "Financeiro",
     "descricao": "Saldo vencido de Contas a Receber.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_kpi_financeiro("vencido_ar")},
    {"id": "fin_total_ap", "nome": "Total a Pagar", "origem": "Financeiro",
     "descricao": "Saldo total em aberto de Contas a Pagar.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_kpi_financeiro("total_ap")},
    {"id": "fin_vencido_ap", "nome": "AP Vencido", "origem": "Financeiro",
     "descricao": "Saldo vencido de Contas a Pagar.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_kpi_financeiro("vencido_ap")},
    {"id": "fin_capital_op", "nome": "Capital Operacional", "origem": "Financeiro",
     "descricao": "Caixa + A Receber + Estoque − A Pagar.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_kpi_financeiro("capital_op")},
    {"id": "fin_evolucao_saldo", "nome": "Evolução do Saldo Bancário", "origem": "Financeiro",
     "descricao": "Saldo bancário diário (últimos 30 registros).", "tipo": "line", "w": 6, "h": 4,
     "fetch": _fetch_evolucao_saldo},
    {"id": "fin_fluxo_projetado", "nome": "Fluxo de Caixa Projetado", "origem": "Financeiro",
     "descricao": "Saldo líquido projetado por horizonte (7/15/30/60/90d).", "tipo": "bar", "w": 6, "h": 4,
     "fetch": _fetch_fluxo_projetado},
    {"id": "fin_aging_faixa", "nome": "Aging AR por Faixa", "origem": "Financeiro",
     "descricao": "Distribuição do AR vencido por faixa de atraso.", "tipo": "pie", "w": 6, "h": 4,
     "fetch": _fetch_aging_ar_faixa},
    {"id": "fin_aging_cliente", "nome": "Aging AR por Cliente", "origem": "Financeiro",
     "descricao": "Top clientes com saldo vencido.", "tipo": "tabela", "w": 6, "h": 4,
     "fetch": _fetch_aging_ar_cliente},
    {"id": "fin_ap_fornecedor", "nome": "AP por Fornecedor", "origem": "Financeiro",
     "descricao": "Saldo em aberto de Contas a Pagar por fornecedor.", "tipo": "tabela", "w": 6, "h": 4,
     "fetch": _fetch_ap_fornecedor},
    {"id": "fin_comp_recebimentos", "nome": "Comparativo de Recebimentos", "origem": "Financeiro",
     "descricao": "Recebimentos liquidados por mês (13 meses).", "tipo": "bar", "w": 6, "h": 4,
     "fetch": _fetch_comparativo_recebimentos},
    {"id": "fin_comp_pagamentos", "nome": "Comparativo de Pagamentos", "origem": "Financeiro",
     "descricao": "Pagamentos liquidados por mês (13 meses).", "tipo": "bar", "w": 6, "h": 4,
     "fetch": _fetch_comparativo_pagamentos},
    {"id": "fin_evolucao_inadimplencia", "nome": "Evolução da Inadimplência", "origem": "Financeiro",
     "descricao": "Inadimplência acumulada por mês de vencimento.", "tipo": "bar", "w": 6, "h": 4,
     "fetch": _fetch_evolucao_inadimplencia},
    {"id": "fin_acumulado_ano", "nome": "Acumulado do Ano", "origem": "Financeiro",
     "descricao": "Recebido/Pago no ano vs ano anterior.", "tipo": "bar", "w": 6, "h": 4,
     "fetch": _fetch_acumulado_ano},
    {"id": "fin_pmr_pmp", "nome": "PMR / PMP", "origem": "Financeiro",
     "descricao": "Prazo médio de recebimento e pagamento.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_pmr_pmp},
    {"id": "fin_concentracao_inadimplencia", "nome": "Concentração de Inadimplência", "origem": "Financeiro",
     "descricao": "% do AR vencido concentrado nos top 3 clientes.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_concentracao_inadimplencia},
    {"id": "fin_projecao_acumulada", "nome": "Projeção de Caixa Acumulada", "origem": "Financeiro",
     "descricao": "Saldo de caixa projetado dia a dia (60 dias).", "tipo": "line", "w": 6, "h": 4,
     "fetch": _fetch_projecao_acumulada},
]
