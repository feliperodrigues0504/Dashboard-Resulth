"""
core/domain/alertas.py — Motor centralizado de alertas
Agrega sinais dos módulos Financeiro, Comercial, Estoque e Compras.
Retorna lista padronizada de alertas para a página 05_Alertas.py.

As 5 regras centrais do Financeiro (caixa projetado, capital operacional, AP
vencido/a vencer, AR crítico) reaproveitam core.domain.financeiro.get_alertas_financeiro()
— o mesmo motor usado no painel rápido da própria página Financeiro — em vez
de reimplementar a regra aqui. Isso evita a divergência que já causou um bug
nesta base (um motor agrupava "AP vencido" e "AP vencendo em 48h" no mesmo
alerta, o outro não). As regras adicionais (% AR vencido, saldo desatualizado,
PMR elevado) só existem nesta central, que olha o financeiro de forma mais
ampla do que o painel rápido.

Formato de cada alerta:
{
    'nivel':   'critico' | 'urgente' | 'atencao',
    'modulo':  'Financeiro' | 'Comercial' | 'Estoque' | 'Compras',
    'icone':   str (Bootstrap Icons key),
    'titulo':  str,
    'detalhe': str,
    'valor':   float | None,   # valor monetário associado (opcional)
    'pagina':  str,            # path da página destino (ex: "Financeiro")
}
"""
from __future__ import annotations

import pandas as pd

# ── importações dos módulos core ──────────────────────────────────────────────
from core.domain.financeiro import (
    get_contas_receber, get_contas_pagar, get_saldo_bancario,
    get_kpis, get_estoque_custo, get_pmr_pmp,
    get_alertas_financeiro as _regras_centrais_financeiro,
)
from core.domain.comercial import (
    get_faturamento, get_ultima_compra_clientes,
    get_clientes_sem_comprar, get_clientes_queda_compras,
    get_concentracao_clientes,
)
from core.domain.estoque import (
    get_estoque_geral, get_ultima_venda,
    get_estoque_parado, get_controle_operacional,
    get_produtos_sem_venda,
)
from core.domain.compras import (
    get_compras_por_fornecedor, get_produtos_sem_giro,
    get_estoque_parado_por_fornecedor,
)

# ── thresholds configuráveis ──────────────────────────────────────────────────
CFG = {
    # Financeiro
    "piso_caixa":          50_000,
    "capital_minimo":      100_000,
    "ap_horas_urgente":    48,
    "ar_dias_critico":     90,
    "ar_vencido_pct":      80,   # % de AR vencido que aciona alerta
    "pmr_atencao":         30,
    "saldo_defasagem_dias": 3,
    # Comercial
    "clientes_sem_comprar_dias":  60,
    "clientes_queda_pct":         40,
    "concentracao_top3_pct":      60,
    # Estoque
    "parado_dias":                90,
    "parado_valor_min":           20_000,   # só alerta se valor total > R$ 20k
    "sem_venda_dias":             90,
    "sem_venda_valor_min":        10_000,
    # Compras
    "dep_fornec_top1_pct":        30,
    "dep_fornec_top3_pct":        60,
    "sem_giro_valor_min":         50_000,
    "parado_forn_valor_min":      20_000,
}

# Ícone por "aba" (formato do painel rápido do Financeiro) — usado só para
# exibição na Central de Alertas; a regra de negócio em si vem de
# get_alertas_financeiro().
_ICONE_POR_ABA = {
    "fluxo": "cash",
    "ap":    "calendar-x",
    "ar":    "person-x",
    "caixa": "bank",
}


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS INTERNOS
# ══════════════════════════════════════════════════════════════════════════════
def _a(nivel: str, modulo: str, icone: str, titulo: str, detalhe: str,
       valor: float | None = None, pagina: str = "") -> dict:
    """Monta um dict de alerta no formato padrão da Central de Alertas (ver docstring do módulo)."""
    return dict(nivel=nivel, modulo=modulo, icone=icone,
                titulo=titulo, detalhe=detalhe, valor=valor, pagina=pagina)


def _fmt(v: float) -> str:
    """Formata um número como moeda brasileira (R$ 1.234,56)."""
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ══════════════════════════════════════════════════════════════════════════════
#  ALERTAS POR MÓDULO
# ══════════════════════════════════════════════════════════════════════════════

