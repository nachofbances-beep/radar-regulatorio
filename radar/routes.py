"""Rutas de la app Flask."""
from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime

from flask import (
    Blueprint, abort, flash, redirect, render_template, request, url_for,
)

from config import config
from radar import db, ingest

log = logging.getLogger(__name__)

bp = Blueprint("radar", __name__)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@bp.route("/")
def index():
    publicaciones = db.listar_publicaciones(archivadas=False, dias=config.display_window_days)
    return render_template(
        "novedades.html",
        publicaciones=publicaciones,
        active_tab="novedades",
        ahora=datetime.now(),
        ventana_dias=config.display_window_days,
    )


@bp.route("/repositorio")
def repositorio():
    publicaciones = db.listar_publicaciones(archivadas=True, dias=10000)
    return render_template(
        "repositorio.html",
        publicaciones=publicaciones,
        active_tab="repositorio",
        ahora=datetime.now(),
    )


@bp.route("/archivar/<int:pub_id>", methods=["POST"])
def archivar(pub_id: int):
    pub = db.get_publicacion(pub_id)
    if not pub:
        abort(404)
    db.archivar(pub_id, archivar_flag=True)
    flash("Publicación archivada.", "success")
    return redirect(request.referrer or url_for("radar.index"))


@bp.route("/desarchivar/<int:pub_id>", methods=["POST"])
def desarchivar(pub_id: int):
    pub = db.get_publicacion(pub_id)
    if not pub:
        abort(404)
    db.archivar(pub_id, archivar_flag=False)
    flash("Publicación devuelta a Novedades.", "success")
    return redirect(request.referrer or url_for("radar.repositorio"))


@bp.route("/refrescar", methods=["POST"])
def refrescar():
    try:
        res = ingest.ejecutar_ingesta()
        if res.total == 0:
            flash("No se han detectado nuevas publicaciones.", "info")
        else:
            flash(
                f"Ingesta completada: {res.boe_nuevas} nuevas en BOE y "
                f"{res.bde_nuevas} en Banco de España.",
                "success",
            )
    except Exception as exc:
        log.exception("Error al refrescar")
        flash(f"Error al refrescar: {exc}", "error")
    return redirect(url_for("radar.index"))


@bp.route("/suscribirse", methods=["GET", "POST"])
def suscribirse():
    if request.method == "GET":
        return render_template("suscribirse.html", active_tab="suscribirse")

    email = (request.form.get("email") or "").strip().lower()
    consentimiento = request.form.get("consentimiento") == "on"

    if not EMAIL_RE.match(email):
        flash("Introduce un correo electrónico válido.", "error")
        return redirect(url_for("radar.suscribirse"))
    if not consentimiento:
        flash("Debes aceptar la política de protección de datos para suscribirte.", "error")
        return redirect(url_for("radar.suscribirse"))

    token = secrets.token_urlsafe(32)
    nuevo = db.alta_suscriptor(email, token)
    if nuevo:
        flash(
            "Suscripción confirmada. Recibirás el primer correo a las 10:00 (hora de Madrid).",
            "success",
        )
    else:
        flash("Esa dirección ya estaba suscrita.", "info")
    return redirect(url_for("radar.index"))


@bp.route("/baja/<token>")
def baja(token: str):
    email = db.baja_por_token(token)
    return render_template("baja.html", email=email, active_tab=None)


@bp.route("/privacidad")
def privacidad():
    return render_template("privacidad.html", active_tab=None)
