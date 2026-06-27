"""
Regras de negócio do módulo comercial: KPIs, metas, funil, ranking de
vendedores, curva ABC, sazonalidade e indicadores de carteira de clientes.
Não faz SQL direto — todo acesso ao Firebird passa por
core.data.repositories.comercial_repo.
"""
import pandas as pd
from core.data.repositories import comercial_repo as repo
from core.domain.classificacao import curva_abc as _curva_abc


def get_faturamento(meses_historico: int = 25) -> pd.DataFrame:
    """
    Pedidos faturados dos últimos N meses (base para todas as análises comerciais).
    Janela ampla o suficiente para cobrir a sazonalidade de 24 meses; os filtros
    globais (período, empresa, vendedor, cliente...) recortam essa base em pandas.
    """
    data_ini = pd.Timestamp.now() - pd.DateOffset(months=meses_historico)
    df = repo.fetch_faturamento(data_ini.strftime("%Y-%m-%d"))
    if df.empty:
        return df
    df["DATAFATURA"]  = pd.to_datetime(df["DATAFATURA"])
    df["TOTALPEDIDO"] = pd.to_numeric(df["TOTALPEDIDO"], errors="coerce").fillna(0)
    return df


def get_kpis_comercial(df_periodo: pd.DataFrame) -> dict:
    """KPIs do recorte (filtros globais já aplicados): total faturado, ticket, nº clientes."""
    if df_periodo.empty:
        return {"total_faturado": 0.0, "qtd_pedidos": 0, "ticket_medio": 0.0, "n_clientes": 0}
    total = float(df_periodo["TOTALPEDIDO"].sum())
    qtd = len(df_periodo)
    return {
        "total_faturado": total,
        "qtd_pedidos": qtd,
        "ticket_medio": total / qtd if qtd else 0.0,
        "n_clientes": int(df_periodo["CODCLIENTE"].nunique()),
    }


# ── Meta do mês ───────────────────────────────────────────────────────────────

def get_meta_mes(meta_configurada: float = 0.0) -> dict:
    """
    Meta de faturamento do mês corrente.
    Prioriza METAFATURAMENTOMENSAL (ERP); como a tabela está vazia na base atual,
    cai para o valor configurado manualmente no DuckDB (mesmo padrão do piso_caixa).
    """
    hoje = pd.Timestamp.now()
    mes_ano = f"{hoje.month:02d}/{hoje.year}"
    meta_erp = 0.0
    df = repo.fetch_meta_mes(mes_ano)
    if not df.empty and df.iloc[0]["META"]:
        meta_erp = float(df.iloc[0]["META"])

    meta = meta_erp if meta_erp > 0 else float(meta_configurada or 0)
    return {
        "meta": meta,
        "fonte": "ERP (METAFATURAMENTOMENSAL)" if meta_erp > 0 else "Configurada manualmente",
        "mes_ano": mes_ano,
    }


def get_projecao_fechamento_mes(df_fat: pd.DataFrame) -> dict:
    """Projeção linear de fechamento do mês corrente, baseada no ritmo diário até hoje."""
    hoje = pd.Timestamp.now()
    inicio_mes = pd.Timestamp(hoje.year, hoje.month, 1)
    dias_no_mes = (inicio_mes + pd.offsets.MonthEnd(1)).day
    dias_passados = hoje.day

    if df_fat.empty:
        return {"total_ate_hoje": 0.0, "projecao": 0.0,
                "dias_passados": dias_passados, "dias_no_mes": dias_no_mes}

    mes_atual = df_fat[(df_fat["DATAFATURA"] >= inicio_mes) & (df_fat["DATAFATURA"] <= hoje)]
    total_ate_hoje = float(mes_atual["TOTALPEDIDO"].sum())
    projecao = (total_ate_hoje / dias_passados * dias_no_mes) if dias_passados else 0.0
    return {
        "total_ate_hoje": total_ate_hoje,
        "projecao": projecao,
        "dias_passados": dias_passados,
        "dias_no_mes": dias_no_mes,
    }


