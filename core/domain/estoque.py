"""
Regras de negócio do módulo Estoque/Produtos: KPIs, estoque parado, ruptura,
curva ABC, giro por grupo e top produtos. Não faz SQL direto — todo acesso ao
Firebird passa por core.data.repositories.estoque_repo.
"""
from __future__ import annotations

import pandas as pd
from core.data.repositories import estoque_repo as repo
from core.domain.classificacao import classe_por_acumulado


def get_estoque_geral() -> pd.DataFrame:
    """Retorna todos os produtos com dados de estoque (COMPPROD × PRODUTO × GRUPROD)."""
    return repo.fetch_estoque_geral()


def get_kpis_estoque(df: pd.DataFrame | None = None) -> dict:
    """KPIs consolidados de estoque a partir do DataFrame get_estoque_geral()."""
    if df is None:
        df = get_estoque_geral()
    if df.empty:
        return {"total_skus": 0, "skus_com_estoque": 0, "skus_ruptura": 0,
                "skus_abaixo_min": 0, "qtd_total": 0.0,
                "valor_custo": 0.0, "valor_venda": 0.0}
    com = df[df["QTD"] > 0]
    abaixo = df[(df["QTD"] < df["EST_MINIMO"]) & (df["EST_MINIMO"] > 0)]
    return {
        "total_skus":       len(df),
        "skus_com_estoque": int((df["QTD"] > 0).sum()),
        "skus_ruptura":     int((df["QTD"] <= 0).sum()),
        "skus_abaixo_min":  len(abaixo),
        "qtd_total":        float(com["QTD"].sum()),
        "valor_custo":      float(com["VALOR_CUSTO"].sum()),
        "valor_venda":      float(com["VALOR_VENDA"].sum()),
    }


def get_ultima_venda() -> pd.DataFrame:
    """Retorna a data da última venda (MVGERAL TM=55) por produto."""
    return repo.fetch_ultima_venda()


