"""Scraper del Banco de España.

Fuente principal: índice cronológico de Circulares del Banco de España.
URL:
    https://www.bde.es/wbe/es/areas-actuacion/normativa/circulares-banco-de-espana/
    circulares-banco-espana-indice-cronologico/

Cada circular aparece como un <li> con el patrón:
    Circular X/AAAA, de DD de MES, del Banco de España, [...]. (BOE de DD de MES de AAAA)
y un <a href> al detalle de la norma en app.bde.es.

Extraemos:
    - identificador: "BdE-Circular-X/AAAA"
    - título: texto completo del item
    - URL: el href del enlace
    - fecha_publicacion: la fecha del BOE si aparece, o la del enunciado de la circular

Nota: muchas circulares también se detectan vía el BOE (sección III, dpto. BANCO DE
ESPAÑA). El UNIQUE(fuente, identificador) en BBDD evita duplicados dentro de cada
fuente; entre fuentes pueden coexistir, pero se identifican claramente con un
prefijo "BdE-" vs. el código del BOE ("BOE-A-..."). Esto es deliberado: a veces
queremos saber que la misma norma se publicó en ambos sitios.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from radar import db

log = logging.getLogger(__name__)

URL_INDICE_CIRCULARES = (
    "https://www.bde.es/wbe/es/areas-actuacion/normativa/circulares-banco-de-espana/"
    "circulares-banco-espana-indice-cronologico/"
)
HEADERS = {
    "User-Agent": "RadarRegulatorio/0.1 (+contacto)",
    "Accept-Language": "es-ES,es;q=0.9",
}
REQUEST_TIMEOUT = 25

MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

RE_CIRCULAR = re.compile(r"Circular\s+(\d+)/(\d{4})", re.IGNORECASE)
RE_BOE_FECHA = re.compile(
    r"BOE\s+de\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", re.IGNORECASE
)
RE_FECHA_FIRMA = re.compile(
    r",\s+de\s+(\d{1,2})\s+de\s+(\w+)(?:\s+de\s+(\d{4}))?", re.IGNORECASE
)


def _fecha_de_grupos(d_str: str, mes_str: str, anyo: int | str) -> date | None:
    try:
        mes = MESES_ES[mes_str.lower()]
        return date(int(anyo), mes, int(d_str))
    except (KeyError, ValueError):
        return None


def _extraer_fecha(texto: str, anyo_circular: int) -> date | None:
    """Intenta extraer una fecha de publicación del texto del item.

    Preferimos la fecha del BOE; si no aparece, usamos la de firma de la
    circular (en cuyo caso el año se infiere del número de circular).
    """
    m = RE_BOE_FECHA.search(texto)
    if m:
        f = _fecha_de_grupos(m.group(1), m.group(2), m.group(3))
        if f:
            return f
    m = RE_FECHA_FIRMA.search(texto)
    if m:
        anyo = m.group(3) or anyo_circular
        return _fecha_de_grupos(m.group(1), m.group(2), anyo)
    return None


def _items(html: str) -> Iterable[dict]:
    soup = BeautifulSoup(html, "html.parser")
    vistos: set[str] = set()
    for li in soup.find_all("li"):
        texto = li.get_text(" ", strip=True)
        m = RE_CIRCULAR.match(texto)
        if not m:
            continue
        numero, anyo = m.group(1), int(m.group(2))
        a = li.find("a", href=True)
        href = a["href"].strip() if a else ""
        if not href:
            continue
        identificador = f"BdE-Circular-{numero}/{anyo}"
        if identificador in vistos:
            continue
        vistos.add(identificador)
        fecha = _extraer_fecha(texto, anyo) or date(anyo, 12, 31)
        yield {
            "identificador": identificador,
            "titulo": texto,
            "url": href,
            "fecha_publicacion": fecha,
            "departamento": "BANCO DE ESPAÑA",
            "seccion": "Circular del Banco de España",
        }


def ingest_circulares(lookback_days: int = 31) -> int:
    """Ingesta circulares del BdE publicadas en los últimos `lookback_days` días."""
    try:
        r = requests.get(URL_INDICE_CIRCULARES, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        log.warning("BdE: error de red al cargar índice: %s", exc)
        return 0
    if r.status_code != 200:
        log.warning("BdE: índice devuelve HTTP %s", r.status_code)
        return 0

    limite = date.today() - timedelta(days=lookback_days)
    nuevas = 0
    for it in _items(r.text):
        if it["fecha_publicacion"] < limite:
            continue
        if db.upsert_publicacion(
            fuente="BDE",
            identificador=it["identificador"],
            titulo=it["titulo"][:1000],  # truncamos defensivamente
            url=it["url"],
            fecha_publicacion=it["fecha_publicacion"].isoformat(),
            departamento=it["departamento"],
            seccion=it["seccion"],
        ):
            nuevas += 1
    if nuevas:
        log.info("BdE: %s circulares nuevas", nuevas)
    return nuevas


def ingest_rango(dias: int = 31) -> int:
    """Alias por simetría con boe.ingest_rango."""
    return ingest_circulares(dias)