# ── Faturamento por período / comparativos ──────────────────────────────────

def get_faturamento_periodo(df_fat: pd.DataFrame, granularidade: str = "dia") -> pd.DataFrame:
    """Agrega faturamento por dia / semana / quinzena / mês."""
    if df_fat.empty:
        return pd.DataFrame()
    df_periodo = df_fat.copy()
    if granularidade == "dia":
        df_periodo["Periodo"] = df_periodo["DATAFATURA"].dt.normalize()
    elif granularidade == "semana":
        df_periodo["Periodo"] = df_periodo["DATAFATURA"].dt.to_period("W").apply(lambda p: p.start_time)
    elif granularidade == "quinzena":
        inicio_mes = df_periodo["DATAFATURA"].dt.to_period("M").dt.start_time
        quinzena = (df_periodo["DATAFATURA"].dt.day > 15).astype(int) * 15
        df_periodo["Periodo"] = inicio_mes + pd.to_timedelta(quinzena, unit="D")
    else:  # mes
        df_periodo["Periodo"] = df_periodo["DATAFATURA"].dt.to_period("M").apply(lambda p: p.start_time)

    agregado = df_periodo.groupby("Periodo").agg(
        Faturamento=("TOTALPEDIDO", "sum"),
        Qtd_Pedidos=("CODPEDIDO", "count"),
    ).reset_index().sort_values("Periodo")
    return agregado


def get_comparativo_faturamento(df_fat: pd.DataFrame) -> dict:
    """Mês atual x mês anterior x mesmo mês do ano anterior (a partir da base de faturamento)."""
    if df_fat.empty:
        return {}
    hoje = pd.Timestamp.now()

    def _total_mes(ref: pd.Timestamp) -> float:
        """Soma o TOTALPEDIDO faturado no mês calendário de `ref`."""
        ini = pd.Timestamp(ref.year, ref.month, 1)
        fim = ini + pd.offsets.MonthEnd(1)
        sub = df_fat[(df_fat["DATAFATURA"] >= ini) & (df_fat["DATAFATURA"] <= fim)]
        return float(sub["TOTALPEDIDO"].sum())

    mes_anterior = hoje - pd.DateOffset(months=1)
    ano_anterior = hoje - pd.DateOffset(years=1)
    return {
        "atual":                  _total_mes(hoje),
        "mes_anterior":           _total_mes(mes_anterior),
        "mesmo_mes_ano_anterior": _total_mes(ano_anterior),
        "label_atual":          hoje.strftime("%m/%Y"),
        "label_mes_anterior":   mes_anterior.strftime("%m/%Y"),
        "label_ano_anterior":   ano_anterior.strftime("%m/%Y"),
    }


