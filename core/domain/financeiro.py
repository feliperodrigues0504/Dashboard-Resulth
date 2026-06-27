"""
Regras de negócio do módulo financeiro: KPIs, faixas de atraso, comparativos,
projeção de caixa, PMR/PMP e alertas. Não faz SQL direto — todo acesso ao
Firebird passa por core.data.repositories.financeiro_repo.
"""
import numpy as np
import pandas as pd
from datetime import datetime
from core.data.repositories import financeiro_repo as repo


def get_contas_receber() -> pd.DataFrame:
    """Contas a Receber em aberto, com DIAS_ATRASO e FAIXA (classificação de atraso) calculados."""
    df = repo.fetch_contas_receber()
    if df.empty:
        return df
    hoje = datetime.now()
    df['DIAS_ATRASO'] = (hoje - df['DT_VENCIMENTO']).dt.days
    df['FAIXA'] = df['DIAS_ATRASO'].apply(_classifica_faixa_ar)
    return df


def get_contas_pagar() -> pd.DataFrame:
    """Contas a Pagar em aberto, com DIAS_ATE_VEN e FAIXA (classificação de prazo) calculados."""
    df = repo.fetch_contas_pagar()
    if df.empty:
        return df
    hoje = datetime.now()
    df['DIAS_ATE_VEN'] = (df['DT_VENCIMENTO'] - hoje).dt.days
    df['FAIXA'] = df['DIAS_ATE_VEN'].apply(_classifica_faixa_ap)
    return df


def get_estoque_custo() -> dict:
    """Valor do estoque da matriz a custo e a venda — ver core.data.repositories.financeiro_repo.fetch_estoque_custo."""
    return repo.fetch_estoque_custo()


def get_saldo_bancario() -> pd.DataFrame:
    """Saldo mais recente de cada conta bancária."""
    return repo.fetch_saldo_bancario()


def get_evolucao_saldo() -> pd.DataFrame:
    """Histórico de saldo de estoque (SALDOST) ordenado por data."""
    return repo.fetch_evolucao_saldo()


# ── KPIs consolidados ─────────────────────────────────────────────────────────

def get_kpis(df_ar: pd.DataFrame, df_ap: pd.DataFrame,
             estoque: dict, df_bco: pd.DataFrame) -> dict:
    """
    Consolida os KPIs executivos do Financeiro a partir dos DataFrames/dict já
    carregados (AR, AP, estoque a custo, saldo bancário). Não consulta o banco.
    Capital operacional = saldo bancário + AR total + estoque a custo - AP total.
    """
    total_ar       = float(df_ar['SALDO_ABERTO'].sum()) if not df_ar.empty else 0
    vencido        = float(df_ar.loc[df_ar['DIAS_ATRASO'] > 0, 'SALDO_ABERTO'].sum()) if not df_ar.empty else 0
    a_vencer_ar    = total_ar - vencido
    total_ap       = float(df_ap['SALDO_ABERTO'].sum()) if not df_ap.empty else 0
    vencido_ap     = float(df_ap.loc[df_ap['DIAS_ATE_VEN'] < 0, 'SALDO_ABERTO'].sum()) if not df_ap.empty else 0
    saldo_bco      = float(df_bco['SALDO'].sum()) if not df_bco.empty else 0
    capital_op     = saldo_bco + total_ar + estoque['custo'] - total_ap
    return {
        'total_ar':    total_ar,
        'vencido_ar':  vencido,
        'a_vencer_ar': a_vencer_ar,
        'total_ap':    total_ap,
        'vencido_ap':  vencido_ap,
        'saldo_bco':   saldo_bco,
        'estoque_custo': estoque['custo'],
        'capital_op':  capital_op,
    }


# ── Aging (Contas a Receber por faixa) ───────────────────────────────────────

def aging_por_cliente(df_ar: pd.DataFrame) -> pd.DataFrame:
    """Top 20 clientes com saldo vencido, pivotado por FAIXA de atraso (uma coluna por faixa) e ordenado por TOTAL."""
    if df_ar.empty:
        return pd.DataFrame()
    vencido = df_ar[df_ar['DIAS_ATRASO'] > 0].copy()
    pivot = vencido.pivot_table(
        index='NOME_CLIENTE',
        columns='FAIXA',
        values='SALDO_ABERTO',
        aggfunc='sum',
        fill_value=0,
    ).reset_index()
    pivot['TOTAL'] = pivot.drop(columns='NOME_CLIENTE').sum(axis=1)
    return pivot.sort_values('TOTAL', ascending=False).head(20)


