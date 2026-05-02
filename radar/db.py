"""Capa de acceso a datos sobre SQLAlchemy Core.

Soporta tanto SQLite (desarrollo local) como PostgreSQL (Render) según el valor
de DATABASE_URL. La API publica (init_db, upsert_publicacion, listar_*, ...)
se mantiene tal cual para que el resto del codigo no se entere del cambio.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Index, Integer, MetaData, String, Table, Text,
    UniqueConstraint, and_, create_engine, select,
)
from sqlalchemy.exc import IntegrityError

from config import config

# --------------------------------- engine -------------------------------- #

_engine_kwargs: dict[str, Any] = {"future": True}
if config.database_url.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_pre_ping"] = True

engine = create_engine(config.database_url, **_engine_kwargs)
metadata = MetaData()


# --------------------------------- tablas -------------------------------- #

publicaciones = Table(
    "publicaciones", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("fuente", String(16), nullable=False),
    Column("identificador", String(120), nullable=False),
    Column("titulo", Text, nullable=False),
    Column("url", Text, nullable=False),
    Column("departamento", Text),
    Column("seccion", Text),
    Column("fecha_publicacion", String(16), nullable=False),
    Column("fecha_deteccion", DateTime(timezone=True), nullable=False),
    Column("archivada", Boolean, nullable=False, server_default="0"),
    Column("fecha_archivado", DateTime(timezone=True)),
    UniqueConstraint("fuente", "identificador", name="uq_publicacion_fuente_id"),
)
Index("idx_pub_fecha", publicaciones.c.fecha_publicacion.desc())
Index("idx_pub_archivada", publicaciones.c.archivada, publicaciones.c.fecha_publicacion.desc())


suscriptores = Table(
    "suscriptores", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String(254), nullable=False, unique=True),
    Column("activo", Boolean, nullable=False, server_default="1"),
    Column("token_baja", String(80), nullable=False, unique=True),
    Column("fecha_alta", DateTime(timezone=True), nullable=False),
    Column("fecha_consentimiento", DateTime(timezone=True), nullable=False),
    Column("fecha_baja", DateTime(timezone=True)),
)


# ------------------------------- inicializacion ------------------------------ #

def init_db() -> None:
    metadata.create_all(engine)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_dict(row) -> dict[str, Any]:
    if row is None:
        return None  # type: ignore[return-value]
    return dict(row._mapping)


# ------------------------------ publicaciones ------------------------------ #

def upsert_publicacion(
    fuente: str,
    identificador: str,
    titulo: str,
    url: str,
    fecha_publicacion: str,
    departamento: Optional[str] = None,
    seccion: Optional[str] = None,
) -> bool:
    valores = {
        "fuente": fuente,
        "identificador": identificador,
        "titulo": titulo,
        "url": url,
        "departamento": departamento,
        "seccion": seccion,
        "fecha_publicacion": fecha_publicacion,
        "fecha_deteccion": _utcnow(),
        "archivada": False,
    }
    try:
        with engine.begin() as conn:
            conn.execute(publicaciones.insert().values(**valores))
        return True
    except IntegrityError:
        return False


def listar_publicaciones(archivadas: bool, dias: int = 92) -> list[dict[str, Any]]:
    desde = (datetime.now(timezone.utc) - timedelta(days=dias)).date().isoformat()
    with engine.connect() as conn:
        if archivadas:
            stmt = (
                select(publicaciones)
                .where(publicaciones.c.archivada.is_(True))
                .order_by(publicaciones.c.fecha_publicacion.desc(),
                          publicaciones.c.id.desc())
            )
        else:
            stmt = (
                select(publicaciones)
                .where(and_(publicaciones.c.archivada.is_(False),
                            publicaciones.c.fecha_publicacion >= desde))
                .order_by(publicaciones.c.fecha_publicacion.desc(),
                          publicaciones.c.id.desc())
            )
        return [_row_to_dict(r) for r in conn.execute(stmt).fetchall()]


def publicaciones_ultimas_horas(horas: int = 24) -> list[dict[str, Any]]:
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)
    with engine.connect() as conn:
        stmt = (
            select(publicaciones)
            .where(publicaciones.c.fecha_deteccion >= desde)
            .order_by(publicaciones.c.fecha_publicacion.desc(),
                      publicaciones.c.id.desc())
        )
        return [_row_to_dict(r) for r in conn.execute(stmt).fetchall()]


def archivar(pub_id: int, archivar_flag: bool = True) -> None:
    ahora = _utcnow() if archivar_flag else None
    with engine.begin() as conn:
        conn.execute(
            publicaciones.update()
            .where(publicaciones.c.id == pub_id)
            .values(archivada=archivar_flag, fecha_archivado=ahora)
        )


def get_publicacion(pub_id: int) -> Optional[dict[str, Any]]:
    with engine.connect() as conn:
        row = conn.execute(
            select(publicaciones).where(publicaciones.c.id == pub_id)
        ).fetchone()
    return _row_to_dict(row) if row else None


# ------------------------------- suscriptores ------------------------------- #

def alta_suscriptor(email: str, token_baja: str) -> bool:
    ahora = _utcnow()
    with engine.begin() as conn:
        existente = conn.execute(
            select(suscriptores).where(suscriptores.c.email == email)
        ).fetchone()
        if existente:
            existente_d = dict(existente._mapping)
            if existente_d["activo"]:
                return False
            conn.execute(
                suscriptores.update()
                .where(suscriptores.c.id == existente_d["id"])
                .values(
                    activo=True,
                    fecha_alta=ahora,
                    fecha_consentimiento=ahora,
                    fecha_baja=None,
                    token_baja=token_baja,
                )
            )
            return True
        conn.execute(
            suscriptores.insert().values(
                email=email,
                activo=True,
                token_baja=token_baja,
                fecha_alta=ahora,
                fecha_consentimiento=ahora,
            )
        )
        return True


def baja_por_token(token: str) -> Optional[str]:
    ahora = _utcnow()
    with engine.begin() as conn:
        row = conn.execute(
            select(suscriptores.c.id, suscriptores.c.email).where(
                and_(suscriptores.c.token_baja == token,
                     suscriptores.c.activo.is_(True))
            )
        ).fetchone()
        if not row:
            return None
        sus_id, sus_email = row[0], row[1]
        conn.execute(
            suscriptores.update()
            .where(suscriptores.c.id == sus_id)
            .values(activo=False, fecha_baja=ahora)
        )
        return sus_email


def listar_suscriptores_activos() -> list[dict[str, Any]]:
    with engine.connect() as conn:
        stmt = (
            select(suscriptores)
            .where(suscriptores.c.activo.is_(True))
            .order_by(suscriptores.c.fecha_alta)
        )
        return [_row_to_dict(r) for r in conn.execute(stmt).fetchall()]
