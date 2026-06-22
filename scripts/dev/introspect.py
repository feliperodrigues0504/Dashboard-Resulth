"""
Utilitário de introspecção do banco Firebird (ferramenta de desenvolvimento,
não faz parte do app em execução).
Rodar a partir da raiz do projeto: python scripts/dev/introspect.py DOCUREC DOCUPAG CLIENTE
"""
import re
import sys
sys.path.insert(0, '.')
from core.data.firebird import fb_query

# Identificador válido de tabela Firebird: letras/dígitos/underscore, começando
# por letra ou underscore, até 31 caracteres (limite clássico do Firebird).
# Nomes de tabela não podem ser parametrizados com "?" (isso é só para valores,
# não para identificadores SQL) — por isso validamos com uma allowlist de
# formato antes de interpolar na string, em vez de aceitar qualquer texto.
_NOME_TABELA_VALIDO = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]{0,30}$")

TIPO_MAP = {
    7: "SMALLINT", 8: "INTEGER", 9: "QUAD", 10: "FLOAT",
    11: "D_FLOAT", 12: "DATE", 13: "TIME", 14: "CHAR",
    16: "BIGINT", 27: "DOUBLE", 35: "TIMESTAMP", 37: "VARCHAR",
    40: "CSTRING", 45: "BLOB_ID", 261: "BLOB",
}

SQL_COLS = """
SELECT TRIM(rf.RDB$FIELD_NAME)      AS campo,
       f.RDB$FIELD_TYPE             AS tipo_cod,
       f.RDB$FIELD_LENGTH           AS tamanho,
       f.RDB$FIELD_SCALE            AS escala,
       rf.RDB$NULL_FLAG             AS nao_nulo,
       TRIM(rf.RDB$DEFAULT_SOURCE)  AS default_val,
       TRIM(rf.RDB$DESCRIPTION)     AS descricao
FROM   RDB$RELATION_FIELDS rf
JOIN   RDB$FIELDS f ON f.RDB$FIELD_NAME = rf.RDB$FIELD_SOURCE
WHERE  rf.RDB$RELATION_NAME = ?
ORDER  BY rf.RDB$FIELD_POSITION
"""

SQL_COUNT = "SELECT COUNT(*) FROM {}"


def introspect(table: str):
    """Imprime no console a estrutura de colunas (tipo, tamanho, obrigatoriedade) e o total de registros de `table`."""
    if not _NOME_TABELA_VALIDO.match(table):
        print(f"[ERRO] Nome de tabela inválido: '{table}'. Use apenas letras, números e underscore.")
        return

    try:
        df = fb_query(SQL_COLS, (table.upper(),))
    except Exception as e:
        print(f"[ERRO] Falha ao consultar metadados de '{table}': {e}")
        return
    if df.empty:
        print(f"[AVISO] Tabela '{table}' não encontrada ou sem colunas.")
        return

    df["tipo"] = df["TIPO_COD"].map(TIPO_MAP).fillna(df["TIPO_COD"].astype(str))

    try:
        # SQL_COUNT.format(...) em vez de f-string solta — mesma validação acima
        # já garante que table.upper() só contém caracteres seguros de identificador.
        count = fb_query(SQL_COUNT.format(table.upper())).iloc[0, 0]
    except Exception as e:
        count = f"erro ({e})"

    print(f"\n{'='*60}")
    print(f"  TABELA: {table.upper()}  |  {count} registros")
    print(f"{'='*60}")
    print(f"  {'Campo':<35} {'Tipo':<12} {'Tam':>5}  {'Nulo?'}")
    print(f"  {'-'*35} {'-'*12} {'-'*5}  {'-'*5}")
    for _, r in df.iterrows():
        nulo = "NÃO" if r["NAO_NULO"] == 1 else "sim"
        print(f"  {r['CAMPO']:<35} {r['tipo']:<12} {int(r['TAMANHO'] or 0):>5}  {nulo}")


if __name__ == "__main__":
    tabelas = sys.argv[1:] if len(sys.argv) > 1 else [
        "DOCUREC", "DOCUPAG", "MOVIREC", "MOVIPAG",
        "CLIENTE", "FORNECE", "COMPPROD",
        "CONTAS", "SALDOST", "MOVIBAN",
    ]
    for t in tabelas:
        introspect(t)