def aging_totais(df_ar: pd.DataFrame) -> pd.Series:
    """Total vencido por FAIXA de atraso (Série indexada pela faixa)."""
    if df_ar.empty:
        return pd.Series(dtype=float)
    vencido = df_ar[df_ar['DIAS_ATRASO'] > 0]
    return vencido.groupby('FAIXA')['SALDO_ABERTO'].sum()


# ── Fluxo de caixa projetado ──────────────────────────────────────────────────

HORIZONTES = [7, 15, 30, 60, 90]


def fluxo_projetado(df_ar: pd.DataFrame, df_ap: pd.DataFrame) -> pd.DataFrame:
    """AR, AP e saldo líquido acumulados até cada horizonte em HORIZONTES (7/15/30/60/90 dias)."""
    hoje = datetime.now()
    rows = []
    for h in HORIZONTES:
        limite = hoje + pd.Timedelta(days=h)
        ar = float(df_ar.loc[df_ar['DT_VENCIMENTO'] <= limite, 'SALDO_ABERTO'].sum()) if not df_ar.empty else 0
        ap = float(df_ap.loc[df_ap['DT_VENCIMENTO'] <= limite, 'SALDO_ABERTO'].sum()) if not df_ap.empty else 0
        rows.append({'Horizonte': f'{h} dias', 'A Receber': ar, 'A Pagar': ap, 'Líquido': ar - ap})
    return pd.DataFrame(rows)


def ap_por_fornecedor(df_ap: pd.DataFrame) -> pd.DataFrame:
    """Saldo em aberto de AP agrupado por fornecedor, ordenado do maior para o menor."""
    if df_ap.empty:
        return pd.DataFrame()
    return (
        df_ap.groupby('NOME_FORNECEDOR')['SALDO_ABERTO']
        .sum()
        .reset_index()
        .sort_values('SALDO_ABERTO', ascending=False)
        .rename(columns={'NOME_FORNECEDOR': 'Fornecedor', 'SALDO_ABERTO': 'Total'})
    )


# ── Comparativos históricos ───────────────────────────────────────────────────

def get_comparativo_recebimentos(meses_atras: int = 13) -> pd.DataFrame:
    """Recebimentos liquidados por mês nos últimos N meses."""
    data_ini = pd.Timestamp.now() - pd.DateOffset(months=meses_atras)
    df = repo.fetch_recebimentos_mes(data_ini.strftime("%Y-%m-%d"))
    if df.empty:
        return df
    df["ANO"] = df["ANO"].astype(int)
    df["MES"]  = df["MES"].astype(int)
    df["MES_ANO"] = df.apply(lambda r: f"{int(r['MES']):02d}/{int(r['ANO'])}", axis=1)
    return df


def get_comparativo_pagamentos(meses_atras: int = 13) -> pd.DataFrame:
    """Pagamentos liquidados por mês nos últimos N meses."""
    data_ini = pd.Timestamp.now() - pd.DateOffset(months=meses_atras)
    df = repo.fetch_pagamentos_mes(data_ini.strftime("%Y-%m-%d"))
    if df.empty:
        return df
    df["ANO"] = df["ANO"].astype(int)
    df["MES"]  = df["MES"].astype(int)
    df["MES_ANO"] = df.apply(lambda r: f"{int(r['MES']):02d}/{int(r['ANO'])}", axis=1)
    return df


