"""Token de sesión firmado (HS256, formato JWT) sin dependencias externas.

El token lleva el id del usuario, su rol y la fecha de expiración, y se firma con la
``SECRET_KEY`` de Django. Se envía en la cabecera ``Authorization: Bearer <token>``.
"""
import base64
import hashlib
import hmac
import json
import time

from django.conf import settings

from .errores import ErrorNegocio

DURACION_SEGUNDOS = 2 * 60 * 60  # 2 horas


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


def _b64d(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _firma(mensaje: str) -> str:
    clave = settings.SECRET_KEY.encode()
    return _b64(hmac.new(clave, mensaje.encode(), hashlib.sha256).digest())


def crear_token(usuario, segundos=DURACION_SEGUNDOS):
    cabecera = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    cuerpo = _b64(
        json.dumps({"sub": str(usuario.id), "rol": usuario.rol, "exp": int(time.time()) + segundos}).encode()
    )
    mensaje = f"{cabecera}.{cuerpo}"
    return f"{mensaje}.{_firma(mensaje)}"


def leer_token(token):
    """Devuelve el contenido del token o lanza ``ErrorNegocio(401)``."""
    try:
        cabecera, cuerpo, firma = token.split(".")
        if not hmac.compare_digest(firma, _firma(f"{cabecera}.{cuerpo}")):
            raise ValueError("firma")
        datos = json.loads(_b64d(cuerpo))
        if datos["exp"] < time.time():
            raise ErrorNegocio("La sesión expiró. Inicia sesión de nuevo.", 401)
        return datos
    except ErrorNegocio:
        raise
    except Exception:
        raise ErrorNegocio("Sesión no válida. Inicia sesión.", 401)


def token_de_cabecera(request):
    valor = request.headers.get("Authorization", "")
    if not valor.startswith("Bearer "):
        raise ErrorNegocio("Debes iniciar sesión para continuar.", 401)
    return valor[7:].strip()
