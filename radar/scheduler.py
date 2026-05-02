"""Programación del job diario.

Usa APScheduler en modo background dentro del propio proceso de Flask.
A la hora configurada (por defecto 10:00 hora Madrid):
    1. Ejecuta la ingesta del BOE y del BdE.
    2. Recoge las publicaciones detectadas en las últimas 24 horas.
    3. Envía un correo a cada suscriptor activo.
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import config
from radar import db, email_service, ingest

log = logging.getLogger(__name__)

TIMEZONE = ZoneInfo("Europe/Madrid")


def _job_diario() -> None:
    log.info("[job diario] Lanzando ingesta + envío de correos")
    res = ingest.ejecutar_ingesta()
    log.info(
        "[job diario] Ingesta terminada (BOE=%s, BdE=%s, %ss)",
        res.boe_nuevas, res.bde_nuevas, res.duracion_segundos,
    )
    publicaciones = [dict(row) for row in db.publicaciones_ultimas_horas(24)]
    ok, fail = email_service.enviar_a_todos(publicaciones)
    log.info("[job diario] Correos: ok=%s, fallidos=%s, novedades=%s", ok, fail, len(publicaciones))


def iniciar_scheduler() -> BackgroundScheduler:
    """Arranca un BackgroundScheduler con el job diario configurado."""
    horas, minutos = (config.daily_job_time + ":00").split(":")[:2]
    scheduler = BackgroundScheduler(timezone=TIMEZONE)
    trigger = CronTrigger(hour=int(horas), minute=int(minutos), timezone=TIMEZONE)
    scheduler.add_job(_job_diario, trigger, id="job_diario", replace_existing=True)
    scheduler.start()
    proximo = scheduler.get_job("job_diario").next_run_time
    log.info("Scheduler arrancado. Próxima ejecución: %s", proximo)
    return scheduler