def get_acumulado_ano() -> dict:
    """
    Acumulado do ano corrente vs mesmo período do ano anterior.
    Retorna dict com recebido_ano, recebido_ano_ant, pago_ano, pago_ano_ant.
    """
    hoje = pd.Timestamp.now()
    ano  = hoje.year
    ini_ano       = pd.Timestamp(f"{ano}-01-01")
    ini_ano_ant   = pd.Timestamp(f"{ano-1}-01-01")
    fim_ano_ant   = pd.Timestamp(f"{ano-1}-{hoje.month:02d}-{hoje.day:02d}")

    def _soma_rec(data_ini, data_fim):
        """Soma de recebimentos liquidados entre `data_ini` e `data_fim` (0.0 se não houver dados)."""
        df = repo.fetch_soma_recebimentos_periodo(
            data_ini.strftime("%Y-%m-%d"), data_fim.strftime("%Y-%m-%d"))
        return float(df.iloc[0]["TOTAL"] or 0) if not df.empty else 0.0

    def _soma_pag(data_ini, data_fim):
        """Soma de pagamentos liquidados entre `data_ini` e `data_fim` (0.0 se não houver dados)."""
        df = repo.fetch_soma_pagamentos_periodo(
            data_ini.strftime("%Y-%m-%d"), data_fim.strftime("%Y-%m-%d"))
        return float(df.iloc[0]["TOTAL"] or 0) if not df.empty else 0.0

    return {
        "recebido_ano":     _soma_rec(ini_ano,     hoje),
        "recebido_ano_ant": _soma_rec(ini_ano_ant, fim_ano_ant),
        "pago_ano":         _soma_pag(ini_ano,     hoje),
        "pago_ano_ant":     _soma_pag(ini_ano_ant, fim_ano_ant),
        "ano":              ano,
        "ano_ant":          ano - 1,
    }


def get_evolucao_inadimplencia() -> pd.DataFrame:
    """Inadimplência acumulada por mês de vencimento (títulos ainda em aberto)."""
    hoje = pd.Timestamp.now().strftime("%Y-%m-%d")
    df = repo.fetch_inadimplencia_mes(hoje)
    if df.empty:
        return df
    df["ANO"] = df["ANO"].astype(int)
    df["MES"]  = df["MES"].astype(int)
    df["MES_ANO"] = df.apply(lambda r: f"{int(r['MES']):02d}/{int(r['ANO'])}", axis=1)
    return df


# ── Drill-down: histórico de movimentações de um título ──────────────────────

_TIPOMOV_AR = {
    '01': 'Pagamento AV/CO',
    '02': 'Pagamento parcial NF',
    '04': 'Liquidação',
    '05': 'Liquidação especial',
    '06': 'Outros',
    '07': 'Estorno',
    '08': 'Outros',
}


def get_historico_ar(codempresa: str, tipodocto: str,
                     coddocto: str, codcliente: str) -> pd.DataFrame:
    """Histórico de movimentações de um título AR, com a descrição do tipo de movimento (DESCRICAO) traduzida."""
    df = repo.fetch_historico_ar(codempresa, tipodocto, coddocto, codcliente)
    if not df.empty:
        df['DESCRICAO'] = df['TIPOMOV'].map(_TIPOMOV_AR).fillna(df['TIPOMOV'])
    return df


def get_historico_ap(codempresa: str, tipodocto: str,
                     coddocto: str, codfornec: str) -> pd.DataFrame:
    """Histórico de movimentações de um título AP."""
    return repo.fetch_historico_ap(codempresa, tipodocto, coddocto, codfornec)


# ── Drill-down: fluxo por dia ─────────────────────────────────────────────────

def get_fluxo_diario(df_ar: pd.DataFrame, df_ap: pd.DataFrame,
                     horizonte_dias: int) -> pd.DataFrame:
    """AR e AP agrupados por dia de vencimento dentro do horizonte."""
    hoje = pd.Timestamp.now().normalize()
    limite = hoje + pd.Timedelta(days=horizonte_dias)

    ar_filt = df_ar[df_ar['DT_VENCIMENTO'] <= limite].copy() if not df_ar.empty else pd.DataFrame()
    ap_filt = df_ap[df_ap['DT_VENCIMENTO'] <= limite].copy() if not df_ap.empty else pd.DataFrame()

    def _agg(df, col_nome):
        """Soma SALDO_ABERTO por dia de vencimento, renomeando a coluna de valor para `col_nome`."""
        if df.empty:
            return pd.DataFrame(columns=['Data', col_nome])
        g = df.groupby(df['DT_VENCIMENTO'].dt.normalize())['SALDO_ABERTO'].sum().reset_index()
        g.columns = ['Data', col_nome]
        return g

    ar_dia = _agg(ar_filt, 'A Receber')
    ap_dia = _agg(ap_filt, 'A Pagar')

    merged = pd.merge(ar_dia, ap_dia, on='Data', how='outer').fillna(0)
    merged['Líquido'] = merged['A Receber'] - merged['A Pagar']
    return merged.sort_values('Data').reset_index(drop=True)