def alertas_financeiro(piso_caixa: float | None = None, capital_minimo: float | None = None,
                       ap_horas_urgente: int | None = None, ar_dias_critico: int | None = None
                       ) -> list[dict]:
    """
    Thresholds opcionais — quando omitidos, usa os defaults de CFG (caso da
    Central de Alertas); a página Financeiro passa seus próprios valores
    configurados pelo usuário (aba Config).
    """
    piso_caixa       = CFG["piso_caixa"]       if piso_caixa       is None else piso_caixa
    capital_minimo   = CFG["capital_minimo"]   if capital_minimo   is None else capital_minimo
    ap_horas_urgente = CFG["ap_horas_urgente"] if ap_horas_urgente is None else ap_horas_urgente
    ar_dias_critico  = CFG["ar_dias_critico"]  if ar_dias_critico  is None else ar_dias_critico

    alertas: list[dict] = []
    try:
        df_ar   = get_contas_receber()
        df_ap   = get_contas_pagar()
        df_bco  = get_saldo_bancario()
        estoque = get_estoque_custo()
        kpis    = get_kpis(df_ar, df_ap, estoque, df_bco)
        hoje    = pd.Timestamp.now()

        # 1-4. Regras centrais (caixa projetado, capital, AP vencido/48h, AR
        # crítico) — compartilhadas com o painel rápido da página Financeiro.
        for alerta in _regras_centrais_financeiro(
                df_ar, df_ap, kpis, piso_caixa, ap_horas_urgente,
                ar_dias_critico, capital_minimo):
            alertas.append(_a(
                alerta["nivel"], "Financeiro",
                _ICONE_POR_ABA.get(alerta["aba"], "exclamation-circle"),
                alerta["titulo"], alerta["detalhe"], None, "Financeiro"))

        # 5. % de AR vencido muito alto (só nesta central)
        if not df_ar.empty:
            total_ar = float(df_ar["SALDO_ABERTO"].sum())
            vencido  = float(df_ar[df_ar["DIAS_ATRASO"] > 0]["SALDO_ABERTO"].sum())
            if total_ar > 0:
                pct_vencido = vencido / total_ar * 100
                if pct_vencido >= CFG["ar_vencido_pct"]:
                    alertas.append(_a(
                        "urgente", "Financeiro", "exclamation-triangle",
                        f"{pct_vencido:.0f}% do AR está vencido",
                        f"Vencido: {_fmt(vencido)} de {_fmt(total_ar)} total a receber",
                        vencido, "Financeiro"))

        # 6. Saldo bancário desatualizado (só nesta central)
        if not df_bco.empty:
            dt_bco = pd.to_datetime(df_bco["DATA_MOV"].iloc[0])
            dias_def = (hoje - dt_bco).days
            if dias_def > CFG["saldo_defasagem_dias"]:
                alertas.append(_a(
                    "atencao", "Financeiro", "clock-history",
                    f"Saldo bancário desatualizado — {dias_def} dias sem registro",
                    f"Último registro MOVIBAN: {dt_bco.strftime('%d/%m/%Y')}",
                    None, "Financeiro"))

        # 7. PMR elevado (só nesta central)
        try:
            pmr_data = get_pmr_pmp()
            pmr = pmr_data.get("pmr", 0)
            if pmr > CFG["pmr_atencao"]:
                nivel = "urgente" if pmr > 45 else "atencao"
                alertas.append(_a(
                    nivel, "Financeiro", "hourglass-split",
                    f"PMR elevado — clientes pagando {pmr:.0f} dias após vencimento",
                    "Risco de inadimplência crescente. Verificar política de cobrança.",
                    None, "Financeiro"))
        except Exception:
            pass

    except Exception:
        pass

    return alertas


def alertas_comercial() -> list[dict]:
    """Alertas do módulo Comercial: clientes inativos, queda de compras e concentração de faturamento (ver CFG para os limiares)."""
    alertas: list[dict] = []
    try:
        df_ult = get_ultima_compra_clientes()

        # 1. Clientes sem comprar há X dias
        sem = get_clientes_sem_comprar(df_ult, CFG["clientes_sem_comprar_dias"])
        if not sem.empty:
            nivel = "urgente" if len(sem) > 10 else "atencao"
            alertas.append(_a(
                nivel, "Comercial", "people",
                f"{len(sem)} cliente(s) sem comprar há >{CFG['clientes_sem_comprar_dias']} dias",
                "Clientes inativos que historicamente compram. Verificar relacionamento.",
                None, "Comercial"))

        # 2. Clientes em queda acentuada
        try:
            queda = get_clientes_queda_compras(meses_base=6, top_n=20)
            if not queda.empty:
                queda_grave = queda[queda["Queda_%"] >= CFG["clientes_queda_pct"]]
                if not queda_grave.empty:
                    val_perdido = float(queda_grave["Valor_Perdido"].sum())
                    alertas.append(_a(
                        "atencao", "Comercial", "graph-down-arrow",
                        f"{len(queda_grave)} cliente(s) com queda ≥{CFG['clientes_queda_pct']}% nas compras",
                        f"Receita perdida estimada no mês: {_fmt(val_perdido)}",
                        val_perdido, "Comercial"))
        except Exception:
            pass

        # 3. Concentração de faturamento
        try:
            hoje = pd.Timestamp.now()
            ini_3m = (hoje - pd.DateOffset(months=3)).strftime("%Y-%m-%d")
            df_fat3 = get_faturamento(meses_historico=4)
            df_fat3 = df_fat3[df_fat3["DATAFATURA"] >= ini_3m] if not df_fat3.empty else df_fat3
            conc = get_concentracao_clientes(df_fat3, top_n=3)
            top3_pct = float(conc.get("top_perc", 0))
            if top3_pct >= CFG["concentracao_top3_pct"]:
                nivel = "urgente" if top3_pct >= 75 else "atencao"
                alertas.append(_a(
                    nivel, "Comercial", "pie-chart",
                    f"Concentração alta: top 3 clientes = {top3_pct:.0f}% do faturamento",
                    "Risco de dependência de poucos clientes. Diversificar carteira.",
                    None, "Comercial"))
        except Exception:
            pass

    except Exception:
        pass

    return alertas


