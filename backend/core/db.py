"""Módulo independiente de conexión a la base de datos (Fase 4).

La configuración vive en ``ticketlock/settings.py`` y se alimenta de variables de
entorno (``DB_NAME``, ``DB_USER``, ``DB_PASSWORD``, ``DB_HOST``, ``DB_PORT``) o del
archivo local ``.env``, que no se sube a Git. Este módulo concentra todo lo que la
aplicación necesita saber sobre la conexión, para que el resto del código no
dependa de detalles del motor:

* ``verificar_conexion()``  comprueba que PostgreSQL responde y mide la latencia.
* ``estadisticas()``        cuenta los registros principales (consulta de datos).
* ``ConexionBDError``       error propio con un mensaje apto para el usuario.
* ``proteger_bd``           decorador que traduce los fallos del motor a ``ConexionBDError``.

Por seguridad, nada de lo que devuelve incluye usuario ni contraseña de la base.
"""
import functools
import logging
import time

from django.db import DatabaseError, OperationalError, connection

logger = logging.getLogger(__name__)

MENSAJE_SIN_CONEXION = (
    "No se pudo conectar con la base de datos. Verifica que PostgreSQL esté en "
    "ejecución y que las variables de entorno (.env) sean correctas."
)
MENSAJE_FALLO_OPERACION = "La operación no se pudo completar en la base de datos. Intenta de nuevo."


class ConexionBDError(Exception):
    """Fallo de conexión u operación contra la base de datos."""

    def __init__(self, mensaje=MENSAJE_SIN_CONEXION, *, conexion=True):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.conexion = conexion  # True: no hay conexión; False: falló la operación


def verificar_conexion():
    """Abre la conexión (si hace falta) y ejecuta ``SELECT 1``.

    Devuelve un diccionario con ``ok``, ``motor``, ``base`` y ``latencia_ms``.
    Si falla, ``ok`` es False y ``detalle`` trae el mensaje para el usuario.
    """
    inicio = time.perf_counter()
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except DatabaseError as exc:
        logger.warning("Verificación de conexión fallida: %s", exc.__class__.__name__)
        return {"ok": False, "motor": connection.vendor, "detalle": MENSAJE_SIN_CONEXION}
    return {
        "ok": True,
        "motor": connection.vendor,
        "base": connection.settings_dict.get("NAME"),
        "latencia_ms": round((time.perf_counter() - inicio) * 1000, 1),
    }


def proteger_bd(funcion):
    """Convierte los errores del motor en ``ConexionBDError`` con mensaje claro."""

    @functools.wraps(funcion)
    def envoltura(*args, **kwargs):
        try:
            return funcion(*args, **kwargs)
        except OperationalError as exc:
            logger.error("Base de datos no disponible: %s", exc.__class__.__name__)
            raise ConexionBDError(MENSAJE_SIN_CONEXION) from exc
        except DatabaseError as exc:
            logger.error("Operación fallida en la base de datos: %s", exc.__class__.__name__)
            raise ConexionBDError(MENSAJE_FALLO_OPERACION, conexion=False) from exc

    return envoltura