def get_titulos_do_dia(df_ar: pd.DataFrame, df_ap: pd.DataFrame,
                       data_referencia: pd.Timestamp):
    """Retorna os títulos AR e AP com vencimento em uma data específica."""
    dia = pd.Timestamp(data_referencia).normalize()
    ar = df_ar[df_ar['DT_VENCIMENTO'].dt.normalize() == dia].copy() if not df_ar.empty else pd.DataFrame()
    ap = df_ap[df_ap['DT_VENCIMENTO'].dt.normalize() == dia].copy() if not df_ap.empty else pd.DataFrame()
    return ar, ap


# ── Drill-down: itens de NF/pedido AV vinculados ao título ───────────────────

def numdocorig_to_numnf(numdocorig: str) -> int | None:
    """
    Converte NUMDOCORIG para o inteiro NUMNF.
    Formato: 'VP' + NUMNF(8 dígitos zero-padded) + '01'
    Ex: 'VP0001047201' → 10472
    """
    try:
        s = str(numdocorig).strip()
        if s.startswith("VP") and len(s) >= 10:
            return int(s[2:10])     # posições 2-9 = NUMNF com zeros
        return None
    except Exception:
        return None


def get_itens_nf(codempresa: str, tipodocto: str, numdocorig: str) -> pd.DataFrame:
    """
    Retorna os itens de produto da NF vinculada ao título AR.
    Link descoberto: DOCUREC.NUMDOCORIG = 'VP' + NUMNF(8 dígitos) + '01'
    Ex: NUMDOCORIG='VP0001047201' → NUMNF 10472 → itens em NFSAIDI
    Só funciona para TIPODOCTO = 'NF'.
    """
    if tipodocto.strip().upper() != "NF":
        return pd.DataFrame()
    numnf = numdocorig_to_numnf(numdocorig)
    if numnf is None:
        return pd.DataFrame()
    return repo.fetch_itens_nf(codempresa, numnf)


def get_itens_av(codempresa: str, numdocorig: str) -> pd.DataFrame:
    """
    Itens de produto de um título AV.
    NUMDOCORIG = TIPOPEDIDO(2 chars) + CODPEDIDO(resto).
    Ex: '5500000001' → TIPOPEDIDO='55', CODPEDIDO='00000001'.
    """
    s = str(numdocorig or "").strip()
    if len(s) < 3:
        return pd.DataFrame()
    tipopedido = s[:2]
    codpedido  = s[2:]
    return repo.fetch_itens_pedido_av(codempresa, tipopedido, codpedido)


# ── Projeção de caixa acumulada (running balance) ─────────────────────────────

def get_projecao_acumulada(df_ar: pd.DataFrame, df_ap: pd.DataFrame,
                            saldo_inicial: float, dias: int = 90) -> pd.DataFrame:
    """
    Calcula o saldo de caixa projetado dia a dia.
    Começa do saldo bancário atual e soma AR - AP a cada dia de vencimento.
    """
    hoje  = pd.Timestamp.now().normalize()
    datas = pd.date_range(hoje, hoje + pd.Timedelta(days=dias - 1), freq="D")

    ar_future = df_ar[df_ar["DT_VENCIMENTO"] >= hoje] if not df_ar.empty else pd.DataFrame()
    ap_future = df_ap[df_ap["DT_VENCIMENTO"] >= hoje] if not df_ap.empty else pd.DataFrame()

    def _por_dia(df, col):
        """Soma a coluna `col` por dia de vencimento, como dict {data: valor} para lookup O(1) no loop abaixo."""
        if df.empty:
            return {}
        return df.groupby(df["DT_VENCIMENTO"].dt.normalize())[col].sum().to_dict()

    ar_dia = _por_dia(ar_future, "SALDO_ABERTO")
    ap_dia = _por_dia(ap_future, "SALDO_ABERTO")

    rows  = []
    saldo = saldo_inicial
    for data in datas:
        entrada = float(ar_dia.get(data, 0))
        saida   = float(ap_dia.get(data, 0))
        saldo  += entrada - saida
        rows.append({
            "Data":    data,
            "Entradas": entrada,
            "Saídas":  saida,
            "Saldo":   saldo,
        })
    return pd.DataFrame(rows)


