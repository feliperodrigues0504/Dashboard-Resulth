"""
Regras de negócio do módulo Compras: histórico, rentabilidade por fornecedor,
produtos sem giro e estoque parado por fornecedor. Não faz SQL direto — todo
acesso ao Firebird passa por core.data.repositories.compras_repo.

Drill-down: Fornecedor → NFs → Itens.
Rentabilidade: Compras × Vendas geradas (MVGERAL TM=55 por produtos do fornecedor).
"""
from __future__ import annotations

import pandas as pd
from core.data.repositories import compras_repo as repo


def get_historico_compras(meses: int = 13) -> pd.DataFrame:
    """Compras mensais — últimos N meses."""
    corte = (pd.Timestamp.now() - pd.DateOffset(months=meses)).strftime("%Y-%m-%d")
    df = repo.fetch_historico_mensal(corte)
    if df.empty:
        return df
    for col in ("ANO", "MES", "QTD_NF", "QTD_FORNEC"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    df["TOTAL_COMPRADO"] = pd.to_numeric(df["TOTAL_COMPRADO"], errors="coerce").fillna(0)
    df["PERIODO"] = df.apply(lambda r: f"{int(r['MES']):02d}/{int(r['ANO'])}", axis=1)
    return df.sort_values(["ANO", "MES"]).reset_index(drop=True)


def get_compras_por_fornecedor(data_ini: str, data_fim: str) -> pd.DataFrame:
    """Compras agregadas por fornecedor no período."""
    df = repo.fetch_compras_fornecedor(data_ini, data_fim)
    if df.empty:
        return df
    df["TOTAL_COMPRADO"] = pd.to_numeric(df["TOTAL_COMPRADO"], errors="coerce").fillna(0)
    df["QTD_NF"] = pd.to_numeric(df["QTD_NF"], errors="coerce").fillna(0).astype(int)
    total = df["TOTAL_COMPRADO"].sum()
    df["PARTICIPACAO"] = df["TOTAL_COMPRADO"] / total * 100 if total > 0 else 0
    df["PARTICIPACAO_ACUM"] = df["PARTICIPACAO"].cumsum()
    df["NOME_EXIB"] = df.apply(
        lambda r: r["FANTASIA"].strip() if r["FANTASIA"] and r["FANTASIA"].strip() else r["FORNECEDOR"],
        axis=1)
    return df.reset_index(drop=True)


def get_nfs_fornecedor(codfornec: str, data_ini: str, data_fim: str) -> pd.DataFrame:
    """NFs de entrada de um fornecedor (drill-down nível 1)."""
    df = repo.fetch_nfs_fornecedor(codfornec, data_ini, data_fim)
    if df.empty:
        return df
    df["DT_ENTRADA"] = pd.to_datetime(df["DT_ENTRADA"], errors="coerce")
    df["DT_EMISSAO"] = pd.to_datetime(df["DT_EMISSAO"], errors="coerce")
    for col in ("TOTAL_NF", "DESC_PERC", "TOTAL_IPI"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def get_itens_nf_entrada(codfornec: str, numeronf: str) -> pd.DataFrame:
    """Itens de uma NF de entrada (drill-down nível 2)."""
    df = repo.fetch_itens_nf_entrada(codfornec, numeronf)
    if df.empty:
        return df
    for col in ("QUANTIDADE", "CUSTO_UNIT", "DESCONTO", "TOTAL_ITEM"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def get_relprfo() -> pd.DataFrame:
    """
    Relação produto-fornecedor (RELPRFO) — tabela pequena e estável, buscada
    uma única vez e compartilhada entre get_rentabilidade_fornecedor(),
    get_produtos_sem_giro() e get_estoque_parado_por_fornecedor() via
    parâmetro opcional, em vez de cada função refazer a mesma busca completa.
    """
    return repo.fetch_relprfo()


def get_estoque_prod() -> pd.DataFrame:
    """Estoque atual por produto (COMPPROD) — ver nota em get_relprfo()."""
    return repo.fetch_estoque_prod()


def get_rentabilidade_fornecedor(data_ini: str, data_fim: str,
                                 df_relprfo: pd.DataFrame | None = None,
                                 df_estoque: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Rentabilidade por fornecedor:
    - Comprado: NFENTRC total
    - Faturado: vendas PDV dos produtos vinculados ao fornecedor (RELPRFO)
    - CMV estimado: QTD_VENDIDA × COMPPROD.PRECOCUSTO (custo atual)
    - Lucro = Faturado - CMV
    - Margem = Lucro / Faturado × 100

    `df_relprfo`/`df_estoque`: passe os DataFrames já carregados (via
    get_relprfo()/get_estoque_prod()) quando esta função for chamada junto
    com get_produtos_sem_giro()/get_estoque_parado_por_fornecedor() na mesma
    página, para não repetir a mesma busca completa 2-3 vezes.
    """
    df_compras  = repo.fetch_compras_fornecedor(data_ini, data_fim)
    df_vendas   = repo.fetch_vendas_prod(data_ini, data_fim)
    if df_relprfo is None:
        df_relprfo = get_relprfo()
    if df_estoque is None:
        df_estoque = get_estoque_prod()

    if df_compras.empty:
        return pd.DataFrame()

    # Normaliza numéricos
    df_compras["TOTAL_COMPRADO"] = pd.to_numeric(df_compras["TOTAL_COMPRADO"], errors="coerce").fillna(0)

    if not df_vendas.empty:
        for col in ("QTD_VENDIDA", "FAT_TOTAL"):
            df_vendas[col] = pd.to_numeric(df_vendas[col], errors="coerce").fillna(0)

    # df_estoque já vem normalizado de get_estoque_prod()

    # Vendas por fornecedor via RELPRFO × MVGERAL
    if not df_relprfo.empty and not df_vendas.empty:
        rel_fat = df_relprfo.merge(df_vendas, on="CODPROD", how="inner")
        fat_forn = (rel_fat.groupby("CODFORNEC")
                    .agg(FAT_TOTAL=("FAT_TOTAL", "sum"),
                         QTD_PROD_VENDIDOS=("CODPROD", "nunique"))
                    .reset_index())
    else:
        fat_forn = pd.DataFrame(columns=["CODFORNEC", "FAT_TOTAL", "QTD_PROD_VENDIDOS"])

    # CMV por fornecedor (QTD_VENDIDA × custo atual do COMPPROD)
    if not df_relprfo.empty and not df_vendas.empty and not df_estoque.empty:
        vend_custo = df_vendas.merge(df_estoque[["CODPROD", "CUSTO_UNIT"]], on="CODPROD", how="left")
        vend_custo["CUSTO_UNIT"] = vend_custo["CUSTO_UNIT"].fillna(0)
        vend_custo["CMV"] = vend_custo["QTD_VENDIDA"] * vend_custo["CUSTO_UNIT"]
        cmv_forn = (df_relprfo.merge(vend_custo[["CODPROD", "CMV"]], on="CODPROD", how="inner")
                    .groupby("CODFORNEC")
                    .agg(CMV_TOTAL=("CMV", "sum"))
                    .reset_index())
    else:
        cmv_forn = pd.DataFrame(columns=["CODFORNEC", "CMV_TOTAL"])

    # Estoque por fornecedor
    if not df_relprfo.empty and not df_estoque.empty:
        est_forn = (df_relprfo.merge(df_estoque[["CODPROD", "QTD", "VALOR_CUSTO"]], on="CODPROD", how="inner")
                    .groupby("CODFORNEC")
                    .agg(ESTOQUE_QTD=("QTD", "sum"),
                         ESTOQUE_VALOR=("VALOR_CUSTO", "sum"),
                         ESTOQUE_SKUS=("CODPROD", "nunique"))
                    .reset_index())
    else:
        est_forn = pd.DataFrame(columns=["CODFORNEC", "ESTOQUE_QTD", "ESTOQUE_VALOR", "ESTOQUE_SKUS"])

    # Cria NOME_EXIB (nome fantasia se disponível, senão razão social)
    df_compras["NOME_EXIB"] = df_compras.apply(
        lambda r: r["FANTASIA"].strip() if r["FANTASIA"] and str(r["FANTASIA"]).strip() else r["FORNECEDOR"],
        axis=1)

    # Merge tudo
    df_rentabilidade = df_compras[["CODFORNEC", "NOME_EXIB", "FORNECEDOR", "QTD_NF", "TOTAL_COMPRADO"]].copy()
    df_rentabilidade = df_rentabilidade.merge(fat_forn,  on="CODFORNEC", how="left")
    df_rentabilidade = df_rentabilidade.merge(cmv_forn,  on="CODFORNEC", how="left")
    df_rentabilidade = df_rentabilidade.merge(est_forn,  on="CODFORNEC", how="left")

    df_rentabilidade["FAT_TOTAL"]          = df_rentabilidade["FAT_TOTAL"].fillna(0)
    df_rentabilidade["QTD_PROD_VENDIDOS"]  = df_rentabilidade["QTD_PROD_VENDIDOS"].fillna(0).astype(int)
    df_rentabilidade["CMV_TOTAL"]          = df_rentabilidade["CMV_TOTAL"].fillna(0)
    df_rentabilidade["ESTOQUE_QTD"]        = df_rentabilidade["ESTOQUE_QTD"].fillna(0)
    df_rentabilidade["ESTOQUE_VALOR"]      = df_rentabilidade["ESTOQUE_VALOR"].fillna(0)
    df_rentabilidade["ESTOQUE_SKUS"]       = df_rentabilidade["ESTOQUE_SKUS"].fillna(0).astype(int)
    df_rentabilidade["LUCRO_BRUTO"]        = df_rentabilidade["FAT_TOTAL"] - df_rentabilidade["CMV_TOTAL"]
    df_rentabilidade["MARGEM"]             = df_rentabilidade.apply(
        lambda r: r["LUCRO_BRUTO"] / r["FAT_TOTAL"] * 100 if r["FAT_TOTAL"] > 0 else 0, axis=1)
    total_compras = df_rentabilidade["TOTAL_COMPRADO"].sum()
    df_rentabilidade["PART_COMPRAS"]       = df_rentabilidade["TOTAL_COMPRADO"] / total_compras * 100 if total_compras > 0 else 0

    return df_rentabilidade.sort_values("TOTAL_COMPRADO", ascending=False).reset_index(drop=True)


def get_produtos_sem_giro(data_ini: str, data_fim: str,
                          df_relprfo: pd.DataFrame | None = None,
                          df_estoque: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Produtos comprados no período mas sem nenhuma venda PDV no mesmo período.
    Retorna ordenado por valor imobilizado (COMPPROD.ESTOQUE × PRECOCUSTO).

    `df_relprfo`/`df_estoque`: ver nota em get_rentabilidade_fornecedor().
    """
    df_itens    = repo.fetch_itens_periodo(data_ini, data_fim)
    df_vendas   = repo.fetch_vendas_prod(data_ini, data_fim)
    if df_estoque is None:
        df_estoque = get_estoque_prod()
    if df_relprfo is None:
        df_relprfo = get_relprfo()

    if df_itens.empty:
        return pd.DataFrame()

    for col in ("QTD_COMPRADA", "VALOR_COMPRADO"):
        df_itens[col] = pd.to_numeric(df_itens[col], errors="coerce").fillna(0)

    # Produtos sem giro = comprados mas não vendidos
    if not df_vendas.empty:
        prods_vendidos = set(df_vendas["CODPROD"].unique())
    else:
        prods_vendidos = set()

    sem_giro = df_itens[~df_itens["CODPROD"].isin(prods_vendidos)].copy()
    if sem_giro.empty:
        return pd.DataFrame()

    # Agrega por produto (pode ter comprado de vários fornecedores)
    sem_giro_agg = (sem_giro.groupby("CODPROD")
                    .agg(QTD_COMPRADA=("QTD_COMPRADA", "sum"),
                         VALOR_COMPRADO=("VALOR_COMPRADO", "sum"))
                    .reset_index())

    # Descrição e grupo: reaproveita core.domain.estoque.get_estoque_geral()
    # (já faz COMPPROD×PRODUTO×GRUPROD em 1 query) em vez de buscar PRODUTO
    # (9.800+ linhas) e GRUPROD inteiros aqui só para rotular esta dezena de produtos.
    try:
        from core.domain.estoque import get_estoque_geral
        cat = get_estoque_geral()[["CODPROD", "DESCRICAO", "GRUPO"]].drop_duplicates("CODPROD")
        sem_giro_agg = sem_giro_agg.merge(cat, on="CODPROD", how="left")
        sem_giro_agg["DESCRICAO"] = sem_giro_agg["DESCRICAO"].fillna(sem_giro_agg["CODPROD"])
        sem_giro_agg["GRUPO"] = sem_giro_agg["GRUPO"].fillna("—")
    except Exception:
        sem_giro_agg["DESCRICAO"] = sem_giro_agg["CODPROD"]
        sem_giro_agg["GRUPO"] = "—"

    # Estoque atual e fornecedor principal
    if not df_estoque.empty:
        sem_giro_agg = sem_giro_agg.merge(
            df_estoque[["CODPROD", "QTD", "VALOR_CUSTO"]], on="CODPROD", how="left")
        sem_giro_agg["QTD"] = sem_giro_agg["QTD"].fillna(0)
        sem_giro_agg["VALOR_CUSTO"] = sem_giro_agg["VALOR_CUSTO"].fillna(0)
    else:
        sem_giro_agg["QTD"] = 0
        sem_giro_agg["VALOR_CUSTO"] = 0

    if not df_relprfo.empty:
        principal = df_relprfo[df_relprfo["PRINCIPAL"] == "S"][["CODPROD", "CODFORNEC"]]
        sem_giro_agg = sem_giro_agg.merge(principal, on="CODPROD", how="left")
    else:
        sem_giro_agg["CODFORNEC"] = ""

    return sem_giro_agg.sort_values("VALOR_CUSTO", ascending=False).reset_index(drop=True)


def get_estoque_parado_por_fornecedor(dias: int = 90,
                                      df_relprfo: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Estoque parado agrupado pelo fornecedor principal (RELPRFO.PRINCIPAL='S').
    Usa get_estoque_parado do módulo de estoque.

    `df_relprfo`: ver nota em get_rentabilidade_fornecedor().
    """
    from core.domain.estoque import get_estoque_geral, get_ultima_venda, get_estoque_parado

    df_est    = get_estoque_geral()
    df_uv     = get_ultima_venda()
    df_parado = get_estoque_parado(dias, df_est, df_uv)

    if df_parado.empty:
        return pd.DataFrame()

    if df_relprfo is None:
        df_relprfo = get_relprfo()
    df_fornece = repo.fetch_fornecedores_basico()

    if df_relprfo.empty:
        return df_parado

    principal = df_relprfo[df_relprfo["PRINCIPAL"] == "S"][["CODPROD", "CODFORNEC"]]
    merged = df_parado.merge(principal, on="CODPROD", how="left")
    merged = merged.merge(df_fornece, on="CODFORNEC", how="left")
    merged["FORNECEDOR"] = merged.apply(
        lambda r: (r["FANTASIA"].strip() if r["FANTASIA"] and r["FANTASIA"].strip()
                   else r["FORNECEDOR"]) if pd.notna(r.get("FORNECEDOR")) else "Sem fornecedor",
        axis=1)

    grp = (merged.groupby("FORNECEDOR")
           .agg(SKUS=("CODPROD", "count"),
                QTD=("QTD", "sum"),
                VALOR_CUSTO=("VALOR_CUSTO", "sum"))
           .reset_index()
           .sort_values("VALOR_CUSTO", ascending=False))
    return grp.reset_index(drop=True)


def get_kpis_compras(data_ini: str, data_fim: str) -> dict:
    """KPIs de resumo de compras do período."""
    df = repo.fetch_kpis_compras_raw(data_ini, data_fim)
    if df.empty:
        return {"total_comprado": 0, "qtd_nf": 0, "qtd_fornec": 0}
    row = df.iloc[0]
    return {
        "total_comprado": float(row["TOTAL_COMPRADO"] or 0),
        "qtd_nf":         int(row["QTD_NF"] or 0),
        "qtd_fornec":     int(row["QTD_FORNEC"] or 0),
    }