def get_funil_pedidos(data_ini, data_fim) -> dict:
    """
    Funil de aproveitamento dos pedidos CRIADOS no período (por DATAPEDIDO),
    agrupado pelo status atual de faturamento (PEDIDOC.FATURADO):
    S = faturado, N = pendente/não faturado, X = cancelado/outro.
    Mostra a taxa de conversão e o valor parado em pedidos pendentes — um
    indicador de funil que complementa o faturamento (que olha por DATAFATURA).
    Atenção: pedidos criados perto do fim do período podem ainda ser faturados
    depois — a taxa reflete o status "até agora", não o resultado final do lote.
    """
    ini = pd.Timestamp(data_ini).strftime("%Y-%m-%d")
    fim = (pd.Timestamp(data_fim) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    vazio = {"total_pedidos": 0, "qtd_faturados": 0, "taxa_conversao": 0.0,
             "valor_pendente": 0.0, "dados": pd.DataFrame()}
    df = repo.fetch_funil_pedidos(ini, fim)
    if df.empty:
        return vazio

    df["QTD"] = pd.to_numeric(df["QTD"], errors="coerce").fillna(0).astype(int)
    df["VALOR"] = pd.to_numeric(df["VALOR"], errors="coerce").fillna(0)
    rotulo = {"S": "Faturado", "N": "Não faturado / pendente", "X": "Cancelado / outro"}
    df["Situação"] = df["STATUS"].map(rotulo).fillna(df["STATUS"])

    total = int(df["QTD"].sum())
    faturados = int(df.loc[df["STATUS"] == "S", "QTD"].sum())
    return {
        "total_pedidos": total,
        "qtd_faturados": faturados,
        "taxa_conversao": (faturados / total * 100) if total else 0.0,
        "valor_pendente": float(df.loc[df["STATUS"] == "N", "VALOR"].sum()),
        "dados": (df[["Situação", "QTD", "VALOR"]]
                  .rename(columns={"QTD": "Quantidade", "VALOR": "Valor"})
                  .sort_values("Quantidade", ascending=False)),
    }


def get_ticket_medio(df_fat: pd.DataFrame) -> dict:
    """Ticket médio geral e por vendedor."""
    if df_fat.empty:
        return {"geral": 0.0, "por_vendedor": pd.DataFrame()}
    geral = float(df_fat["TOTALPEDIDO"].sum() / len(df_fat))
    por_vend = df_fat.groupby(["CODVENDEDOR", "NOME_VENDEDOR"]).agg(
        Faturamento=("TOTALPEDIDO", "sum"),
        Pedidos=("CODPEDIDO", "count"),
    ).reset_index()
    por_vend["Ticket_Medio"] = por_vend["Faturamento"] / por_vend["Pedidos"]
    return {"geral": geral, "por_vendedor": por_vend.sort_values("Ticket_Medio", ascending=False)}


def get_ranking_vendedores(df_fat: pd.DataFrame) -> pd.DataFrame:
    """
    Placar de vendedores no período: faturamento, nº de pedidos, ticket médio
    e nº de clientes atendidos — ordenado por faturamento, com posição no ranking.
    Usa só a base de faturamento já carregada (sem nova consulta ao Firebird).
    """
    if df_fat.empty:
        return pd.DataFrame()
    g = df_fat.groupby(["CODVENDEDOR", "NOME_VENDEDOR"]).agg(
        Faturamento=("TOTALPEDIDO", "sum"),
        Pedidos=("CODPEDIDO", "count"),
        Clientes=("CODCLIENTE", "nunique"),
    ).reset_index()
    g["Ticket_Medio"] = g["Faturamento"] / g["Pedidos"]
    g = g.sort_values("Faturamento", ascending=False).reset_index(drop=True)
    g.insert(0, "Posição", range(1, len(g) + 1))
    return g


# ── Descontos concedidos ─────────────────────────────────────────────────────

def get_descontos_periodo(df_itens: pd.DataFrame, df_fat: pd.DataFrame) -> dict:
    """
    Descontos concedidos nos itens faturados do período (PEDIDOI.DESCONTOVLR):
    total, percentual sobre o faturamento líquido dos itens, e ranking por
    vendedor/cliente — ajuda a identificar onde a margem está sendo cedida em
    negociação. Reaproveita `df_itens` (já carregado para lucro bruto/top produtos),
    sem nova consulta pesada ao Firebird.
    """
    vazio = {"total_desconto": 0.0, "perc_sobre_faturado": 0.0,
             "por_vendedor": pd.DataFrame(), "por_cliente": pd.DataFrame()}
    if df_itens.empty or "DESCONTO" not in df_itens.columns:
        return vazio

    total_desconto = float(df_itens["DESCONTO"].sum())
    total_faturado = float(df_itens["TOTALRATEADO"].sum())
    perc = (total_desconto / total_faturado * 100) if total_faturado else 0.0

    mapa_vend = df_fat[["CODVENDEDOR", "NOME_VENDEDOR"]].drop_duplicates()
    por_vendedor = (df_itens.groupby("CODVENDEDOR")
                    .agg(Desconto=("DESCONTO", "sum"), Faturamento=("TOTALRATEADO", "sum"))
                    .reset_index()
                    .merge(mapa_vend, on="CODVENDEDOR", how="left"))
    por_vendedor["Desconto_%"] = por_vendedor.apply(
        lambda r: (r["Desconto"] / r["Faturamento"] * 100) if r["Faturamento"] else 0.0, axis=1
    ).round(1)
    por_vendedor = por_vendedor.sort_values("Desconto", ascending=False)

    mapa_cli = df_fat[["CODCLIENTE", "NOME_CLIENTE"]].drop_duplicates()
    por_cliente = (df_itens.groupby("CODCLIENTE")
                   .agg(Desconto=("DESCONTO", "sum"), Faturamento=("TOTALRATEADO", "sum"))
                   .reset_index()
                   .merge(mapa_cli, on="CODCLIENTE", how="left"))
    por_cliente["Desconto_%"] = por_cliente.apply(
        lambda r: (r["Desconto"] / r["Faturamento"] * 100) if r["Faturamento"] else 0.0, axis=1
    ).round(1)
    por_cliente = por_cliente[por_cliente["Desconto"] > 0].sort_values("Desconto", ascending=False).head(10)

    return {
        "total_desconto": total_desconto,
        "perc_sobre_faturado": perc,
        "por_vendedor": por_vendedor,
        "por_cliente": por_cliente,
    }


# ── Itens do pedido (lucro bruto / top produtos / drill-down) ───────────────

def get_itens_periodo(data_ini, data_fim) -> pd.DataFrame:
    """
    Itens vendidos no período (faturados), com custo atual (COMPPROD.PRECOCUSTO)
    para cálculo de Lucro Bruto estimado. Usado em Top Clientes/Produtos por lucro
    e Concentração por produto — NÃO usar para janelas muito amplas (24m de itens
    é pesado); manter restrito ao período filtrado.
    """
    ini = pd.Timestamp(data_ini).strftime("%Y-%m-%d")
    fim = (pd.Timestamp(data_fim) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    df = repo.fetch_itens_periodo(ini, fim)
    if df.empty:
        return df
    for c in ("QUANTIDADE", "TOTALRATEADO", "DESCONTO", "PRECOCUSTO"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["LUCRO_BRUTO"] = df["TOTALRATEADO"] - (df["QUANTIDADE"] * df["PRECOCUSTO"])
    return df


def get_itens_pedido(codempresa: str, tipopedido: str, codpedido: str, codcliente: str) -> pd.DataFrame:
    """Drill-down: itens de um pedido específico (Cliente → Pedido → Itens)."""
    df = repo.fetch_itens_pedido(codempresa, tipopedido, codpedido, codcliente)
    if not df.empty:
        for c in ("QUANTIDADE", "PRECOUNIT", "DESCONTO", "TOTAL"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def get_pedidos_cliente(df_fat: pd.DataFrame, codcliente: str) -> pd.DataFrame:
    """Drill-down: pedidos faturados de um cliente, mais recentes primeiro."""
    if df_fat.empty:
        return df_fat
    return (df_fat[df_fat["CODCLIENTE"] == codcliente]
            .sort_values("DATAFATURA", ascending=False)
            .reset_index(drop=True))


# ── Top clientes / produtos ──────────────────────────────────────────────────

def get_top_clientes_faturamento(df_fat: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Top `top_n` clientes por faturamento total no recorte já filtrado de `df_fat`."""
    if df_fat.empty:
        return pd.DataFrame()
    g = df_fat.groupby(["CODCLIENTE", "NOME_CLIENTE"]).agg(
        Faturamento=("TOTALPEDIDO", "sum"),
        Pedidos=("CODPEDIDO", "count"),
    ).reset_index()
    return g.sort_values("Faturamento", ascending=False).head(top_n)


def get_top_clientes_lucro(df_itens: pd.DataFrame, df_fat: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Top `top_n` clientes por lucro bruto (precisa de `df_itens`, que já traz LUCRO_BRUTO calculado)."""
    if df_itens.empty:
        return pd.DataFrame()
    g = df_itens.groupby("CODCLIENTE")["LUCRO_BRUTO"].sum().reset_index()
    g = g.merge(df_fat[["CODCLIENTE", "NOME_CLIENTE"]].drop_duplicates(), on="CODCLIENTE", how="left")
    return g.sort_values("LUCRO_BRUTO", ascending=False).head(top_n)


def get_top_produtos(df_itens: pd.DataFrame, criterio: str = "faturamento", top_n: int = 20) -> pd.DataFrame:
    """Top `top_n` produtos por `criterio` ('faturamento', 'quantidade' ou 'lucro')."""
    if df_itens.empty:
        return pd.DataFrame()
    g = df_itens.groupby(["CODPROD", "PRODUTO"]).agg(
        Quantidade=("QUANTIDADE", "sum"),
        Faturamento=("TOTALRATEADO", "sum"),
        Lucro_Bruto=("LUCRO_BRUTO", "sum"),
    ).reset_index()
    col = {"faturamento": "Faturamento", "quantidade": "Quantidade", "lucro": "Lucro_Bruto"}.get(criterio, "Faturamento")
    return g.sort_values(col, ascending=False).head(top_n)


# ── Clientes sem comprar / com queda de compras ─────────────────────────────

def get_ultima_compra_clientes() -> pd.DataFrame:
    """
    Primeira e última compra de cada cliente (toda a base — não dá para limitar
    por janela, senão um cliente "sumido" há anos não apareceria, nem um cliente
    "novo" seria identificável). Base de "Clientes sem comprar" e "Novos x Recorrentes".
    """
    df = repo.fetch_ultima_compra_clientes()
    if df.empty:
        return df
    df["PRIMEIRA_COMPRA"] = pd.to_datetime(df["PRIMEIRA_COMPRA"])
    df["ULTIMA_COMPRA"] = pd.to_datetime(df["ULTIMA_COMPRA"])
    df["TOTAL_HISTORICO"] = pd.to_numeric(df["TOTAL_HISTORICO"], errors="coerce").fillna(0)
    df["DIAS_SEM_COMPRAR"] = (pd.Timestamp.now().normalize() - df["ULTIMA_COMPRA"]).dt.days
    return df


def get_clientes_novos_recorrentes(df_fat: pd.DataFrame, df_ultima: pd.DataFrame, data_ini) -> dict:
    """
    Classifica os clientes ativos no período filtrado em "novos" (primeira compra
    de toda a história cai dentro do período) vs "recorrentes" (já compravam antes
    do início do período). Indicador clássico de saúde comercial: mostra se o
    crescimento vem de captação de clientes ou de retenção dos existentes.
    """
    vazio = {"novos": 0, "recorrentes": 0, "fat_novos": 0.0, "fat_recorrentes": 0.0,
             "dados": pd.DataFrame()}
    if df_fat.empty or df_ultima.empty or "PRIMEIRA_COMPRA" not in df_ultima.columns:
        return vazio

    corte = pd.Timestamp(data_ini)
    primeira = df_ultima.set_index("CODCLIENTE")["PRIMEIRA_COMPRA"]
    clientes_periodo = df_fat["CODCLIENTE"].unique()

    novos_ids = [c for c in clientes_periodo if c in primeira.index and primeira[c] >= corte]
    novos_set = set(novos_ids)
    recorrentes_ids = [c for c in clientes_periodo if c not in novos_set]

    fat_novos = float(df_fat[df_fat["CODCLIENTE"].isin(novos_set)]["TOTALPEDIDO"].sum())
    fat_recorrentes = float(df_fat[df_fat["CODCLIENTE"].isin(recorrentes_ids)]["TOTALPEDIDO"].sum())

    dados = pd.DataFrame({
        "Categoria":    ["Novos", "Recorrentes"],
        "Clientes":     [len(novos_ids), len(recorrentes_ids)],
        "Faturamento":  [fat_novos, fat_recorrentes],
    })
    return {
        "novos": len(novos_ids),
        "recorrentes": len(recorrentes_ids),
        "fat_novos": fat_novos,
        "fat_recorrentes": fat_recorrentes,
        "dados": dados,
    }


def get_clientes_sem_comprar(df_ultima: pd.DataFrame, dias: int = 30) -> pd.DataFrame:
    """Clientes sem comprar há pelo menos `dias` dias, ordenados do mais inativo para o menos."""
    if df_ultima.empty:
        return pd.DataFrame()
    return (df_ultima[df_ultima["DIAS_SEM_COMPRAR"] >= dias]
            .sort_values("DIAS_SEM_COMPRAR", ascending=False))


def get_clientes_queda_compras(meses_base: int = 6, top_n: int = 10) -> pd.DataFrame:
    """
    Clientes com maior queda: média mensal dos últimos N meses (excluindo o mês
    corrente, que está incompleto) vs total comprado nos últimos 30 dias.
    """
    hoje = pd.Timestamp.now()
    mes_corrente = pd.Timestamp(hoje.year, hoje.month, 1)
    data_ini_hist = mes_corrente - pd.DateOffset(months=meses_base)

    df_mensal = repo.fetch_compras_mensais(data_ini_hist.strftime("%Y-%m-%d"))
    if df_mensal.empty:
        return pd.DataFrame()
    df_mensal["ANO"] = df_mensal["ANO"].astype(int)
    df_mensal["MES"] = df_mensal["MES"].astype(int)
    df_mensal["MES_ANO"] = pd.to_datetime(dict(year=df_mensal["ANO"], month=df_mensal["MES"], day=1))

    historico = df_mensal[df_mensal["MES_ANO"] < mes_corrente]
    if historico.empty:
        return pd.DataFrame()

    media_hist = (historico.groupby(["CODCLIENTE", "NOME_CLIENTE"])["TOTAL"]
                  .mean().reset_index().rename(columns={"TOTAL": "Media_6m"}))

    corte_30d = hoje - pd.Timedelta(days=30)
    df_30d = repo.fetch_compras_30d(corte_30d.strftime("%Y-%m-%d"))
    if df_30d.empty:
        df_30d = pd.DataFrame(columns=["CODCLIENTE", "Ultimos_30d"])
    else:
        df_30d = df_30d.rename(columns={"TOTAL_30D": "Ultimos_30d"})

    g = media_hist.merge(df_30d, on="CODCLIENTE", how="left")
    g["Ultimos_30d"] = pd.to_numeric(g["Ultimos_30d"], errors="coerce").fillna(0)
    g = g[g["Media_6m"] > 0].copy()
    g["Queda_%"] = ((g["Media_6m"] - g["Ultimos_30d"]) / g["Media_6m"] * 100).round(1)
    g["Valor_Perdido"] = (g["Media_6m"] - g["Ultimos_30d"]).clip(lower=0)
    g = g[g["Queda_%"] > 0].sort_values("Queda_%", ascending=False)
    return g.head(top_n)


# ── Concentração de faturamento ──────────────────────────────────────────────

def get_concentracao_clientes(df_fat: pd.DataFrame, top_n: int = 10) -> dict:
    """
    Concentração de faturamento por cliente: tabela ordenada com participação
    e acumulado percentual (base para a curva ABC), mais o % dos top `top_n`.
    """
    if df_fat.empty:
        return {"total": 0.0, "top_perc": 0.0, "n_clientes": 0, "dados": pd.DataFrame()}
    total = float(df_fat["TOTALPEDIDO"].sum())
    g = (df_fat.groupby(["CODCLIENTE", "NOME_CLIENTE"])["TOTALPEDIDO"]
         .sum().sort_values(ascending=False).reset_index())
    participacao = (g["TOTALPEDIDO"] / total * 100) if total else g["TOTALPEDIDO"] * 0.0
    g["Acumulado %"] = participacao.cumsum().round(1)
    g["Participação %"] = participacao.round(1)
    g = g[["CODCLIENTE", "NOME_CLIENTE", "TOTALPEDIDO", "Participação %", "Acumulado %"]]
    g.columns = ["Código", "Cliente", "Valor", "Participação %", "Acumulado %"]
    return {
        "total": total,
        "top_perc": float(g.head(top_n)["Participação %"].sum()),
        "n_clientes": len(g),
        "dados": g,
    }


def get_concentracao_produtos(df_itens: pd.DataFrame, top_n: int = 20) -> dict:
    """
    Concentração de faturamento por produto: tabela ordenada com participação
    e acumulado percentual (base para a curva ABC), mais o % dos top `top_n`.
    """
    if df_itens.empty:
        return {"total": 0.0, "top_perc": 0.0, "n_produtos": 0, "dados": pd.DataFrame()}
    total = float(df_itens["TOTALRATEADO"].sum())
    g = (df_itens.groupby(["CODPROD", "PRODUTO"])["TOTALRATEADO"]
         .sum().sort_values(ascending=False).reset_index())
    participacao = (g["TOTALRATEADO"] / total * 100) if total else g["TOTALRATEADO"] * 0.0
    g["Acumulado %"] = participacao.cumsum().round(1)
    g["Participação %"] = participacao.round(1)
    g = g[["CODPROD", "PRODUTO", "TOTALRATEADO", "Participação %", "Acumulado %"]]
    g.columns = ["Código", "Produto", "Valor", "Participação %", "Acumulado %"]
    return {
        "total": total,
        "top_perc": float(g.head(top_n)["Participação %"].sum()),
        "n_produtos": len(g),
        "dados": g,
    }


def classifica_curva_abc(df_concentracao: pd.DataFrame) -> pd.DataFrame:
    """
    Classifica clientes/produtos em curva ABC pela regra clássica de Pareto
    (80/95) sobre o valor — ver core.domain.classificacao.curva_abc (regra
    compartilhada com a curva ABC de estoque). Recebe o DataFrame de
    get_concentracao_clientes/produtos (já com coluna "Valor") e devolve com
    a coluna "Classe" adicionada.
    """
    if df_concentracao.empty or "Valor" not in df_concentracao.columns:
        return df_concentracao
    return _curva_abc(df_concentracao, col_valor="Valor", col_classe="Classe")


def resumo_curva_abc(df_classificado: pd.DataFrame) -> pd.DataFrame:
    """Resumo da curva ABC: nº de itens e % do valor total por classe (A/B/C)."""
    if df_classificado.empty or "Classe" not in df_classificado.columns:
        return pd.DataFrame()
    total = float(df_classificado["Valor"].sum())
    g = (df_classificado.groupby("Classe")
         .agg(Itens=("Classe", "size"), Valor=("Valor", "sum"))
         .reindex(["A", "B", "C"]).fillna(0).reset_index())
    g["Itens"] = g["Itens"].astype(int)
    g["% do Valor"] = (g["Valor"] / total * 100).round(1) if total else 0.0
    return g


# ── Sazonalidade ─────────────────────────────────────────────────────────────

def get_sazonalidade(meses: int = 24) -> pd.DataFrame:
    """
    Série mensal de faturamento dos últimos N meses.
    "Compras" e "margem bruta" (pedidos pelo cliente) ficam para quando o módulo
    Compras existir — ver nota em docs/MODULO_COMERCIAL.md.
    """
    data_ini = pd.Timestamp.now() - pd.DateOffset(months=meses)
    df = repo.fetch_sazonalidade(data_ini.strftime("%Y-%m-%d"))
    if df.empty:
        return df
    df["ANO"] = df["ANO"].astype(int)
    df["MES"] = df["MES"].astype(int)
    df["FATURAMENTO"] = pd.to_numeric(df["FATURAMENTO"], errors="coerce").fillna(0)
    df["MES_ANO"] = df.apply(lambda r: f"{int(r['MES']):02d}/{int(r['ANO'])}", axis=1)
    return df


def get_faturamento_por_forma_pgto(df_fat: pd.DataFrame) -> pd.DataFrame:
    """
    Faturamento por forma de pagamento, no mesmo período/filtro de `df_fat`
    (saída de get_faturamento(), já filtrada por período/empresa/vendedor/etc.
    na página). PEDIDOC não guarda forma de pagamento — o valor real está nas
    liquidações (MOVIREC), ligadas ao pedido via DOCUREC.NUMDOCORIG (NF ou AV).

    Quando um pedido foi liquidado em mais de uma forma (pagamento dividido),
    o faturamento desse pedido é RATEADO proporcionalmente ao peso de cada
    forma nas liquidações reais — em vez de atribuído inteiro à forma
    predominante. Pedidos sem nenhuma liquidação localizada (ex.: título tipo
    CO/convênio, sem ligação direta com um pedido) não entram no rateio.

    Retorna colunas: CODFORMAPGTO, VALOR_RATEADO, PCT.
    """
    if df_fat.empty:
        return pd.DataFrame(columns=["CODFORMAPGTO", "VALOR_RATEADO", "PCT"])

    liquid = repo.fetch_liquidacoes_nf_av()
    if liquid.empty:
        return pd.DataFrame(columns=["CODFORMAPGTO", "VALOR_RATEADO", "PCT"])

    from core.domain.financeiro import numdocorig_to_numnf

    def _decodifica(row) -> tuple[str, str] | None:
        """Decodifica NUMDOCORIG em (CODPEDIDO, TIPOPEDIDO) — AV é direto; NF passa pelo mapa NFSAIDC."""
        s = str(row["NUMDOCORIG"] or "").strip()
        if row["TIPODOCTO"] == "AV":
            if len(s) < 3:
                return None
            return s[2:], s[:2]
        # TIPODOCTO == 'NF'
        numnf = numdocorig_to_numnf(s)
        if numnf is None:
            return None
        achado = mapa_nf[(mapa_nf["CODEMPRESA"] == row["CODEMPRESA"]) & (mapa_nf["NUMNF"] == numnf)]
        if achado.empty:
            return None
        r = achado.iloc[0]
        return r["CODPEDIDO"], r["TIPOPEDIDO"]

    mapa_nf = repo.fetch_nf_pedido_map()
    decodificado = liquid.apply(_decodifica, axis=1)
    liquid = liquid[decodificado.notna()].copy()
    liquid["CODPEDIDO"], liquid["TIPOPEDIDO"] = zip(*decodificado[decodificado.notna()])

    pedidos = df_fat[["CODEMPRESA", "CODPEDIDO", "TIPOPEDIDO", "TOTALPEDIDO"]].drop_duplicates()
    merged = liquid.merge(pedidos, on=["CODEMPRESA", "CODPEDIDO", "TIPOPEDIDO"], how="inner")
    if merged.empty:
        return pd.DataFrame(columns=["CODFORMAPGTO", "VALOR_RATEADO", "PCT"])

    total_liquidado_pedido = merged.groupby(["CODEMPRESA", "CODPEDIDO", "TIPOPEDIDO"])["VALOR_LIQUIDADO"].transform("sum")
    merged["VALOR_RATEADO"] = merged["VALOR_LIQUIDADO"] / total_liquidado_pedido * merged["TOTALPEDIDO"]

    resultado = merged.groupby("CODFORMAPGTO")["VALOR_RATEADO"].sum().reset_index()
    total = resultado["VALOR_RATEADO"].sum()
    resultado["PCT"] = (resultado["VALOR_RATEADO"] / total * 100) if total > 0 else 0
    return resultado.sort_values("VALOR_RATEADO", ascending=False).reset_index(drop=True)


# ── Classificação auxiliar (UI) ───────────────────────────────────────────────

def classifica_faixa_sem_comprar(dias: float) -> str:
    """Classifica um cliente pelos dias desde a última compra em uma faixa textual, para exibição em gráfico/tabela."""
    if dias < 30:
        return "Comprou nos últimos 30 dias"
    if dias < 60:
        return "30-60 dias"
    if dias < 90:
        return "60-90 dias"
    if dias < 180:
        return "90-180 dias"
    return "+180 dias"
