"""
core/dashboard/widgets_alertas.py — widgets do Painel Personalizado
originados da Central de Alertas. Reusa core/domain/alertas.py.
"""
from __future__ import annotations
from datetime import date

from core.dashboard import adapters as ad
from core.domain import alertas as al


def _fetch_lista_alertas(data_ini: date, data_fim: date) -> dict:
    todos = al.get_todos_alertas(str(data_ini), str(date.today()))
    return ad.lista_alertas(todos)


def _fetch_total_alertas(data_ini: date, data_fim: date) -> dict:
    todos = al.get_todos_alertas(str(data_ini), str(date.today()))
    resumo = al.resumo_alertas(todos)
    return ad.kpi(resumo.get("total", 0), "int")


def _fetch_alertas_criticos(data_ini: date, data_fim: date) -> dict:
    todos = al.get_todos_alertas(str(data_ini), str(date.today()))
    resumo = al.resumo_alertas(todos)
    return ad.kpi(resumo.get("criticos", 0), "int")


WIDGETS_ALERTAS = [
    {"id": "alr_lista", "nome": "Alertas Ativos", "origem": "Alertas",
     "descricao": "Lista dos alertas ativos (críticos/urgentes/atenção).", "tipo": "lista_alertas", "w": 4, "h": 4,
     "fetch": _fetch_lista_alertas},
    {"id": "alr_total", "nome": "Total de Alertas", "origem": "Alertas",
     "descricao": "Quantidade total de alertas ativos.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_total_alertas},
    {"id": "alr_criticos", "nome": "Alertas Críticos", "origem": "Alertas",
     "descricao": "Quantidade de alertas em nível crítico.", "tipo": "kpi", "w": 3, "h": 2,
     "fetch": _fetch_alertas_criticos},
]