def alertas_estoque() -> list[dict]:
    """Alertas do módulo Estoque: estoque parado, ruptura, abaixo do mínimo e produtos nunca vendidos (ver CFG)."""
    alertas: list[dict] = []
    try:
        df_est  = get_estoque_geral()
        df_uv   = get_ultima_venda()
        ctrl    = get_controle_operacional(df_est)

        # 1. Estoque parado (alto valor)
        parado = get_estoque_parado(CFG["parado_dias"], df_est, df_uv)
        if not parado.empty:
            val_parado = float(parado["VALOR_CUSTO"].sum())
            n_sku = len(parado)
            if val_parado >= CFG["parado_valor_min"]:
                nivel = "urgente" if val_parado > 200_000 else "atencao"
                alertas.append(_a(
                    nivel, "Estoque", "box-seam",
                    f"{n_sku} SKUs parados >{CFG['parado_dias']}d — {_fmt(val_parado)} imobilizados",
                    "Capital imobilizado em produtos sem giro. Avaliar liquidação/promoção.",
                    val_parado, "Estoque"))

        # 2. Ruptura (produtos sem estoque)
        ruptura = ctrl.get("ruptura", pd.DataFrame())
        n_rup = len(ruptura)
        if n_rup > 0:
            # Só alerta se for uma quantidade relevante
            df_com = df_est[df_est["QTD"] > 0]
            total_sku = len(df_est)
            pct_rup = n_rup / total_sku * 100 if total_sku else 0
            # Alerta apenas quando ruptura é atípica (abaixo de 300 SKUs com estoque)
            if len(df_com) < 300:
                alertas.append(_a(
                    "urgente", "Estoque", "exclamation-octagon",
                    f"Ruptura crítica — apenas {len(df_com)} SKUs com estoque",
                    f"{n_rup} produtos sem estoque ({pct_rup:.0f}% do catálogo)",
                    None, "Estoque"))

        # 3. Produtos abaixo do mínimo
        abaixo = ctrl.get("abaixo_minimo", pd.DataFrame())
        if not abaixo.empty:
            alertas.append(_a(
                "atencao", "Estoque", "arrow-down-square",
                f"{len(abaixo)} produto(s) abaixo do estoque mínimo cadastrado",
                f"Deficit total: {abaixo['DEFICIT'].sum():.0f} unidades. Verificar reposição.",
                None, "Estoque"))

        # 4. Produtos sem venda sem estoque (parados com estoque cobertura parado já acima)
        # Não duplicar: get_estoque_parado já cobre produtos com estoque > 0 sem venda.
        # Aqui apenas sinalizamos produtos que nunca tiveram qualquer movimento de saída.
        try:
            nunca = get_produtos_sem_venda(df_est, df_uv)
            if not nunca.empty:
                val_nunca = float(nunca["VALOR_CUSTO"].sum())
                if val_nunca >= CFG["sem_venda_valor_min"]:
                    alertas.append(_a(
                        "atencao", "Estoque", "tag-x",
                        f"{len(nunca)} produto(s) com estoque sem nenhuma venda registrada",
                        f"Capital em estoque sem histórico de saída: {_fmt(val_nunca)}",
                        val_nunca, "Estoque"))
        except Exception:
            pass

    except Exception:
        pass

    return alertas


