"""Listas de palabras/etiquetas para filtrar contenido relevante.

Filosofía conservadora: preferimos un falso positivo (entrada que luego archivamos)
a un falso negativo (norma relevante que se nos escapa). Las listas se pueden
ampliar o recortar con el tiempo según los resultados que veamos.
"""
from __future__ import annotations

import re
import unicodedata


# --- Palabras / expresiones a buscar en el TÍTULO de la publicación. --- #
# Se normalizan (sin tildes, minúsculas) antes de comparar.
KEYWORDS_RAW: list[str] = [
    # Entidades de crédito y figuras afines
    "entidad de credito",
    "entidades de credito",
    "establecimiento financiero de credito",
    "establecimientos financieros de credito",
    "entidades financieras",
    "entidad financiera",
    "sucursal de entidad",
    "sucursales de entidades",
    # Bancos
    "banco",
    "bancos",
    "bancaria",
    "bancario",
    "banca",
    # Supervisión y solvencia
    "solvencia",
    "supervision prudencial",
    "supervision bancaria",
    "fondos propios",
    "ratio de capital",
    "capital regulatorio",
    "requerimientos de capital",
    "requisitos de capital",
    "colchon de capital",
    "apalancamiento",
    "liquidez",
    "lcr",
    "nsfr",
    "mrel",
    "tlac",
    "resolucion bancaria",
    "frob",
    "fondo de garantia de depositos",
    "fgd",
    "deposito de garantia",
    "depositos garantizados",
    # Conducta y consumidores
    "credito al consumo",
    "credito hipotecario",
    "credito inmobiliario",
    "prestamo hipotecario",
    "servicios de pago",
    "dinero electronico",
    # Blanqueo / sanciones
    "blanqueo de capitales",
    "prevencion del blanqueo",
    "sepblac",
    "financiacion del terrorismo",
    "sancion financiera",
    # Reguladores y marcos comunitarios
    "banco de espana",
    "autoridad bancaria europea",
    "european banking authority",
    "banco central europeo",
    "mecanismo unico de supervision",
    "mecanismo unico de resolucion",
    "junta unica de resolucion",
    "directiva 2013/36",  # CRD
    "reglamento 575/2013",  # CRR
    "crr",
    "crd iv",
    "crd v",
    "crd vi",
    "basilea",
    # Mercados y otros conceptos cercanos
    "abuso de mercado",
    "titulizacion",
    "covered bond",
    "cedulas hipotecarias",
    "emision de deuda",
    "instrumentos financieros",
    "mifid",
    "psd2",
    "dora",
    # Sostenibilidad financiera
    "riesgo climatico",
    "sostenibilidad",
    "esg",
]


# --- Departamentos del BOE típicamente relevantes (en mayúsculas tal cual los publica el BOE). --- #
DEPARTAMENTOS_RELEVANTES: set[str] = {
    "BANCO DE ESPAÑA",
    "MINISTERIO DE ECONOMÍA",
    "MINISTERIO DE ECONOMÍA Y EMPRESA",
    "MINISTERIO DE ECONOMÍA Y HACIENDA",
    "MINISTERIO DE ECONOMÍA, COMERCIO Y EMPRESA",
    "MINISTERIO DE ASUNTOS ECONÓMICOS Y TRANSFORMACIÓN DIGITAL",
    "MINISTERIO DE HACIENDA",
    "MINISTERIO DE HACIENDA Y FUNCIÓN PÚBLICA",
    "JEFATURA DEL ESTADO",   # Leyes y reales decretos-ley
    "CORTES GENERALES",
    "PRESIDENCIA DEL GOBIERNO",
    "COMISIÓN NACIONAL DEL MERCADO DE VALORES",
    "TRIBUNAL DE CUENTAS",
}


def _normaliza(texto: str) -> str:
    """Pasa a minúsculas y elimina tildes para comparaciones robustas."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_tildes.lower()


_KEYWORDS_NORM = [_normaliza(k) for k in KEYWORDS_RAW]
_KEYWORD_REGEXES = [re.compile(rf"\b{re.escape(k)}\b") for k in _KEYWORDS_NORM]


def titulo_es_relevante(titulo: str) -> bool:
    """True si el título contiene alguna palabra clave (con frontera de palabra)."""
    norm = _normaliza(titulo)
    return any(rx.search(norm) for rx in _KEYWORD_REGEXES)


def departamento_es_relevante(departamento: str) -> bool:
    if not departamento:
        return False
    return departamento.strip().upper() in DEPARTAMENTOS_RELEVANTES