# ── PMR e PMP ─────────────────────────────────────────────────────────────────

def get_pmr_pmp(dias_janela: int = 90) -> dict:
    """
    PMR — Prazo Médio de Recebimento: média dos dias entre vencimento e liquidação (AR).
    PMP — Prazo Médio de Pagamento:   média dos dias entre vencimento e liquidação (AP).
    Janela: últimos N dias de liquidações.
    """
    data_corte = (pd.Timestamp.now() - pd.Timedelta(days=dias_janela)).strftime("%Y-%m-%d")

    pmr_pmp = {"pmr": None, "pmp": None,
              "pmr_ant": None, "pmp_ant": None,
              "janela": dias_janela}
    try:
        df_ar = repo.fetch_liquidacoes_ar(data_corte)
        if not df_ar.empty:
            df_ar["DT_VENCIMENTO"] = pd.to_datetime(df_ar["DT_VENCIMENTO"])
            df_ar["DT_MOVIMENTO"]  = pd.to_datetime(df_ar["DT_MOVIMENTO"])
            df_ar["DIAS"] = (df_ar["DT_MOVIMENTO"] - df_ar["DT_VENCIMENTO"]).dt.days
            pmr_pmp["pmr"] = round(float(df_ar["DIAS"].mean()), 1)

            # Comparativo: primeira metade da janela (mês anterior aprox.)
            meio = pd.Timestamp.now() - pd.Timedelta(days=dias_janela // 2)
            df_ant = df_ar[df_ar["DT_MOVIMENTO"] < meio]
            pmr_pmp["pmr_ant"] = round(float(df_ant["DIAS"].mean()), 1) if not df_ant.empty else None
    except Exception:
        pass

    try:
        df_ap = repo.fetch_liquidacoes_ap(data_corte)
        if not df_ap.empty:
            df_ap["DT_VENCIMENTO"] = pd.to_datetime(df_ap["DT_VENCIMENTO"])
            df_ap["DT_MOVIMENTO"]  = pd.to_datetime(df_ap["DT_MOVIMENTO"])
            df_ap["DIAS"] = (df_ap["DT_MOVIMENTO"] - df_ap["DT_VENCIMENTO"]).dt.days
            pmr_pmp["pmp"] = round(float(df_ap["DIAS"].mean()), 1)

            meio = pd.Timestamp.now() - pd.Timedelta(days=dias_janela // 2)
            df_ant = df_ap[df_ap["DT_MOVIMENTO"] < meio]
            pmr_pmp["pmp_ant"] = round(float(df_ant["DIAS"].mean()), 1) if not df_ant.empty else None
    except Exception:
        pass

    return pmr_pmp


# ── Concentração de inadimplência ─────────────────────────────────────────────

def get_concentracao_inadimplencia(df_ar: pd.DataFrame) -> dict:
    """
    Retorna a concentração do total vencido nos top N clientes.
    Quanto maior, mais o risco de inadimplência está concentrado em poucos clientes.
    """
    if df_ar.empty:
        return {"total": 0, "dados": pd.DataFrame()}

    vencidos = df_ar[df_ar["DIAS_ATRASO"] > 0]
    if vencidos.empty:
        return {"total": 0, "dados": pd.DataFrame()}

    total = float(vencidos["SALDO_ABERTO"].sum())
    por_cliente = (
        vencidos.groupby("NOME_CLIENTE")["SALDO_ABERTO"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    por_cliente["Participação %"] = (por_cliente["SALDO_ABERTO"] / total * 100).round(1)
    por_cliente["Acumulado %"]    = por_cliente["Participação %"].cumsum().round(1)
    por_cliente.columns = ["Cliente", "Valor", "Participação %", "Acumulado %"]

    top3_perc = float(por_cliente.head(3)["Participação %"].sum())
    top5_perc = float(por_cliente.head(5)["Participação %"].sum())

    return {
        "total":     total,
        "top3_perc": round(top3_perc, 1),
        "top5_perc": round(top5_perc, 1),
        "n_clientes": len(por_cliente),
        "dados":     por_cliente,
    }


# ── Alertas inteligentes ──────────────────────────────────────────────────────
# Nota: existe um segundo motor de alertas em core/domain/alertas.py
# (usado pela Central de Alertas). Mantido aqui por ora — unificação prevista
# nesta mesma rodada de reestruturação para eliminar a duplicação de regra.

def get_alertas_financeiro(df_ar: pd.DataFrame, df_ap: pd.DataFrame,
                            kpis: dict, piso_caixa: float = 50_000,
                            horas_ap: int = 48,
                            dias_critico: int = 90,
                            capital_minimo: float = 100_000) -> list[dict]:
    """
    Verifica condições de alerta e retorna lista de alertas ativos.
    Cada alerta: {'nivel': 'critico'|'urgente'|'atencao', 'titulo': str,
                  'detalhe': str, 'aba': str}
    """
    alertas = []
    hoje = pd.Timestamp.now()

    # 1. Caixa projeta negativo em 7 dias
    try:
        proj = get_projecao_acumulada(df_ar, df_ap, kpis.get("saldo_bco", 0), dias=7)
        saldo_min_7d = float(proj["Saldo"].min())
        if saldo_min_7d < 0:
            alertas.append({
                "nivel":  "critico",
                "titulo": "Caixa negativo projetado",
                "detalhe": f"Saldo projetado cai para R$ {saldo_min_7d:,.0f} nos próximos 7 dias",
                "aba":    "fluxo",
            })
        elif saldo_min_7d < piso_caixa:
            alertas.append({
                "nivel":  "urgente",
                "titulo": "Caixa abaixo do piso mínimo",
                "detalhe": f"Saldo mínimo projetado: R$ {saldo_min_7d:,.0f} (piso: R$ {piso_caixa:,.0f})",
                "aba":    "fluxo",
            })
    except Exception:
        pass

    # 2a. AP já vencidos em aberto (crítico — distinto de "vencendo em breve")
    if not df_ap.empty:
        ja_vencidos = df_ap[df_ap["DT_VENCIMENTO"] < hoje]
        if not ja_vencidos.empty:
            total_venc = float(ja_vencidos["SALDO_ABERTO"].sum())
            alertas.append({
                "nivel":  "critico",
                "titulo": f"{len(ja_vencidos)} título(s) AP já vencidos e em aberto",
                "detalhe": f"Total vencido a pagar: R$ {total_venc:,.2f}",
                "aba":    "ap",
            })

        # 2b. AP vencendo nas próximas N horas (urgente — além dos já vencidos)
        limite_ap = hoje + pd.Timedelta(hours=horas_ap)
        ap_urgente = df_ap[(df_ap["DT_VENCIMENTO"] >= hoje) & (df_ap["DT_VENCIMENTO"] <= limite_ap)]
        if not ap_urgente.empty:
            total_ap_urg = float(ap_urgente["SALDO_ABERTO"].sum())
            alertas.append({
                "nivel":  "urgente",
                "titulo": f"{len(ap_urgente)} título(s) AP vence(m) em {horas_ap}h",
                "detalhe": f"Total: R$ {total_ap_urg:,.2f}",
                "aba":    "ap",
            })

    # 3. Clientes com atraso crítico (> N dias)
    if not df_ar.empty:
        criticos = df_ar[df_ar["DIAS_ATRASO"] > dias_critico]
        if not criticos.empty:
            n_cli = criticos["CODCLIENTE"].nunique()
            valor_atraso = float(criticos["SALDO_ABERTO"].sum())
            alertas.append({
                "nivel":  "critico",
                "titulo": f"{n_cli} cliente(s) com atraso acima de {dias_critico} dias",
                "detalhe": f"Total em atraso crítico: R$ {valor_atraso:,.2f}",
                "aba":    "ar",
            })

    # 4. Capital operacional abaixo do mínimo
    capital = kpis.get("capital_op", 0)
    if capital < capital_minimo:
        nivel = "critico" if capital < 0 else "atencao"
        alertas.append({
            "nivel":  nivel,
            "titulo": "Capital operacional baixo",
            "detalhe": f"Capital atual: R$ {capital:,.2f} (mínimo: R$ {capital_minimo:,.0f})",
            "aba":    "caixa",
        })

    return alertas


# ── Mapa de calor de vencimentos ──────────────────────────────────────────────

def get_heatmap_vencimentos(df_ar: pd.DataFrame, df_ap: pd.DataFrame,
                             semanas: int = 6) -> pd.DataFrame:
    """
    Retorna um DataFrame com colunas: Data, DiaSemana, Semana, AR, AP, Total.
    Usado para montar o calendário/heatmap de vencimentos.
    """
    hoje  = pd.Timestamp.now().normalize()
    fim   = hoje + pd.Timedelta(weeks=semanas)
    datas = pd.date_range(hoje, fim, freq="D")

    def _agg(df, col):
        """Soma a coluna `col` por dia de vencimento dentro da janela [hoje, fim], como dict {data: valor}."""
        if df is None or df.empty:
            return {}
        fut = df[(df["DT_VENCIMENTO"] >= hoje) & (df["DT_VENCIMENTO"] <= fim)]
        return fut.groupby(fut["DT_VENCIMENTO"].dt.normalize())[col].sum().to_dict()

    ar_dia = _agg(df_ar, "SALDO_ABERTO")
    ap_dia = _agg(df_ap, "SALDO_ABERTO")

    rows = []
    for data in datas:
        ar = float(ar_dia.get(data, 0))
        ap = float(ap_dia.get(data, 0))
        rows.append({
            "Data":       data,
            "DiaSemana":  data.day_of_week,      # 0=Seg, 6=Dom
            "Semana":     int((data - hoje).days // 7),
            "AR":         ar,
            "AP":         ap,
            "Total":      ar + ap,
            "Label":      data.strftime("%d/%m"),
        })
    return pd.DataFrame(rows)


def matriz_heatmap(df_heat: pd.DataFrame, col: str, n_semanas: int,
                    formatador_valor=str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Pivota o DataFrame de get_heatmap_vencimentos() em uma matriz 7×n_semanas
    (dia da semana × semana) para uso direto em go.Heatmap.
    `formatador_valor`: função de formatação para os valores no hover
    (ex.: components.metrics.fmt_brl) — injetada para este módulo não
    depender de um helper de apresentação.
    """
    matriz_valores = np.zeros((7, n_semanas))
    labels = np.full((7, n_semanas), "", dtype=object)
    hover  = np.full((7, n_semanas), "", dtype=object)
    for _, row in df_heat.iterrows():
        dia_idx    = int(row["DiaSemana"])
        semana_idx = int(row["Semana"])
        matriz_valores[dia_idx][semana_idx] = row[col]
        labels[dia_idx][semana_idx] = row["Label"]
        hover[dia_idx][semana_idx]  = (f"<b>{row['Label']}</b><br>"
                        f"AR: {formatador_valor(row['AR'])}<br>"
                        f"AP: {formatador_valor(row['AP'])}<br>"
                        f"Total: {formatador_valor(row['Total'])}")
    return matriz_valores, labels, hover


# ── Helpers ───────────────────────────────────────────────────────────────────

def _classifica_faixa_ar(dias: float) -> str:
    """Classifica um título AR pelos dias de atraso em uma faixa textual ('A vencer', '1-30 dias', ..., '+90 dias')."""
    if dias <= 0:
        return 'A vencer'
    if dias <= 30:
        return '1-30 dias'
    if dias <= 60:
        return '31-60 dias'
    if dias <= 90:
        return '61-90 dias'
    return '+90 dias'


def _classifica_faixa_ap(dias_ate_ven: float) -> str:
    """Classifica um título AP pelos dias até o vencimento em uma faixa textual ('+90 dias', ..., '0-7 dias', 'Vencido')."""
    if dias_ate_ven > 90:
        return '+90 dias'
    if dias_ate_ven > 60:
        return '61-90 dias'
    if dias_ate_ven > 30:
        return '31-60 dias'
    if dias_ate_ven > 15:
        return '15-30 dias'
    if dias_ate_ven > 7:
        return '8-15 dias'
    if dias_ate_ven >= 0:
        return '0-7 dias'
    return 'Vencido'
