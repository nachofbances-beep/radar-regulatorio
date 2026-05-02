"""Orquestador de la ingesta: lanza todos los scrapers y devuelve el resumen."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from config import config
from radar import db
from radar.scrapers import bde, boe

log = logging.getLogger(__name__)


@dataclass
class ResultadoIngesta:
    inicio: datetime
    fin: datetime
    boe_nuevas: int
    bde_nuevas: int

    @property
    def total(self) -> int:
        return self.boe_nuevas + self.bde_nuevas

    @property
    def duracion_segundos(self) -> float:
        return (self.fin - self.inicio).total_seconds()


def ejecutar_ingesta() -> ResultadoIngesta:
    """Ingesta completa: BOE + BdE, en el rango de lookback configurado."""
    db.init_db()
    inicio = datetime.now(timezone.utc)
    log.info("Ingesta iniciada (lookback=%s días)", config.ingest_lookback_days)
    boe_n = boe.ingest_rango(dias=config.ingest_lookback_days)
    bde_n = bde.ingest_rango(dias=config.ingest_lookback_days)
    fin = datetime.now(timezone.utc)
    log.info("Ingesta finalizada: BOE=%s, BdE=%s, dur=%.1fs", boe_n, bde_n, (fin - inicio).total_seconds())
    return ResultadoIngesta(inicio=inicio, fin=fin, boe_nuevas=boe_n, bde_nuevas=bde_n)
