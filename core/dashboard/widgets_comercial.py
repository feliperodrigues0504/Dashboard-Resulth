"""
core/dashboard/widgets_comercial.py — widgets do Painel Personalizado
originados do módulo Comercial. Reusa core/domain/comercial.py — mesmas
funções que pages/02_Comercial.py já chama.
"""
from __future__ import annotations
from datetime import date
import pandas as pd

from core.dashboard import adapters as ad
from core.data.duckdb_store import get_config
from core.domain import comercial as com


def _base_comercial(data_ini: date, data_fim: date):
    """Faturamento (25 meses) filtrado pelo período do painel — base de quase todo widget comercial."""
    df_fat_raw = com.get_faturamento(meses_historico=25)
    return ad.filtra_periodo(df_fat_raw, "DATAFATURA", data_ini, data_fim)


def _base_itens(data_ini: date, data_fim: date):
    """Itens de pedido faturados no período (para lucro bruto/top produtos/concentração de produto)."""
    return com.get_itens_periodo(pd.Timestamp(data_ini), pd.Timestamp(data_fim))


def _fetch_kpis_comercial(chave: str, formatador: str = "brl"):
    def _fetch(data_ini: date, data_fim: date) -> dict:
        df_fat = _base_comercial(data_ini, data_fim)
        kpis = com.get_kpis_comercial(df_fat)
        return ad.kpi(kpis.get(chave, 0), formatador)
    return _fetch


def _fetch_meta_progresso(data_ini: date, data_fim: date) -> dict:
    meta_configurada = float(get_config("meta_faturamento_mensal", 0) or 0)
    meta_info = com.get_meta_mes(meta_configurada)
    df_mes = com.get_faturamento(meses_historico=1)
    proj = com.get_projecao_fechamento_mes(df_mes)
    meta = meta_info.get("meta", 0)
    if meta <= 0:
        return ad.progresso(0, "meta não configurada")
    pct = proj.get("total_ate_hoje", 0) / meta * 100
    return ad.progresso(pct, f"da meta ({meta_info.get('mes_ano','')})")


def _fetch_faturamento_periodo(data_ini: date, data_fim: date) -> dict:
    df_fat = _base_comercial(data_ini, data_fim)
    df = com.get_faturamento_periodo(df_fat, granularidade="dia")
    return ad.bar_de_df(df, "Periodo", "Faturamento", "Faturamento")


def _fetch_comparativo_faturamento(data_ini: date, data_fim: date) -> dict:
    df_fat = _base_comercial(data_ini, data_fim)
    d = com.get_comparativo_faturamento(df_fat)
    if not d:
        return ad.bar_de_df(pd.DataFrame(), "x", "y")
    df = pd.DataFrame({
        "Período": [d["label_atual"], d["label_mes_anterior"], d["label_ano_anterior"]],
        "Valor": [d["atual"], d["mes_anterior"], d["mesmo_mes_ano_anterior"]],
    })
    return ad.bar_de_df(df, "Período", "Valor", "Faturamento")


def _fetch_ranking_vendedores(data_ini: date, data_fim: date) -> dict:
    df_fat = _base_comercial(data_ini, data_fim)
    df = com.get_ranking_vendedores(df_fat)
    return ad.tabela_de_df(df, ["NOME_VENDEDOR", "Faturamento", "Pedidos"])


def _fetch_funil_pedidos(data_ini: date, data_fim: date) -> dict:
    d = com.get_funil_pedidos(data_ini, data_fim)
    df = d.get("dados", pd.DataFrame())
    return ad.pie_de_df(df, "Situação", "Valor")


def _fetch_descontos(data_ini: date, data_fim: date) -> dict:
    df_fat = _base_comercial(data_ini, data_fim)
    df_itens = _base_itens(data_ini, data_fim)
    d = com.get_descontos_periodo(df_itens, df_fat)
    return ad.kpi(d.get("total_desconto", 0), "brl")


