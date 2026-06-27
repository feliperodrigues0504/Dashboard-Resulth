"""
core/dashboard/widgets_compras.py — widgets do Painel Personalizado
originados do módulo Compras. Reusa core/domain/compras.py.
"""
from __future__ import annotations
from datetime import date

from core.dashboard import adapters as ad
from core.domain import compras as cmp


def _fetch_kpis_compras(chave: str, formatador: str = "brl"):
    def _fetch(data_ini: date, data_fim: date) -> dict:
        kpis = cmp.get_kpis_compras(str(data_ini), str(data_fim))
        return ad.kpi(kpis.get(chave, 0), formatador)
    return _fetch


def _fetch_historico_compras(data_ini: date, data_fim: date) -> dict:
    df = cmp.get_historico_compras(13)
    return ad.bar_de_df(df, "PERIODO", "TOTAL_COMPRADO", "Comprado")


def _fetch_top_fornecedores(data_ini: date, data_fim: date) -> dict:
    df = cmp.get_compras_por_fornecedor(str(data_ini), str(data_fim))
    return ad.tabela_de_df(df.head(10), ["NOME_EXIB", "TOTAL_COMPRADO", "PARTICIPACAO"])


def _fetch_rentabilidade_fornecedor(data_ini: date, data_fim: date) -> dict:
    df = cmp.get_rentabilidade_fornecedor(str(data_ini), str(data_fim))
    return ad.tabela_de_df(df.head(10), ["NOME_EXIB", "FAT_TOTAL", "LUCRO_BRUTO", "MARGEM"])


def _fetch_produtos_sem_giro(data_ini: date, data_fim: date) -> dict:
    df = cmp.get_produtos_sem_giro(str(data_ini), str(data_fim))
    return ad.kpi(float(df["VALOR_CUSTO"].sum()) if not df.empty else 0, "brl")


def _fetch_estoque_parado_fornecedor(data_ini: date, data_fim: date) -> dict:
    df = cmp.get_estoque_parado_por_fornecedor(90)
    return ad.tabela_de_df(df.head(10), ["FORNECEDOR", "SKUS", "VALOR_CUSTO"])


WIDGETS_COMPRAS = [
    {"id": "cmp_total_comprado", "nome": "Total Comprado no Período", "origem": "Compras",
     "descricao": "Total comprado (NFs de entrada) no período.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_kpis_compras("total_comprado")},
    {"id": "cmp_qtd_fornec", "nome": "Fornecedores Ativos", "origem": "Compras",
     "descricao": "Quantidade de fornecedores com compra no período.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_kpis_compras("qtd_fornec", "int")},
    {"id": "cmp_historico", "nome": "Histórico de Compras", "origem": "Compras",
     "descricao": "Compras mensais dos últimos 13 meses.", "tipo": "bar", "w": 6, "h": 4,
     "fetch": _fetch_historico_compras},
    {"id": "cmp_top_fornecedores", "nome": "Top Fornecedores", "origem": "Compras",
     "descricao": "Top 10 fornecedores por valor comprado no período.", "tipo": "tabela", "w": 6, "h": 4,
     "fetch": _fetch_top_fornecedores},
    {"id": "cmp_rentabilidade_fornecedor", "nome": "Rentabilidade por Fornecedor", "origem": "Compras",
     "descricao": "Top 10 fornecedores por lucro bruto gerado.", "tipo": "tabela", "w": 6, "h": 4,
     "fetch": _fetch_rentabilidade_fornecedor},
    {"id": "cmp_sem_giro", "nome": "Produtos Sem Giro (Valor)", "origem": "Compras",
     "descricao": "Valor comprado sem nenhuma venda no período.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_produtos_sem_giro},
    {"id": "cmp_estoque_parado_fornecedor", "nome": "Estoque Parado por Fornecedor", "origem": "Compras",
     "descricao": "Top 10 fornecedores com estoque parado (>90d).", "tipo": "tabela", "w": 6, "h": 4,
     "fetch": _fetch_estoque_parado_fornecedor},
]
