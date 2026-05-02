"""Punto de entrada de la app Flask del Radar Regulatorio."""
from __future__ import annotations

import logging
import os
from datetime import timedelta

from flask import Flask

from config import config
from radar import db
from radar.auth import bp as auth_bp
from radar.routes import bp as radar_bp


def crear_app() -> Flask:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = Flask(__name__)
    app.secret_key = config.flask_secret_key
    app.permanent_session_lifetime = timedelta(days=30)
    app.register_blueprint(auth_bp)
    app.register_blueprint(radar_bp)

    db.init_db()

    if os.environ.get("RADAR_DISABLE_SCHEDULER") != "1":
        if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            from radar.scheduler import iniciar_scheduler
            iniciar_scheduler()

    return app


app = crear_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
