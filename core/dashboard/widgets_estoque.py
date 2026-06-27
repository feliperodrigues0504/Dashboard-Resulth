"""
core/dashboard/widgets_estoque.py — widgets do Painel Personalizado
originados do módulo Estoque. Reusa core/domain/estoque.py.
"""
from __future__ import annotations
from datetime import date
import pandas as pd

from core.dashboard import adapters as ad
from core.domain import estoque as est


def _fetch_kpi_estoque(chave: str, formatador: str = "int"):
    def _fetch(data_ini: date, data_fim: date) -> dict:
        kpis = est.get_kpis_estoque()
        return ad.kpi(kpis.get(chave, 0), formatador)
    return _fetch


def _fetch_curva_abc_estoque(data_ini: date, data_fim: date) -> dict:
    df_abc = est.get_curva_abc_estoque()
    resumo = est.resumo_abc_estoque(df_abc)
    return ad.pie_de_df(resumo, "CLASSE", "VALOR")


def _fetch_giro_por_grupo(data_ini: date, data_fim: date) -> dict:
    df = est.get_giro_por_grupo(str(data_ini), str(data_fim))
    return ad.bar_de_df(df.head(10), "GRUPO", "GIRO", "Giro")


def _fetch_top_produtos_estoque(data_ini: date, data_fim: date) -> dict:
    d = est.get_top_produtos(str(data_ini), str(data_fim), top_n=10)
    return ad.tabela_de_df(d.get("por_fat", pd.DataFrame()), ["DESCRICAO", "FAT_TOTAL", "QTD_VENDIDA"])


def _fetch_estoque_parado(data_ini: date, data_fim: date) -> dict:
    df = est.get_estoque_parado(90)
    return ad.kpi(float(df["VALOR_CUSTO"].sum()) if not df.empty else 0, "brl")


def _fetch_produtos_sem_venda(data_ini: date, data_fim: date) -> dict:
    df = est.get_produtos_sem_venda()
    return ad.tabela_de_df(df, ["DESCRICAO", "GRUPO", "VALOR_CUSTO"])


def _fetch_controle_operacional(data_ini: date, data_fim: date) -> dict:
    ctrl = est.get_controle_operacional()
    df_ruptura = ctrl.get("ruptura", pd.DataFrame())
    df_abaixo = ctrl.get("abaixo_minimo", pd.DataFrame())
    resumo = pd.DataFrame({
        "Categoria": ["Ruptura", "Abaixo do mínimo"],
        "SKUs": [len(df_ruptura), len(df_abaixo)],
    })
    return ad.bar_de_df(resumo, "Categoria", "SKUs", "SKUs")


WIDGETS_ESTOQUE = [
    {"id": "est_total_skus", "nome": "Total de SKUs", "origem": "Estoque",
     "descricao": "Quantidade total de produtos cadastrados.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_kpi_estoque("total_skus")},
    {"id": "est_skus_com_estoque", "nome": "SKUs Com Estoque", "origem": "Estoque",
     "descricao": "Produtos com saldo em estoque > 0.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_kpi_estoque("skus_com_estoque")},
    {"id": "est_skus_ruptura", "nome": "SKUs em Ruptura", "origem": "Estoque",
     "descricao": "Produtos sem estoque.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_kpi_estoque("skus_ruptura")},
    {"id": "est_skus_abaixo_min", "nome": "SKUs Abaixo do Mínimo", "origem": "Estoque",
     "descricao": "Produtos com saldo abaixo do estoque mínimo cadastrado.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_kpi_estoque("skus_abaixo_min")},
    {"id": "est_valor_custo", "nome": "Estoque a Custo", "origem": "Estoque",
     "descricao": "Valor total do estoque a custo.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_kpi_estoque("valor_custo", "brl")},
    {"id": "est_valor_venda", "nome": "Estoque a Venda", "origem": "Estoque",
     "descricao": "Valor total do estoque a preço de venda.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_kpi_estoque("valor_venda", "brl")},
    {"id": "est_curva_abc", "nome": "Curva ABC de Estoque", "origem": "Estoque",
     "descricao": "Distribuição do valor de estoque por classe A/B/C.", "tipo": "pie", "w": 6, "h": 4,
     "fetch": _fetch_curva_abc_estoque},
    {"id": "est_giro_grupo", "nome": "Giro por Grupo", "origem": "Estoque",
     "descricao": "Giro de estoque por grupo de produto no período.", "tipo": "bar", "w": 6, "h": 4,
     "fetch": _fetch_giro_por_grupo},
    {"id": "est_top_produtos", "nome": "Top Produtos (Estoque)", "origem": "Estoque",
     "descricao": "Top 10 produtos por faturamento no período.", "tipo": "tabela", "w": 6, "h": 4,
     "fetch": _fetch_top_produtos_estoque},
    {"id": "est_estoque_parado", "nome": "Valor em Estoque Parado", "origem": "Estoque",
     "descricao": "Valor de custo parado (>90 dias sem venda).", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_estoque_parado},
    {"id": "est_sem_venda", "nome": "Produtos Sem Venda", "origem": "Estoque",
     "descricao": "Produtos com estoque que nunca foram vendidos.", "tipo": "tabela", "w": 6, "h": 4,
     "fetch": _fetch_produtos_sem_venda},
    {"id": "est_controle_operacional", "nome": "Controle Operacional", "origem": "Estoque",
     "descricao": "Ruptura vs abaixo do mínimo — contagem de SKUs.", "tipo": "bar", "w": 6, "h": 4,
     "fetch": _fetch_controle_operacional},
]
