"""
Paleta de cores única do sistema — fonte canônica para todas as telas.

Importar daqui em vez de redefinir constantes locais. Antes desta consolidação,
COR_PRIM/OK/ALERTA/PERIGO estavam redefinidos identicamente em 6 arquivos, e o
estilo de alerta por nível ("crítico"/"urgente"/"atenção") tinha tons divergentes
entre páginas (ex.: vermelho crítico era #d62728 em pages/05_Alertas.py e #c0392b
em pages/01_Financeiro.py/03_Estoque.py para o mesmo significado).
"""

# ── Cores de status / KPI ──────────────────────────────────────────────────
COR_PRIM   = "#1f6bb5"   # azul primário — identidade visual, valores neutros
COR_OK     = "#2ca02c"   # verde — positivo / saudável
COR_ALERTA = "#e67e22"   # laranja — atenção / urgente
COR_PERIGO = "#d62728"   # vermelho — crítico / vencido

# ── Estilo de card de alerta por nível: (fundo, borda/destaque, ícone bootstrap, texto) ──
NIVEL_STYLE = {
    "critico": ("#fde8e8", "#c0392b", "exclamation-octagon-fill",  "#7b1111"),
    "urgente": ("#fff3e0", "#e67e22", "exclamation-triangle-fill", "#7a3a00"),
    "atencao": ("#fefce8", "#b7950b", "info-circle-fill",          "#5a4800"),
}

NIVEL_LABEL = {"critico": "CRÍTICO", "urgente": "URGENTE", "atencao": "ATENÇÃO"}
