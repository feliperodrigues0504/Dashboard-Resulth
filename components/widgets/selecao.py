"""Grade de dados com seleção de linha — UI pura, sem acesso a dado."""
import pandas as pd
import streamlit as st


def df_selecionavel(df: pd.DataFrame, key: str, height: int = 320):
    """st.dataframe com seleção de linha — compatível com st.dialog (fragment rerun)."""
    ev = st.dataframe(
        df, use_container_width=True, hide_index=True,
        selection_mode="single-row", on_select="rerun",
        height=height, key=key,
    )
    rows = ev.selection.rows if ev and ev.selection else []
    return rows[0] if rows else None


def selecao_mudou(key: str, valor) -> bool:
    """
    True só quando `valor` é uma seleção genuinamente nova para essa `key`
    (diferente do valor visto na última checagem com a mesma key).

    A seleção de uma grade (AgGrid ou st.dataframe) continua "verdadeira"
    em todo rerun seguinte até o usuário mudar a seleção — ela não volta a
    None sozinha depois de abrir o dialog. Numa página com 2+ grades que
    abrem dialog (ex.: uma por aba), isso faz o Streamlit tentar abrir mais
    de um `st.dialog` no mesmo script run sempre que o usuário interage com
    qualquer aba depois de já ter selecionado algo em outra — e lançar
    StreamlitAPIException ("Only one dialog is allowed..."). Usar esta
    função para só disparar o dialog quando a seleção realmente mudou
    resolve o problema na raiz, em vez de só no ponto onde ele apareceu.
    """
    chave_estado = f"_ultima_sel_{key}"
    anterior = st.session_state.get(chave_estado)
    st.session_state[chave_estado] = valor
    return valor is not None and valor != anterior
