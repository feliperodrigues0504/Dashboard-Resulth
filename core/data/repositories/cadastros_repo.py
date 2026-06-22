"""
Queries de cadastros base — usadas para popular os filtros globais.
Todos os resultados são cacheados (TTL longo — cadastros mudam pouco).
"""
import pandas as pd
from core.data.firebird import fb_query

# Nota: a tabela EMPRESA do Resulth é um registro único de licença/config do
# sistema (sem lista de empresas com CODEMPRESA/NOME) — não existe cadastro de
# empresas no banco. Os únicos códigos em uso real são '00' (matriz — todo o
# movimento financeiro/comercial/compras e o estoque real) e '01' (filial —
# aparece apenas em COMPPROD, sempre com saldo zerado). Por isso a lista de
# empresas é fixa em Python, não consultada via SQL.
_EMPRESAS_FIXAS = pd.DataFrame({"COD": ["00", "01"], "NOME": ["Matriz (00)", "Filial (01)"]})

_SQL_VENDEDORES = "SELECT TRIM(CODVENDEDOR) AS COD, TRIM(NOME) AS NOME FROM VENDEND ORDER BY NOME"
_SQL_CLIENTES  = "SELECT TRIM(CODCLIENTE) AS COD, TRIM(NOME) AS NOME FROM CLIENTE ORDER BY NOME"
_SQL_FORNECEDORES = "SELECT TRIM(CODFORNEC) AS COD, TRIM(NOME) AS NOME FROM FORNECE ORDER BY NOME"
_SQL_GRUPOS    = "SELECT TRIM(CODGRUPO) AS COD, TRIM(DESCRICAO) AS NOME FROM GRUPROD ORDER BY DESCRICAO"
_SQL_MARCAS    = "SELECT TRIM(CODFABRIC) AS COD, TRIM(DESCRICAO) AS NOME FROM CADFABR ORDER BY DESCRICAO"


def _safe(sql: str) -> pd.DataFrame:
    """Executa uma das queries de cadastro acima; devolve tabela vazia (COD/NOME) em caso de falha."""
    try:
        return fb_query(sql)
    except Exception:
        return pd.DataFrame(columns=["COD", "NOME"])


def fetch_opcoes_filtros() -> dict:
    """Retorna todas as opções para os filtros globais."""
    def _lista(df: pd.DataFrame) -> list[str]:
        """Extrai a coluna NOME de um cadastro como lista simples (para popular um selectbox)."""
        return df["NOME"].dropna().tolist()

    empresas    = _EMPRESAS_FIXAS
    vendedores  = _safe(_SQL_VENDEDORES)
    clientes    = _safe(_SQL_CLIENTES)
    fornecedores = _safe(_SQL_FORNECEDORES)
    grupos      = _safe(_SQL_GRUPOS)
    marcas      = _safe(_SQL_MARCAS)

    return {
        "empresas_df":     empresas,
        "vendedores_df":   vendedores,
        "clientes_df":     clientes,
        "fornecedores_df": fornecedores,
        "grupos_df":       grupos,
        "marcas_df":       marcas,
        "empresas":    _lista(empresas),
        "vendedores":  _lista(vendedores),
        "clientes":    _lista(clientes),
        "fornecedores": _lista(fornecedores),
        "grupos":      _lista(grupos),
        "marcas":      _lista(marcas),
    }
