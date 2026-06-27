"""Configuração central do app: credenciais Firebird (via .env), caminho do DuckDB e constantes globais."""
import os
from dotenv import load_dotenv

# Carrega variáveis de C:\...\Projeto-Cetel\.env (arquivo fora do versionamento —
# ver .env.example para o template). Credenciais nunca devem ficar hardcoded
# aqui: este projeto acessa um banco de produção real do cliente.
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Firebird — valores abaixo são apenas placeholders não-funcionais, usados só
# se o .env não existir ou a variável não estiver definida nele. NUNCA coloque
# aqui um caminho/usuário/senha reais — este arquivo vai para o controle de
# versão (o .env real, esse sim, fica de fora via .gitignore).
FB_HOST     = os.environ.get("FB_HOST", "localhost")
FB_DATABASE = os.environ.get("FB_DATABASE", r"C:\Caminho\Para\RESULTH.FB")
FB_USER     = os.environ.get("FB_USER", "SYSDBA")
FB_PASSWORD = os.environ.get("FB_PASSWORD", "troque-esta-senha")
FB_CHARSET  = os.environ.get("FB_CHARSET", "WIN1252")

# DuckDB
DUCK_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "store.duckdb")

# Relatórios gerados automaticamente (ex.: relatório executivo semanal)
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "relatorios")

# App
APP_TITLE = "Cetel — Dashboards Resulth"
SYNC_INTERVAL_MINUTES = 15
