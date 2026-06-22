"""
Classificação de curva ABC (regra de Pareto), compartilhada entre os módulos
Comercial (concentração de clientes/produtos) e Estoque (valor investido por
SKU) — antes reimplementada de forma independente em cada um, com o mesmo
limiar 80/95 mas nomes de coluna diferentes.
"""
import pandas as pd


def classe_por_acumulado(acumulado_pct: float, limite_a: float = 80, limite_b: float = 95) -> str:
    """A = até `limite_a`% acumulado, B = até `limite_b`%, C = o resto."""
    if acumulado_pct <= limite_a:
        return "A"
    if acumulado_pct <= limite_b:
        return "B"
    return "C"


def curva_abc(df: pd.DataFrame, col_valor: str, col_classe: str = "Classe",
              limite_a: float = 80, limite_b: float = 95) -> pd.DataFrame:
    """
    Classifica as linhas de `df` em curva ABC pelo percentual acumulado de
    `col_valor` (do maior para o menor). Devolve uma cópia ordenada com a
    coluna `col_classe` adicionada.
    """
    if df.empty or col_valor not in df.columns:
        return df
    df_ordenado = df.sort_values(col_valor, ascending=False).copy()
    total = df_ordenado[col_valor].sum()
    if total == 0:
        return df_ordenado
    acumulado = df_ordenado[col_valor].cumsum() / total * 100
    df_ordenado[col_classe] = acumulado.apply(
        lambda v: classe_por_acumulado(v, limite_a, limite_b))
    return df_ordenado
