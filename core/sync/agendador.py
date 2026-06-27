"""
core/sync/agendador.py — Agendador de snapshots diários.
Utiliza APScheduler com BackgroundScheduler.
Integração com Streamlit via @st.cache_resource (singleton por processo).

Uso em app.py:
    from core.sync.agendador import iniciar_agendador
    iniciar_agendador()
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

# Horários de tentativa do snapshot diário: 08:00 é a coleta principal; 11:00 e
# 15:00 são "retries" — o APScheduler não tenta de novo sozinho quando um job
# lança exceção (só loga e espera o próximo disparo, que seria só no dia
# seguinte), então cobrimos isso com gatilhos extras no mesmo dia. Funciona
# porque gravar_todos()/_ja_existe() já são idempotentes: se a coleta das
# 08:00 deu certo, as tentativas de 11:00/15:00 não fazem nada (no-op); se
# falhou (ex.: Firebird fora do ar naquele minuto), a próxima tentativa cobre.
_HORARIOS_TENTATIVA = [(8, 0), (11, 0), (15, 0)]


def iniciar_agendador():
    """
    Inicia o BackgroundScheduler (idempotente via st.cache_resource).
    Grava snapshots de hoje se ainda não foram coletados.
    Agenda até 3 tentativas de coleta no mesmo dia (ver _HORARIOS_TENTATIVA).
    """
    import streamlit as st

    @st.cache_resource(show_spinner=False)
    def _scheduler_singleton():
        """
        Cria e inicia o BackgroundScheduler uma única vez por processo
        (st.cache_resource garante isso mesmo com múltiplos reruns do
        Streamlit), agenda as tentativas de snapshot do dia e dispara uma
        coleta imediata, caso o snapshot de hoje ainda não tenha sido feito.
        """
        from apscheduler.schedulers.background import BackgroundScheduler
        from core.sync.snapshot import gravar_todos
        from core.domain.relatorio_executivo import gravar_relatorio_semanal

        scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
        for hora, minuto in _HORARIOS_TENTATIVA:
            scheduler.add_job(
                gravar_todos,
                trigger="cron",
                hour=hora, minute=minuto,
                id=f"snapshot_diario_{hora:02d}{minuto:02d}",
                replace_existing=True,
            )
        # Relatório executivo consolidado: toda segunda-feira às 07:00, depois
        # da janela de snapshot das 08h/11h/15h não ter rodado ainda — usa os
        # dados ao vivo do Firebird na hora da geração, não snapshot.
        scheduler.add_job(
            gravar_relatorio_semanal,
            trigger="cron",
            day_of_week="mon", hour=7, minute=0,
            id="relatorio_executivo_semanal",
            replace_existing=True,
        )
        scheduler.start()
        horarios_fmt = ", ".join(f"{h:02d}:{m:02d}" for h, m in _HORARIOS_TENTATIVA)
        logger.info(f"[agendador] iniciado — tentativas de snapshot às {horarios_fmt}; "
                    f"relatório executivo semanal às segundas 07:00")

        # Grava imediatamente o snapshot de hoje (se ainda não feito)
        try:
            gravar_todos()
            logger.info("[agendador] snapshot inicial do dia concluído")
        except Exception as e:
            logger.warning(f"[agendador] snapshot inicial falhou: {e}")

        return scheduler

    return _scheduler_singleton()
