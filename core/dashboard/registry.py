"""
core/dashboard/registry.py — registro central de widgets do Painel
Personalizado. Agrega os widgets por módulo (ver widgets_*.py) e expõe
helpers de consulta usados por app.py (Home — painel arrastável/redimensionável).
"""
from __future__ import annotations

from core.dashboard.widgets_financeiro import WIDGETS_FINANCEIRO
from core.dashboard.widgets_comercial import WIDGETS_COMERCIAL
from core.dashboard.widgets_estoque import WIDGETS_ESTOQUE
from core.dashboard.widgets_compras import WIDGETS_COMPRAS
from core.dashboard.widgets_alertas import WIDGETS_ALERTAS
from core.dashboard.widgets_geral import WIDGETS_GERAL

WIDGET_REGISTRY: list[dict] = [
    *WIDGETS_GERAL,
    *WIDGETS_FINANCEIRO,
    *WIDGETS_COMERCIAL,
    *WIDGETS_ESTOQUE,
    *WIDGETS_COMPRAS,
    *WIDGETS_ALERTAS,
]

_POR_ID = {w["id"]: w for w in WIDGET_REGISTRY}

# Tamanho padrão por widget no grid (12 colunas) — usado quando o widget é
# adicionado ao painel pela primeira vez e ainda não tem posição salva.
DEFAULT_W, DEFAULT_H = 4, 3


def get_widget(widget_id: str) -> dict | None:
    """Retorna a definição (metadados + fetch) de um widget pelo id, ou None se não existir."""
    return _POR_ID.get(widget_id)


def widgets_por_origem() -> dict[str, list[dict]]:
    """Agrupa os widgets do registro por módulo de origem, na ordem em que aparecem no registro."""
    grupos: dict[str, list[dict]] = {}
    for w in WIDGET_REGISTRY:
        grupos.setdefault(w["origem"], []).append(w)
    return grupos


def todos_ids() -> list[str]:
    """Lista de todos os ids de widget disponíveis no registro."""
    return [w["id"] for w in WIDGET_REGISTRY]
