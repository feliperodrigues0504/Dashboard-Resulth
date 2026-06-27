"""
core/domain/relatorio_executivo.py — Relatório executivo consolidado
(Financeiro + Comercial + Estoque + Compras + Alertas em um único PDF).

Gerado automaticamente toda semana pelo agendador (ver core/sync/agendador.py)
e gravado em data/relatorios/ — não depende de o usuário abrir o dashboard.
Também pode ser gerado manualmente a qualquer momento (botão "Gerar agora").
"""
from __future__ import annotations
import os
import glob
from datetime import date

import pandas as pd

from config.settings import REPORTS_DIR
from core.export import gerar_pdf


def _kpis_financeiro() -> dict:
    """Bloco de KPIs financeiros para o relatório consolidado (mesmos dados do card Caixa/AR/AP do home)."""
    from core.domain.financeiro import (
        get_contas_receber, get_contas_pagar, get_saldo_bancario, get_estoque_custo, get_kpis,
    )
    df_ar, df_ap = get_contas_receber(), get_contas_pagar()
    kpis = get_kpis(df_ar, df_ap, get_estoque_custo(), get_saldo_bancario())
    return {
        "Caixa": kpis.get("saldo_bco", 0),
        "A Receber (total)": kpis.get("total_ar", 0),
        "A Receber (vencido)": kpis.get("vencido_ar", 0),
        "A Pagar (total)": kpis.get("total_ap", 0),
        "A Pagar (vencido)": kpis.get("vencido_ap", 0),
        "Capital Operacional": kpis.get("capital_op", 0),
    }


def _kpis_comercial() -> dict:
    """Bloco de faturamento do mês corrente vs anterior."""
    from core.domain.comercial import get_faturamento
    df = get_faturamento(meses_historico=2)
    if df.empty:
        return {"Faturamento do mês": 0.0, "Faturamento mês anterior": 0.0}
    df["DATAFATURA"] = pd.to_datetime(df["DATAFATURA"], errors="coerce")
    hoje = pd.Timestamp.now()
    ini_m = pd.Timestamp(hoje.year, hoje.month, 1)
    ini_m_ant = ini_m - pd.DateOffset(months=1)
    fat_mes = float(df[df["DATAFATURA"] >= ini_m]["TOTALPEDIDO"].sum())
    fat_ant = float(df[(df["DATAFATURA"] >= ini_m_ant) & (df["DATAFATURA"] < ini_m)]["TOTALPEDIDO"].sum())
    return {"Faturamento do mês": fat_mes, "Faturamento mês anterior": fat_ant}


def _kpis_estoque() -> dict:
    """Bloco de estoque (SKUs e valor a custo)."""
    from core.domain.estoque import get_kpis_estoque
    k = get_kpis_estoque()
    return {
        "SKUs em estoque": k.get("skus_com_estoque", 0),
        "Estoque a custo": k.get("valor_custo", 0),
        "Estoque abaixo do mínimo": k.get("skus_abaixo_min", 0),
    }


def _tabela_alertas_criticos() -> pd.DataFrame:
    """Top 15 alertas críticos/urgentes ativos, para a seção de Alertas do relatório."""
    from core.domain.alertas import get_todos_alertas
    ini = (pd.Timestamp.now() - pd.DateOffset(months=3)).strftime("%Y-%m-%d")
    fim = (pd.Timestamp.now() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    todos = get_todos_alertas(ini, fim)
    prioritarios = [a for a in todos if a["nivel"] in ("critico", "urgente")][:15]
    if not prioritarios:
        return pd.DataFrame()
    return pd.DataFrame([
        {"Módulo": a["modulo"], "Nível": a["nivel"].upper(), "Alerta": a["titulo"]}
        for a in prioritarios
    ])


def _fmt_kpis(kpis: dict) -> dict:
    """Formata valores numéricos como R$ para exibição no PDF; mantém inteiros (contagens) como estão."""
    from components.metrics import fmt_brl
    out = {}
    for label, valor in kpis.items():
        if isinstance(valor, (int,)) and not isinstance(valor, bool):
            out[label] = str(valor)
        else:
            out[label] = fmt_brl(valor)
    return out


def gerar_relatorio_executivo() -> bytes:
    """Monta o PDF do relatório executivo consolidado (Financeiro+Comercial+Estoque+Alertas)."""
    kpis = {}
    kpis.update(_kpis_financeiro())
    kpis.update(_kpis_comercial())
    kpis.update(_kpis_estoque())

    secoes = {"Alertas críticos e urgentes": _tabela_alertas_criticos()}

    return gerar_pdf(
        titulo="Relatório Executivo — Cetel",
        kpis=_fmt_kpis(kpis),
        secoes=secoes,
        periodo_ini=None,
        periodo_fim=date.today(),
        comentario="Relatório consolidado gerado automaticamente — Financeiro, Comercial, Estoque e Alertas.",
    )


def gravar_relatorio_semanal() -> str | None:
    """
    Gera o relatório executivo e grava em data/relatorios/relatorio_AAAA-MM-DD.pdf
    (chamado pelo agendador, toda segunda-feira — ver core/sync/agendador.py).
    Retorna o caminho do arquivo gravado, ou None em caso de erro.
    """
    try:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        pdf_bytes = gerar_relatorio_executivo()
        caminho = os.path.join(REPORTS_DIR, f"relatorio_{date.today()}.pdf")
        with open(caminho, "wb") as f:
            f.write(bytes(pdf_bytes))
        return caminho
    except Exception as e:
        print(f"[relatorio_executivo] erro ao gravar relatório semanal: {e}")
        return None


def ultimo_relatorio() -> dict | None:
    """Retorna {'caminho', 'data', 'bytes'} do relatório mais recente em data/relatorios/, ou None se não houver nenhum."""
    if not os.path.isdir(REPORTS_DIR):
        return None
    arquivos = sorted(glob.glob(os.path.join(REPORTS_DIR, "relatorio_*.pdf")), reverse=True)
    if not arquivos:
        return None
    caminho = arquivos[0]
    with open(caminho, "rb") as f:
        conteudo = f.read()
    nome = os.path.basename(caminho)
    data_str = nome.replace("relatorio_", "").replace(".pdf", "")
    return {"caminho": caminho, "data": data_str, "bytes": conteudo}
