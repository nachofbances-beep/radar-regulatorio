"""Autenticación basada en una contraseña compartida.

Diseño deliberadamente simple: una única contraseña ("APP_PASSWORD" en .env)
da acceso a toda la web. Comparación con `secrets.compare_digest` para evitar
ataques de timing. La sesión de Flask guarda un flag booleano cifrado.

Rutas exentas (no exigen login):
    /login      → formulario de acceso
    /logout     → cerrar sesión
    /baja/<t>   → enlace de baja del correo (es público por diseño)
    /static/*   → CSS / assets
"""
from __future__ import annotations

import secrets
from functools import wraps
from typing import Callable

from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for,
)

from config import config

bp = Blueprint("auth", __name__)

SESSION_KEY = "auth_ok"

# Rutas que NO necesitan login (endpoint names, no URLs).
RUTAS_PUBLICAS = {
    "auth.login",
    "auth.logout",
    "radar.baja",
    "static",
}


def usuario_autenticado() -> bool:
    return bool(session.get(SESSION_KEY))


def login_required(view: Callable) -> Callable:
    """Decorador que redirige al login si la sesión no está autenticada."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not usuario_autenticado():
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


@bp.before_app_request
def _proteger_globalmente():
    """Aplica el muro de login a TODAS las vistas salvo las exentas.

    Más robusto que decorar cada ruta a mano: si en el futuro se añade una
    ruta nueva, queda protegida por defecto.
    """
    endpoint = request.endpoint or ""
    if endpoint in RUTAS_PUBLICAS:
        return None
    if usuario_autenticado():
        return None
    # Permite a Flask resolver assets estáticos sin redirección.
    if endpoint == "static":
        return None
    return redirect(url_for("auth.login", next=request.path))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if usuario_autenticado():
        return redirect(url_for("radar.index"))

    if request.method == "POST":
        intento = request.form.get("password", "")
        # compare_digest opera sobre bytes/str de igual longitud; conviene
        # convertir antes para no filtrar la longitud configurada.
        if secrets.compare_digest(intento, config.app_password):
            session[SESSION_KEY] = True
            session.permanent = True
            destino = request.args.get("next") or url_for("radar.index")
            # Defensa básica contra open-redirect: sólo aceptamos rutas relativas.
            if not destino.startswith("/"):
                destino = url_for("radar.index")
            return redirect(destino)
        flash("Contraseña incorrecta.", "error")
        return redirect(url_for("auth.login"))

    return render_template("login.html", active_tab=None)


@bp.route("/logout")
def logout():
    session.pop(SESSION_KEY, None)
    flash("Sesión cerrada.", "success")
    return redirect(url_for("auth.login"))
