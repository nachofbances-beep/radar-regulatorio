"""Script CLI para lanzar la ingesta y, opcionalmente, los correos diarios.

Uso:
    python run_ingest.py              # sólo ingesta
    python run_ingest.py --enviar     # ingesta + envío a suscriptores

Pensado para ejecutarse desde el Programador de tareas de Windows si prefieres
no depender del scheduler interno de la app.
"""
from __future__ import annotations

import argparse
import logging
import sys

from radar import db, email_service, ingest


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Ingesta del Radar Regulatorio.")
    parser.add_argument("--enviar", action="store_true", help="Enviar correos a los suscriptores tras la ingesta.")
    args = parser.parse_args()

    res = ingest.ejecutar_ingesta()
    print(f"BOE nuevas: {res.boe_nuevas}")
    print(f"BdE nuevas: {res.bde_nuevas}")
    print(f"Total:      {res.total}")
    print(f"Duración:   {res.duracion_segundos:.1f}s")

    if args.enviar:
        publicaciones = [dict(r) for r in db.publicaciones_ultimas_horas(24)]
        ok, fail = email_service.enviar_a_todos(publicaciones)
        print(f"Correos enviados: ok={ok}, fallidos={fail}, novedades={len(publicaciones)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
