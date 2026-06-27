"""
Rastreamento do horário real da última busca de dados (cache miss), para
exibir "Dados de 14:32 (há 3 min)" em vez de datetime.now() — que mostra a
hora em que a página foi renderizada, não a hora em que os dados foram
efetivamente buscados no Firebird (podem estar até `ttl` minutos atrasados
por causa do st.cache_data).

Uso dentro de uma função decorada com @st.cache_data (executa só em cache
miss, exatamente quando queremos registrar o horário):

    @st.cache_data(ttl=600, show_spinner=False)
    def _home_financeiro():
        marcar_frescor("home_financeiro")
        ...

E na UI:
    st.caption(rotulo_frescor("home_financeiro", "home_faturamento", ...))
"""
from __future__ import annotations
from datetime import datetime
import streamlit as st


@st.cache_resource(show_spinner=False)
def _registro() -> dict[str, datetime]:
    """Singleton por processo (sobrevive a TTL/reruns) — guarda a hora do último cache miss de cada chave."""
    return {}


def marcar_frescor(chave: str) -> None:
    """Registra agora como o horário do último fetch real (cache miss) da fonte `chave`."""
    _registro()[chave] = datetime.now()


def hora_frescor(chave: str) -> datetime | None:
    """Horário do último fetch real registrado para `chave`, ou None se nunca buscado nesta sessão do processo."""
    return _registro().get(chave)


def rotulo_frescor(*chaves: str) -> str:
    """
    Rótulo amigável baseado na fonte MAIS ANTIGA entre `chaves` — representa
    o dado mais desatualizado que compõe a página, não a mais recente.
    """
    horarios = [h for h in (hora_frescor(c) for c in chaves) if h is not None]
    if not horarios:
        return "Dados: carregando…"

    mais_antigo = min(horarios)
    delta_min = int((datetime.now() - mais_antigo).total_seconds() // 60)
    hora_str = mais_antigo.strftime("%H:%M")

    if delta_min <= 0:
        return f"Dados de {hora_str} (agora mesmo)"
    if delta_min == 1:
        return f"Dados de {hora_str} (há 1 min)"
    return f"Dados de {hora_str} (há {delta_min} min)"