def _fetch_top_clientes_faturamento(data_ini: date, data_fim: date) -> dict:
    df_fat = _base_comercial(data_ini, data_fim)
    df = com.get_top_clientes_faturamento(df_fat, top_n=10)
    return ad.tabela_de_df(df, ["NOME_CLIENTE", "Faturamento", "Pedidos"])


def _fetch_top_clientes_lucro(data_ini: date, data_fim: date) -> dict:
    df_fat = _base_comercial(data_ini, data_fim)
    df_itens = _base_itens(data_ini, data_fim)
    df = com.get_top_clientes_lucro(df_itens, df_fat, top_n=10)
    return ad.tabela_de_df(df, ["NOME_CLIENTE", "LUCRO_BRUTO"])


def _fetch_top_produtos_comercial(data_ini: date, data_fim: date) -> dict:
    df_itens = _base_itens(data_ini, data_fim)
    df = com.get_top_produtos(df_itens, criterio="faturamento", top_n=10)
    return ad.tabela_de_df(df, ["PRODUTO", "Faturamento", "Quantidade"])


def _fetch_clientes_sem_comprar(data_ini: date, data_fim: date) -> dict:
    df_ultima = com.get_ultima_compra_clientes()
    df = com.get_clientes_sem_comprar(df_ultima, dias=60)
    return ad.kpi(len(df), "int")


def _fetch_clientes_queda(data_ini: date, data_fim: date) -> dict:
    df = com.get_clientes_queda_compras(meses_base=6, top_n=10)
    return ad.tabela_de_df(df, ["NOME_CLIENTE", "Queda_%", "Valor_Perdido"])


def _fetch_clientes_novos_recorrentes(data_ini: date, data_fim: date) -> dict:
    df_fat = _base_comercial(data_ini, data_fim)
    df_ultima = com.get_ultima_compra_clientes()
    d = com.get_clientes_novos_recorrentes(df_fat, df_ultima, data_ini)
    return ad.bar_de_df(d.get("dados", pd.DataFrame()), "Categoria", "Faturamento", "Faturamento")


def _fetch_concentracao_clientes(data_ini: date, data_fim: date) -> dict:
    df_fat = _base_comercial(data_ini, data_fim)
    d = com.get_concentracao_clientes(df_fat, top_n=10)
    df = d.get("dados", pd.DataFrame()).head(10)
    return ad.pie_de_df(df, "Cliente", "Valor")


def _fetch_concentracao_produtos(data_ini: date, data_fim: date) -> dict:
    df_itens = _base_itens(data_ini, data_fim)
    d = com.get_concentracao_produtos(df_itens, top_n=20)
    df = d.get("dados", pd.DataFrame()).head(10)
    return ad.pie_de_df(df, "Produto", "Valor")


def _fetch_sazonalidade(data_ini: date, data_fim: date) -> dict:
    df = com.get_sazonalidade(24)
    return ad.line_de_df(df, "MES_ANO", "FATURAMENTO", "Faturamento")


def _fetch_forma_pgto(data_ini: date, data_fim: date) -> dict:
    df_fat = _base_comercial(data_ini, data_fim)
    df = com.get_faturamento_por_forma_pgto(df_fat)
    return ad.pie_de_df(df, "CODFORMAPGTO", "VALOR_RATEADO")


