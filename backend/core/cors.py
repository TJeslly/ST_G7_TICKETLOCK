"""Vista base de la API: CORS, autenticación por token y manejo común de errores.

En producción se debe restringir el origen permitido."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import auth
from . import repositories as repo
from .db import ConexionBDError
from .errores import ErrorNegocio


class CorsAPIView(APIView):
    """Agrega cabeceras CORS, valida el token si la vista lo exige y responde errores claros."""

    cors_origin = "*"  # desarrollo; en producción usar el dominio del frontend
    requiere_auth = False
    rol_requerido = None  # p. ej. "ADMIN"
    authentication_classes = []  # la autenticación la maneja auth.py
    permission_classes = []

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.usuario = None
        if self.requiere_auth and request.method != "OPTIONS":
            datos = auth.leer_token(auth.token_de_cabecera(request))
            usuario = repo.usuario_por_id(datos["sub"])
            if usuario is None:
                raise ErrorNegocio("Sesión no válida. Inicia sesión.", 401)
            if self.rol_requerido and usuario.rol != self.rol_requerido:
                raise ErrorNegocio("No tienes permiso para esta acción.", 403)
            self.usuario = usuario

    def handle_exception(self, exc):
        if isinstance(exc, ErrorNegocio):
            return Response({"detail": exc.detalle}, status=exc.estado)
        if isinstance(exc, ConexionBDError):
            codigo = status.HTTP_503_SERVICE_UNAVAILABLE if exc.conexion else status.HTTP_500_INTERNAL_SERVER_ERROR
            return Response({"detail": exc.mensaje}, status=codigo)
        return super().handle_exception(exc)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Access-Control-Allow-Origin"] = self.cors_origin
        response["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response
