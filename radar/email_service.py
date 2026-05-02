"""Servicio de envío de correos vía API de Brevo (https://developers.brevo.com/).

Si BREVO_API_KEY no está configurada, los correos se "simulan" y se vuelcan a
logs/emails_simulados.log para que se pueda probar el flujo en local sin cuenta.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from html import escape
from typing import Iterable

import requests

from config import config

log = logging.getLogger(__name__)

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"


def _render_email_html(publicaciones: list[dict], url_baja: str) -> tuple[str, str]:
    """Devuelve (asunto, html). publicaciones es lista de dicts con titulo/url/fuente/fecha_publicacion/departamento."""
    fecha = datetime.now().strftime("%d/%m/%Y")
    n = len(publicaciones)
    if n == 0:
        asunto = f"Radar Regulatorio · {fecha} · Sin novedades en las últimas 24 h"
    else:
        asunto = f"Radar Regulatorio · {fecha} · {n} novedad{'es' if n != 1 else ''} en las últimas 24 h"

    if n == 0:
        cuerpo_lista = "<p>No se han detectado nuevas publicaciones relevantes en las últimas 24 horas.</p>"
    else:
        items_html = []
        for p in publicaciones:
            fuente = escape(p.get("fuente", ""))
            depto = escape(p.get("departamento") or "")
            fecha_pub = escape(p.get("fecha_publicacion", ""))
            titulo = escape(p.get("titulo", ""))
            url = escape(p.get("url", ""))
            items_html.append(
                f"""
                <li style="margin-bottom:14px;">
                    <div style="font-size:12px;color:#666;">[{fuente}] {fecha_pub} · {depto}</div>
                    <a href="{url}" style="color:#0a3a7a;text-decoration:none;font-weight:600;">{titulo}</a>
                </li>
                """.strip()
            )
        cuerpo_lista = "<ul style='padding-left:18px;'>" + "\n".join(items_html) + "</ul>"

    html = f"""
    <html><body style="font-family:Arial,Helvetica,sans-serif;color:#222;max-width:680px;margin:0 auto;padding:18px;">
        <h2 style="color:#0a3a7a;border-bottom:1px solid #eee;padding-bottom:8px;">Radar Regulatorio</h2>
        <p style="color:#444;">Resumen diario de novedades regulatorias detectadas en BOE y Banco de España (últimas 24 h).</p>
        {cuerpo_lista}
        <hr style="border:none;border-top:1px solid #eee;margin-top:24px;"/>
        <p style="font-size:11px;color:#888;">
            Recibes este correo porque te suscribiste en el Radar Regulatorio.
            Si no deseas seguir recibiéndolo, <a href="{escape(url_baja)}" style="color:#888;">date de baja aquí</a>.
            Tus datos se usan exclusivamente para enviarte estas alertas y nunca se ceden a terceros.
        </p>
    </body></html>
    """.strip()
    return asunto, html


def _enviar_via_brevo(destinatario: str, asunto: str, html: str) -> bool:
    payload = {
        "sender": {"email": config.brevo_sender_email, "name": config.brevo_sender_name},
        "to": [{"email": destinatario}],
        "subject": asunto,
        "htmlContent": html,
    }
    headers = {
        "api-key": config.brevo_api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        r = requests.post(BREVO_ENDPOINT, headers=headers, json=payload, timeout=20)
    except requests.RequestException as exc:
        log.error("Brevo: error de red enviando a %s: %s", destinatario, exc)
        return False
    if r.status_code in (200, 201, 202):
        return True
    log.error("Brevo: HTTP %s al enviar a %s: %s", r.status_code, destinatario, r.text[:200])
    return False


def _simular_envio(destinatario: str, asunto: str, html: str) -> bool:
    log_path = config.logs_dir / "emails_simulados.log"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"\n----- {datetime.now(timezone.utc).isoformat()} -----\n")
        fh.write(f"To: {destinatario}\nSubject: {asunto}\n\n{html}\n")
    log.info("Email SIMULADO a %s (BREVO_API_KEY vacía)", destinatario)
    return True


def enviar_alerta(destinatario: str, publicaciones: list[dict], token_baja: str) -> bool:
    url_baja = f"{config.public_base_url}/baja/{token_baja}"
    asunto, html = _render_email_html(publicaciones, url_baja)
    if not config.brevo_api_key:
        return _simular_envio(destinatario, asunto, html)
    return _enviar_via_brevo(destinatario, asunto, html)


def enviar_a_todos(publicaciones: list[dict]) -> tuple[int, int]:
    """Envía la alerta a todos los suscriptores activos. Devuelve (ok, fallidos)."""
    suscriptores = db.listar_suscriptores_activos()
    ok = 0
    fail = 0
    for s in suscriptores:
        if enviar_alerta(s["email"], publicaciones, s["token_baja"]):
            ok += 1
        else:
            fail += 1
    return ok, fail


# Importación tardía para evitar ciclo entre db y email_service.
from radar import db  # noqa: E402