def get_estoque_parado(dias: int = 90, df_estoque: pd.DataFrame | None = None,
                       df_ult_venda: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Produtos com estoque > 0 e sem venda nos últimos `dias` dias.
    Retorna DataFrame ordenado por VALOR_CUSTO desc.
    """
    if df_estoque is None:
        df_estoque = get_estoque_geral()
    if df_ult_venda is None:
        df_ult_venda = get_ultima_venda()

    com_estoque = df_estoque[df_estoque["QTD"] > 0].copy()
    if com_estoque.empty:
        return com_estoque

    corte = pd.Timestamp.now() - pd.Timedelta(days=dias)
    merged = com_estoque.merge(df_ult_venda, on="CODPROD", how="left")
    parado = merged[(merged["ULT_VENDA"].isna()) | (merged["ULT_VENDA"] < corte)].copy()
    parado["DIAS_PARADO"] = (pd.Timestamp.now() - parado["ULT_VENDA"]).dt.days
    parado["DIAS_PARADO"] = parado["DIAS_PARADO"].fillna(9999).astype(int)
    return parado.sort_values("VALOR_CUSTO", ascending=False).reset_index(drop=True)


def get_controle_operacional(df_estoque: pd.DataFrame | None = None) -> dict:
    """
    Retorna dois DataFrames:
    - 'ruptura': produtos com QTD <= 0 e ativos
    - 'abaixo_minimo': produtos com QTD < EST_MINIMO (EST_MINIMO > 0)
    """
    if df_estoque is None:
        df_estoque = get_estoque_geral()
    if df_estoque.empty:
        return {"ruptura": pd.DataFrame(), "abaixo_minimo": pd.DataFrame()}

    ruptura = df_estoque[
        (df_estoque["QTD"] <= 0) & (df_estoque["ATIVO"] != "N")
    ].copy().sort_values("DESCRICAO")

    abaixo = df_estoque[
        (df_estoque["QTD"] < df_estoque["EST_MINIMO"]) & (df_estoque["EST_MINIMO"] > 0)
    ].copy()
    abaixo["DEFICIT"] = abaixo["EST_MINIMO"] - abaixo["QTD"]
    abaixo = abaixo.sort_values("DEFICIT", ascending=False).reset_index(drop=True)

    return {"ruptura": ruptura, "abaixo_minimo": abaixo}


def get_curva_abc_estoque(df_estoque: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Curva ABC pelo valor de custo investido em estoque (regra de Pareto
    compartilhada com a curva ABC comercial — ver core.domain.classificacao).
    Classe A = até 80% do valor total, B = 80-95%, C = resto.
    Retorna apenas produtos com QTD > 0 e VALOR_CUSTO > 0.
    """
    if df_estoque is None:
        df_estoque = get_estoque_geral()
    if df_estoque.empty:
        return df_estoque

    df = df_estoque[(df_estoque["QTD"] > 0) & (df_estoque["VALOR_CUSTO"] > 0)].copy()
    df = df.sort_values("VALOR_CUSTO", ascending=False).reset_index(drop=True)
    total = df["VALOR_CUSTO"].sum()
    if total == 0:
        return df

    df["PERC"]      = df["VALOR_CUSTO"] / total * 100
    df["ACUMULADO"] = df["VALOR_CUSTO"].cumsum() / total * 100
    df["CLASSE"] = df["ACUMULADO"].apply(classe_por_acumulado)
    return df


def get_giro_por_grupo(data_ini: str, data_fim: str,
                       df_estoque: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Giro de estoque por grupo = valor vendido no período / valor médio em estoque.
    Valor médio em estoque = valor atual (snapshot) — sem histórico diário disponível.
    """
    if df_estoque is None:
        df_estoque = get_estoque_geral()

    df_vendas = repo.fetch_vendas_periodo(data_ini, data_fim)

    if df_estoque.empty:
        return pd.DataFrame()

    # Estoque por grupo
    est_grupo = (
        df_estoque[df_estoque["QTD"] > 0]
        .groupby(["CODGRUPO", "GRUPO"])
        .agg(VALOR_ESTOQUE=("VALOR_CUSTO", "sum"), QTD_SKUS=("CODPROD", "count"))
        .reset_index()
    )

    if df_vendas.empty or df_vendas is None:
        est_grupo["FAT_VENDIDO"] = 0.0
        est_grupo["GIRO"] = 0.0
        return est_grupo.sort_values("VALOR_ESTOQUE", ascending=False).reset_index(drop=True)

    # Vendas por grupo
    for col in ("QTD_VENDIDA", "FAT_TOTAL"):
        df_vendas[col] = pd.to_numeric(df_vendas[col], errors="coerce").fillna(0)

    fat_grupo = (
        df_vendas.merge(
            df_estoque[["CODPROD", "CODGRUPO", "GRUPO"]].drop_duplicates(),
            on="CODPROD", how="left"
        )
        .groupby("CODGRUPO")
        .agg(FAT_VENDIDO=("FAT_TOTAL", "sum"))
        .reset_index()
    )

    df_giro = est_grupo.merge(fat_grupo, on="CODGRUPO", how="left")
    df_giro["FAT_VENDIDO"] = df_giro["FAT_VENDIDO"].fillna(0)
    df_giro["GIRO"] = df_giro.apply(
        lambda r: round(r["FAT_VENDIDO"] / r["VALOR_ESTOQUE"], 2)
        if r["VALOR_ESTOQUE"] > 0 else 0.0,
        axis=1
    )
    return df_giro.sort_values("FAT_VENDIDO", ascending=False).reset_index(drop=True)


def get_top_produtos(data_ini: str, data_fim: str,
                     df_estoque: pd.DataFrame | None = None,
                     top_n: int = 15) -> dict:
    """
    Top produtos por quantidade vendida, faturamento e lucro bruto.
    Lucro bruto = FAT - (QTD × PRECOCUSTO do COMPPROD) — custo atual como proxy.
    """
    if df_estoque is None:
        df_estoque = get_estoque_geral()

    df_vendas = repo.fetch_vendas_periodo(data_ini, data_fim)

    if df_vendas is None or df_vendas.empty:
        return {"por_qtd": pd.DataFrame(), "por_fat": pd.DataFrame(), "por_lucro": pd.DataFrame()}

    for col in ("QTD_VENDIDA", "FAT_TOTAL"):
        df_vendas[col] = pd.to_numeric(df_vendas[col], errors="coerce").fillna(0)

    # Adiciona descrição, grupo e custo atual
    cat = df_estoque[["CODPROD", "DESCRICAO", "GRUPO", "CUSTO_UNIT"]].drop_duplicates("CODPROD")
    df = df_vendas.merge(cat, on="CODPROD", how="left")
    df["DESCRICAO"] = df["DESCRICAO"].fillna(df["CODPROD"])
    df["GRUPO"] = df["GRUPO"].fillna("Sem grupo")
    df["CUSTO_UNIT"] = df["CUSTO_UNIT"].fillna(0)
    df["CMV"] = df["QTD_VENDIDA"] * df["CUSTO_UNIT"]
    df["LUCRO_BRUTO"] = df["FAT_TOTAL"] - df["CMV"]
    df["MARGEM"] = df.apply(
        lambda r: r["LUCRO_BRUTO"] / r["FAT_TOTAL"] * 100 if r["FAT_TOTAL"] > 0 else 0, axis=1
    )

    return {
        "por_qtd":   df.nlargest(top_n, "QTD_VENDIDA").reset_index(drop=True),
        "por_fat":   df.nlargest(top_n, "FAT_TOTAL").reset_index(drop=True),
        "por_lucro": df.nlargest(top_n, "LUCRO_BRUTO").reset_index(drop=True),
    }


def get_produtos_sem_venda(df_estoque: pd.DataFrame | None = None,
                           df_ult_venda: pd.DataFrame | None = None) -> pd.DataFrame:
    """Produtos com estoque > 0 que NUNCA foram vendidos (sem registro em MVGERAL TM=55)."""
    if df_estoque is None:
        df_estoque = get_estoque_geral()
    if df_ult_venda is None:
        df_ult_venda = get_ultima_venda()

    com_estoque = df_estoque[df_estoque["QTD"] > 0].copy()
    if com_estoque.empty:
        return com_estoque

    merged = com_estoque.merge(df_ult_venda, on="CODPROD", how="left")
    nunca = merged[merged["ULT_VENDA"].isna()].copy()
    nunca["DIAS_PARADO"] = 9999
    return nunca.sort_values("VALOR_CUSTO", ascending=False).reset_index(drop=True)


_TIPOMOV_DESC = {
    "55": "Venda PDV",
    "01": "Entrada NF",
    "09": "Saída consig./orç.",
    "61": "Dev. entrada",
    "05": "Dev. venda",
    "06": "Ajuste saída",
    "11": "Ajuste entrada",
}


def get_movimentacoes_produto(codprod: str) -> pd.DataFrame:
    """Histórico completo de movimentações de um produto (drill-down)."""
    df = repo.fetch_movimentacoes_produto(codprod)
    if df.empty:
        return df
    df["DESC_TIPO"] = df["TIPOMOV"].map(_TIPOMOV_DESC).fillna(df["TIPOMOV"])
    return df


def resumo_abc_estoque(df_abc: pd.DataFrame) -> pd.DataFrame:
    """Agrupa curva ABC em resumo por classe (SKUs, valor, % do total)."""
    if df_abc.empty:
        return df_abc
    total = df_abc["VALOR_CUSTO"].sum()
    grp = (
        df_abc.groupby("CLASSE")
        .agg(SKUS=("CODPROD", "count"), VALOR=("VALOR_CUSTO", "sum"))
        .reset_index()
    )
    grp["PERC"] = grp["VALOR"] / total * 100
    grp = grp.set_index("CLASSE").loc[["A", "B", "C"]].reset_index()
    return grp
