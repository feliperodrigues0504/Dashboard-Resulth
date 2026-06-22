"""
Camada de acesso ao DuckDB (data/store.duckdb) — o único armazenamento
gravável do app (snapshots diários, comentários gerenciais, configurações).
O Firebird é sempre somente-leitura; nada aqui é escrito de volta nele.
"""
import duckdb
import pandas as pd
from contextlib import contextmanager
from config.settings import DUCK_PATH


def get_conn() -> duckdb.DuckDBPyConnection:
    """Abre uma nova conexão com o arquivo DuckDB local (data/store.duckdb)."""
    return duckdb.connect(DUCK_PATH)


@contextmanager
def duck_conn():
    """Context manager: abre uma conexão DuckDB e garante o fechamento à saída do bloco `with`."""
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()


def duck_query(sql: str, params: list = None) -> pd.DataFrame:
    """Executa uma query de leitura no DuckDB e retorna o resultado como DataFrame."""
    with duck_conn() as conn:
        if params:
            return conn.execute(sql, params).df()
        return conn.execute(sql).df()


def duck_execute(sql: str, params: list = None):
    """Executa um comando de escrita (INSERT/UPDATE/DELETE/DDL) no DuckDB."""
    with duck_conn() as conn:
        if params:
            conn.execute(sql, params)
        else:
            conn.execute(sql)


def duck_executemany(sql: str, params_seq: list[list]):
    """
    Executa o mesmo INSERT/UPDATE para várias linhas em uma única conexão
    (1 round trip), em vez de chamar duck_execute() dentro de um loop —
    que abriria/fecharia uma conexão por linha.
    """
    if not params_seq:
        return
    with duck_conn() as conn:
        conn.executemany(sql, params_seq)


def get_config(chave: str, default=None):
    """Lê um valor de configuração do DuckDB."""
    try:
        df = duck_query("SELECT valor FROM config_alertas WHERE chave = ?", [chave])
        return df.iloc[0]["valor"] if not df.empty else default
    except Exception:
        return default


def get_preferencia(chave: str, default: str = "true") -> str:
    """Lê preferência da tela inicial."""
    try:
        df = duck_query("SELECT valor FROM preferencias_home WHERE chave = ?", [chave])
        return df.iloc[0]["valor"] if not df.empty else default
    except Exception:
        return default


def set_preferencia(chave: str, valor: str):
    """Salva preferência da tela inicial."""
    try:
        duck_execute("""
            INSERT INTO preferencias_home (chave, valor)
            VALUES (?, ?)
            ON CONFLICT (chave) DO UPDATE SET valor = excluded.valor
        """, [chave, valor])
    except Exception:
        pass


def set_config(chave: str, valor: str) -> bool:
    """Salva ou atualiza um valor de configuração. Retorna False em caso de falha."""
    try:
        duck_execute("""
            INSERT INTO config_alertas (chave, valor)
            VALUES (?, ?)
            ON CONFLICT (chave) DO UPDATE SET valor = excluded.valor
        """, [chave, str(valor)])
        return True
    except Exception as e:
        print(f"[set_config] erro ao gravar '{chave}': {e}")
        return False


def salvar_comentario(modulo: str, indicador: str,
                      periodo_ini, periodo_fim, texto: str) -> bool:
    """Grava um comentário gerencial. Retorna False em caso de falha."""
    try:
        with duck_conn() as conn:
            conn.execute("""
                INSERT INTO comentarios (id, modulo, indicador, periodo_ini, periodo_fim, texto)
                VALUES (nextval('seq_comentarios'), ?, ?, ?, ?, ?)
            """, [modulo, indicador, str(periodo_ini), str(periodo_fim), texto.strip()])
        return True
    except Exception as e:
        print(f"[salvar_comentario] erro ao gravar comentário ({modulo}/{indicador}): {e}")
        return False