def alertas_compras(data_ini: str, data_fim: str) -> list[dict]:
    """Alertas do módulo Compras no período: dependência de fornecedor, produtos sem giro e estoque parado por fornecedor (ver CFG)."""
    alertas: list[dict] = []
    try:
        df_forn = get_compras_por_fornecedor(data_ini, data_fim)

        # 1. Dependência de fornecedor — top 1
        if not df_forn.empty:
            top1_pct = float(df_forn["PARTICIPACAO"].iloc[0])
            top3_pct = float(df_forn["PARTICIPACAO"].iloc[:3].sum()) if len(df_forn) >= 3 else top1_pct

            if top1_pct >= CFG["dep_fornec_top1_pct"]:
                nivel = "urgente" if top1_pct >= 40 else "atencao"
                alertas.append(_a(
                    nivel, "Compras", "building",
                    f"Dependência alta: {df_forn['NOME_EXIB'].iloc[0]} = {top1_pct:.0f}% das compras",
                    "Risco operacional. Buscar fornecedores alternativos.",
                    None, "Compras"))

            if top3_pct >= CFG["dep_fornec_top3_pct"]:
                alertas.append(_a(
                    "atencao", "Compras", "diagram-3",
                    f"Top 3 fornecedores concentram {top3_pct:.0f}% das compras",
                    "Avaliar diversificação da cadeia de suprimentos.",
                    None, "Compras"))

        # 2. Produtos comprados sem giro
        try:
            df_sg = get_produtos_sem_giro(data_ini, data_fim)
            if not df_sg.empty:
                val_sg = float(df_sg["VALOR_CUSTO"].sum())
                if val_sg >= CFG["sem_giro_valor_min"]:
                    alertas.append(_a(
                        "atencao", "Compras", "cart-x",
                        f"{len(df_sg)} produto(s) comprados sem venda no período",
                        f"{_fmt(val_sg)} imobilizados em itens sem giro após compra.",
                        val_sg, "Compras"))
        except Exception:
            pass

        # 3. Estoque parado por fornecedor
        try:
            df_ep = get_estoque_parado_por_fornecedor(90)
            if not df_ep.empty:
                val_ep = float(df_ep["VALOR_CUSTO"].sum())
                if val_ep >= CFG["parado_forn_valor_min"]:
                    alertas.append(_a(
                        "atencao", "Compras", "archive",
                        f"Estoque parado >90d por fornecedor: {_fmt(val_ep)} em {len(df_ep)} forn.",
                        "Negociar devolução/troca ou promoção com os fornecedores afetados.",
                        val_ep, "Compras"))
        except Exception:
            pass

    except Exception:
        pass

    return alertas


def alertas_sistema() -> list[dict]:
    """
    Alerta de saúde do próprio app: sinaliza quando o snapshot diário (job
    agendado às 08:00 — ver core/sync/agendador.py) não roda por 2+ dias.
    O job falha silenciosamente (só loga no console do processo), então sem
    isto a única forma de notar seria uma lacuna no gráfico de Histórico.
    """
    alertas: list[dict] = []
    try:
        from core.sync.snapshot import status_snapshot
        status = status_snapshot()
        if status["atrasado"]:
            if status["ultima_data"] is None:
                detalhe = "Nenhum snapshot foi coletado ainda."
            else:
                detalhe = (f"Última coleta: {status['ultima_data'].strftime('%d/%m/%Y')} "
                           f"({status['dias_atraso']} dias atrás). Verifique se o Firebird "
                           f"estava acessível no horário agendado (08:00).")
            alertas.append(_a(
                "atencao", "Sistema", "exclamation-triangle-fill",
                "Snapshot diário atrasado",
                detalhe, None, ""))
    except Exception:
        pass

    return alertas


# ══════════════════════════════════════════════════════════════════════════════
#  FUNÇÃO PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
_ORDEM_NIVEL = {"critico": 0, "urgente": 1, "atencao": 2}


def get_todos_alertas(data_ini: str, data_fim: str) -> list[dict]:
    """
    Coleta alertas de todos os módulos e retorna lista ordenada por severidade.
    """
    alertas = (
        alertas_financeiro()
        + alertas_comercial()
        + alertas_estoque()
        + alertas_compras(data_ini, data_fim)
        + alertas_sistema()
    )
    return sorted(alertas, key=lambda a: _ORDEM_NIVEL.get(a["nivel"], 9))


def resumo_alertas(alertas: list[dict]) -> dict:
    """Conta alertas por nível e por módulo."""
    criticos = [a for a in alertas if a["nivel"] == "critico"]
    urgentes = [a for a in alertas if a["nivel"] == "urgente"]
    atencoes = [a for a in alertas if a["nivel"] == "atencao"]

    por_modulo: dict[str, int] = {}
    for a in alertas:
        por_modulo[a["modulo"]] = por_modulo.get(a["modulo"], 0) + 1

    return {
        "total":    len(alertas),
        "criticos": len(criticos),
        "urgentes": len(urgentes),
        "atencoes": len(atencoes),
        "por_modulo": por_modulo,
    }
