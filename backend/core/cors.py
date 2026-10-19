"""Soporte mínimo de CORS para que la interfaz (index.html) pueda consultar la API
durante el desarrollo. En producción se debe restringir el origen permitido."""
from rest_framework.views import APIView


class CorsAPIView(APIView):
    """Vista base que agrega las cabeceras CORS a todas las respuestas."""

    cors_origin = "*"  # desarrollo; en producción usar el dominio del frontend

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Access-Control-Allow-Origin"] = self.cors_origin
        response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        return response
