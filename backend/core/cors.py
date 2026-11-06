"""Soporte mínimo de CORS para que la interfaz (index.html) pueda consultar la API
durante el desarrollo, y manejo común de errores de base de datos.
En producción se debe restringir el origen permitido."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .db import ConexionBDError


class CorsAPIView(APIView):
    """Vista base: agrega cabeceras CORS y responde 503 si la base de datos falla."""

    cors_origin = "*"  # desarrollo; en producción usar el dominio del frontend

    def handle_exception(self, exc):
        if isinstance(exc, ConexionBDError):
            codigo = status.HTTP_503_SERVICE_UNAVAILABLE if exc.conexion else status.HTTP_500_INTERNAL_SERVER_ERROR
            return Response({"detail": exc.mensaje}, status=codigo)
        return super().handle_exception(exc)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Access-Control-Allow-Origin"] = self.cors_origin
        response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        return response