def get_comentarios(modulo: str, indicador: str,
                    periodo_ini=None, periodo_fim=None) -> pd.DataFrame:
    """
    Lê os comentários gerenciais salvos para um indicador de um módulo,
    mais recentes primeiro. `periodo_ini`/`periodo_fim`, quando informados,
    restringem aos comentários cujo período de referência se sobrepõe ao filtro.
    """
    sql = """
        SELECT id, texto, criado_em
        FROM comentarios
        WHERE modulo = ? AND indicador = ?
    """
    params = [modulo, indicador]
    if periodo_ini:
        sql += " AND periodo_ini >= ?"
        params.append(str(periodo_ini))
    if periodo_fim:
        sql += " AND periodo_fim <= ?"
        params.append(str(periodo_fim))
    sql += " ORDER BY criado_em DESC"
    try:
        return duck_query(sql, params)
    except Exception as e:
        print(f"[get_comentarios] erro ao ler comentários ({modulo}/{indicador}): {e}")
        return pd.DataFrame(columns=["id", "texto", "criado_em"])


def deletar_comentario(id_: int) -> bool:
    """Exclui um comentário gerencial. Retorna False em caso de falha."""
    try:
        duck_execute("DELETE FROM comentarios WHERE id = ?", [id_])
        return True
    except Exception as e:
        print(f"[deletar_comentario] erro ao excluir id={id_}: {e}")
        return False


def init_store():
    """Cria as tabelas analíticas e de snapshot no DuckDB (idempotente)."""
    with duck_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snap_inadimplencia (
                data          DATE,
                valor_vencido DECIMAL(18,2),
                qtd_titulos   INTEGER,
                faixa_1_30    DECIMAL(18,2),
                faixa_31_60   DECIMAL(18,2),
                faixa_61_90   DECIMAL(18,2),
                faixa_90_mais DECIMAL(18,2),
                PRIMARY KEY (data)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snap_saldo_bancario (
                data     DATE,
                id_conta INTEGER,
                saldo    DECIMAL(18,2),
                PRIMARY KEY (data, id_conta)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                tabela      VARCHAR,
                executado_em TIMESTAMP DEFAULT current_timestamp,
                qtd_linhas  INTEGER,
                status      VARCHAR,
                PRIMARY KEY (tabela, executado_em)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS comentarios (
                id          INTEGER PRIMARY KEY,
                modulo      VARCHAR NOT NULL,
                indicador   VARCHAR NOT NULL,
                periodo_ini DATE,
                periodo_fim DATE,
                texto       TEXT    NOT NULL,
                criado_em   TIMESTAMP DEFAULT current_timestamp
            )
        """)
        conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS seq_comentarios START 1
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS config_alertas (
                chave     VARCHAR PRIMARY KEY,
                valor     VARCHAR NOT NULL,
                descricao VARCHAR
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS preferencias_home (
                chave VARCHAR PRIMARY KEY,
                valor VARCHAR NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snap_kpis_diario (
                data        DATE PRIMARY KEY,
                total_ar    DECIMAL(18,2),
                vencido_ar  DECIMAL(18,2),
                total_ap    DECIMAL(18,2),
                vencido_ap  DECIMAL(18,2),
                saldo_bco   DECIMAL(18,2),
                capital_op  DECIMAL(18,2),
                estoque_custo DECIMAL(18,2),
                fat_mes     DECIMAL(18,2)
            )
        """)
        # Valores padrão — só insere se ainda não existirem
        defaults = [
            ("piso_caixa",           "50000",  "Saldo mínimo de caixa (R$) — abaixo disso gera alerta"),
            ("alerta_ap_horas",      "48",     "Horas de antecedência para alertar AP a vencer"),
            ("alerta_atraso_dias",   "90",     "Dias de atraso para classificar cliente como crítico"),
            ("alerta_capital_minimo","100000", "Capital operacional mínimo (R$) — abaixo gera alerta"),
        ]
        for chave, valor, desc in defaults:
            conn.execute("""
                INSERT INTO config_alertas (chave, valor, descricao)
                SELECT ?, ?, ?
                WHERE NOT EXISTS (SELECT 1 FROM config_alertas WHERE chave = ?)
            """, [chave, valor, desc, chave])
