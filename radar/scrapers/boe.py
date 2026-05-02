"""Scraper del BOE basado en la API de datos abiertos.

Endpoint: https://www.boe.es/datosabiertos/api/boe/sumario/YYYYMMDD
Devuelve un JSON con la jerarquía:
    data.sumario.diario[].seccion[].departamento[].texto.epigrafe[].item[]

(En partes del árbol algunos campos pueden ser un dict (un solo elemento)
 en lugar de una lista — `_to_list` los normaliza.)

Filosofía de filtrado (conservadora):
    - Sólo miramos las secciones I (Disposiciones generales) y III (Otras
      disposiciones), que son donde se publican leyes, reales decretos,
      órdenes ministeriales, circulares del Banco de España, etc.
    - Una publicación se considera relevante si:
          * el departamento emisor está en la lista DEPARTAMENTOS_RELEVANTES, O
          * el título contiene alguna palabra clave de KEYWORDS_RAW.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Iterable

import requests

from radar import db
from radar.keywords import departamento_es_relevante, titulo_es_relevante

log = logging.getLogger(__name__)

API_TPL = "https://www.boe.es/datosabiertos/api/boe/sumario/{yyyymmdd}"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "RadarRegulatorio/0.1 (+contacto)",
}
SECCIONES_INTERESANTES = {"1", "3"}  # I. Disposiciones generales y III. Otras disposiciones

REQUEST_TIMEOUT = 20  # segundos


def _to_list(x: Any) -> list:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def _fetch_sumario(d: date) -> dict | None:
    url = API_TPL.format(yyyymmdd=d.strftime("%Y%m%d"))
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        log.warning("BOE %s: error de red: %s", d, exc)
        return None
    if r.status_code != 200:
        log.debug("BOE %s: HTTP %s", d, r.status_code)
        return None
    try:
        data = r.json()
    except ValueError:
        log.debug("BOE %s: respuesta no es JSON", d)
        return None
    if data.get("status", {}).get("code") != "200":
        # Domingos / festivos sin BOE devuelven un status distinto
        return None
    return data


def _items_de_sumario(data: dict) -> Iterable[tuple[str, str, dict]]:
    """Itera (codigo_seccion, nombre_departamento, item_dict) sobre el sumario."""
    sumario = data.get("data", {}).get("sumario", {})
    for diario in _to_list(sumario.get("diario")):
        for sec in _to_list(diario.get("seccion")):
            cod_sec = str(sec.get("codigo", ""))
            if cod_sec not in SECCIONES_INTERESANTES:
                continue
            for dep in _to_list(sec.get("departamento")):
                nombre_dep = (dep.get("nombre") or "").strip()
                texto = dep.get("texto", {}) or {}
                # Forma A: texto.epigrafe[].item[]
                # Forma B: texto.item (sin epígrafes intermedios)
                if "epigrafe" in texto:
                    epigrafes = _to_list(texto["epigrafe"])
                    bloques = (_to_list(ep.get("item")) for ep in epigrafes)
                else:
                    bloques = [_to_list(texto.get("item"))]
                for items in bloques:
                    for it in items:
                        if it:
                            yield cod_sec, nombre_dep, it


def _item_relevante(nombre_dep: str, titulo: str) -> bool:
    if departamento_es_relevante(nombre_dep):
        return True
    return titulo_es_relevante(titulo)


def ingest_dia(d: date) -> int:
    """Ingesta el sumario del BOE de una fecha. Devuelve nº de publicaciones nuevas."""
    data = _fetch_sumario(d)
    if not data:
        return 0
    nuevas = 0
    for cod_sec, nombre_dep, item in _items_de_sumario(data):
        identificador = (item.get("identificador") or "").strip()
        titulo = (item.get("titulo") or "").strip()
        if not identificador or not titulo:
            continue
        if not _item_relevante(nombre_dep, titulo):
            continue
        # Preferimos la URL HTML (consultable directamente); como respaldo, el PDF.
        url = (item.get("url_html") or "").strip()
        if not url:
            url_pdf = item.get("url_pdf") or {}
            url = (url_pdf.get("texto") or "").strip()
        if not url:
            url = f"https://www.boe.es/diario_boe/txt.php?id={identificador}"

        seccion_nombre = "I. Disposiciones generales" if cod_sec == "1" else "III. Otras disposiciones"
        if db.upsert_publicacion(
            fuente="BOE",
            identificador=identificador,
            titulo=titulo,
            url=url,
            fecha_publicacion=d.isoformat(),
            departamento=nombre_dep,
            seccion=seccion_nombre,
        ):
            nuevas += 1
    return nuevas


def ingest_rango(dias: int = 31) -> int:
    """Ingesta los últimos `dias` días desde hoy. Devuelve total de novedades nuevas."""
    total = 0
    hoy = date.today()
    for delta in range(0, dias + 1):
        d = hoy - timedelta(days=delta)
        n = ingest_dia(d)
        if n:
            log.info("BOE %s: %s nuevas", d, n)
        total += n
    return total