WIDGETS_COMERCIAL = [
    {"id": "com_faturamento_total", "nome": "Faturamento do Período", "origem": "Comercial",
     "descricao": "Total faturado no período (filtro do painel).", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_kpis_comercial("total_faturado")},
    {"id": "com_ticket_medio", "nome": "Ticket Médio", "origem": "Comercial",
     "descricao": "Ticket médio geral do período.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_kpis_comercial("ticket_medio")},
    {"id": "com_meta_progresso", "nome": "Progresso da Meta do Mês", "origem": "Comercial",
     "descricao": "% da meta de faturamento mensal já atingida.", "tipo": "progresso", "w": 4, "h": 2,
     "fetch": _fetch_meta_progresso},
    {"id": "com_faturamento_periodo", "nome": "Faturamento por Dia", "origem": "Comercial",
     "descricao": "Evolução diária do faturamento no período.", "tipo": "bar", "w": 6, "h": 4,
     "fetch": _fetch_faturamento_periodo},
    {"id": "com_comparativo_faturamento", "nome": "Comparativo de Faturamento", "origem": "Comercial",
     "descricao": "Mês atual x mês anterior x mesmo mês ano anterior.", "tipo": "bar", "w": 6, "h": 4,
     "fetch": _fetch_comparativo_faturamento},
    {"id": "com_ranking_vendedores", "nome": "Ranking de Vendedores", "origem": "Comercial",
     "descricao": "Faturamento e pedidos por vendedor.", "tipo": "tabela", "w": 6, "h": 4,
     "fetch": _fetch_ranking_vendedores},
    {"id": "com_funil_pedidos", "nome": "Funil de Pedidos", "origem": "Comercial",
     "descricao": "Pedidos criados no período por status de faturamento.", "tipo": "pie", "w": 6, "h": 4,
     "fetch": _fetch_funil_pedidos},
    {"id": "com_descontos", "nome": "Descontos Concedidos", "origem": "Comercial",
     "descricao": "Total de descontos concedidos no período.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_descontos},
    {"id": "com_top_clientes_fat", "nome": "Top Clientes por Faturamento", "origem": "Comercial",
     "descricao": "Top 10 clientes por faturamento no período.", "tipo": "tabela", "w": 6, "h": 4,
     "fetch": _fetch_top_clientes_faturamento},
    {"id": "com_top_clientes_lucro", "nome": "Top Clientes por Lucro", "origem": "Comercial",
     "descricao": "Top 10 clientes por lucro bruto no período.", "tipo": "tabela", "w": 6, "h": 4,
     "fetch": _fetch_top_clientes_lucro},
    {"id": "com_top_produtos", "nome": "Top Produtos (Comercial)", "origem": "Comercial",
     "descricao": "Top 10 produtos por faturamento no período.", "tipo": "tabela", "w": 6, "h": 4,
     "fetch": _fetch_top_produtos_comercial},
    {"id": "com_clientes_sem_comprar", "nome": "Clientes Sem Comprar", "origem": "Comercial",
     "descricao": "Quantidade de clientes sem comprar há 60+ dias.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_clientes_sem_comprar},
    {"id": "com_clientes_queda", "nome": "Clientes em Queda de Compras", "origem": "Comercial",
     "descricao": "Top 10 clientes com maior queda de compras.", "tipo": "tabela", "w": 6, "h": 4,
     "fetch": _fetch_clientes_queda},
    {"id": "com_novos_recorrentes", "nome": "Clientes Novos x Recorrentes", "origem": "Comercial",
     "descricao": "Faturamento de clientes novos vs recorrentes no período.", "tipo": "bar", "w": 6, "h": 4,
     "fetch": _fetch_clientes_novos_recorrentes},
    {"id": "com_concentracao_clientes", "nome": "Concentração de Clientes", "origem": "Comercial",
     "descricao": "Top 10 clientes por participação no faturamento.", "tipo": "pie", "w": 6, "h": 4,
     "fetch": _fetch_concentracao_clientes},
    {"id": "com_concentracao_produtos", "nome": "Concentração de Produtos", "origem": "Comercial",
     "descricao": "Top 10 produtos por participação no faturamento.", "tipo": "pie", "w": 6, "h": 4,
     "fetch": _fetch_concentracao_produtos},
    {"id": "com_sazonalidade", "nome": "Sazonalidade (24 meses)", "origem": "Comercial",
     "descricao": "Série mensal de faturamento dos últimos 24 meses.", "tipo": "line", "w": 6, "h": 4,
     "fetch": _fetch_sazonalidade},
    {"id": "com_forma_pgto", "nome": "Faturamento por Forma de Pagamento", "origem": "Comercial",
     "descricao": "Rateio proporcional do faturamento por forma de pagamento.", "tipo": "pie", "w": 6, "h": 4,
     "fetch": _fetch_forma_pgto},
]
