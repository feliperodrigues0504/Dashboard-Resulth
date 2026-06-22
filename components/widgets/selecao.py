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
