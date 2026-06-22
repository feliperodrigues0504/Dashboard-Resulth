"""
Conexão somente-leitura ao banco Firebird de produção (ERP Resulth) e
execução de queries cru, devolvendo o resultado como DataFrame.
"""
import fdb
import pandas as pd
from contextlib import contextmanager
from config.settings import FB_HOST, FB_DATABASE, FB_USER, FB_PASSWORD, FB_CHARSET

# Garante que o fdb encontre o fbclient.dll na raiz do projeto
# (core/data/firebird.py está 3 níveis abaixo da raiz: data -> core -> raiz)
import os
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
fdb.load_api(os.path.join(_ROOT, "fbclient.dll"))


def _connect():
    """Abre uma nova conexão com o Firebird usando as credenciais de config.settings."""
    return fdb.connect(
        host=FB_HOST,
        database=FB_DATABASE,
        user=FB_USER,
        password=FB_PASSWORD,
        charset=FB_CHARSET,
    )


@contextmanager
def firebird_conn():
    """Context manager: abre uma conexão Firebird e garante o fechamento à saída do bloco `with`, mesmo em caso de exceção."""
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


def fb_query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Executa uma query no Firebird e retorna DataFrame."""
    with firebird_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)
