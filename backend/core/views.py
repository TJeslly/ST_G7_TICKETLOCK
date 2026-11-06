"""Capa de interfaz HTTP (Fase 4): recibe la petición, valida y responde.

La lógica de negocio está en ``services`` y las consultas en ``repositories``;
la conexión a la base de datos, en ``db``.
"""
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response

from . import db, repositories as repo, services
from .cors import CorsAPIView
from .serializers import (
    AsientoSerializer,
    EventoSerializer,
    LoginSerializer,
    RegistroUsuarioSerializer,
    UsuarioPublicoSerializer,
)


class SaludView(CorsAPIView):
    """GET /api/salud/ — estado de la conexión con PostgreSQL y totales de registros.

    Responde 200 si la base responde y 503 si no. Sirve a la interfaz para mostrar
    el estado de conexión y como prueba rápida de que los datos vienen de la base.
    """

    def get(self, request):
        estado = db.verificar_conexion()
        if not estado["ok"]:
            return Response(estado, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        estado["registros"] = repo.contar_registros()
        return Response(estado)


class EventoListView(CorsAPIView):
    """GET /api/eventos/ — catálogo público de eventos publicados (RF03)."""

    def get(self, request):
        return Response(EventoSerializer(services.listar_eventos(), many=True).data)


class AsientosEventoView(CorsAPIView):
    """GET /api/eventos/<id>/asientos/ — estado de cada asiento del evento (RF04)."""

    def get(self, request, pk):
        evento = repo.evento_publicado(pk)
        if evento is None:
            raise Http404
        return Response(
            {
                "evento": EventoSerializer(evento).data,
                "asientos": AsientoSerializer(services.asientos_ordenados(evento), many=True).data,
            }
        )


class UsuarioCreateView(CorsAPIView):
    """POST /api/usuarios/ — registro de usuario con validaciones (RF01)."""

    def post(self, request):
        serializer = RegistroUsuarioSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        usuario = services.registrar_usuario(serializer.validated_data)
        if usuario is None:
            # Dos registros simultáneos con el mismo correo: la restricción UNIQUE de la BD lo detiene.
            return Response(
                {"email": ["Ya existe una cuenta con este correo."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(UsuarioPublicoSerializer(usuario).data, status=status.HTTP_201_CREATED)


class LoginView(CorsAPIView):
    """POST /api/login/ — verifica credenciales y registra el intento en auditoría (RF02).

    Nota: por ahora no emite token (JWT queda para la siguiente entrega); la interfaz
    solo conserva los datos públicos del usuario durante la sesión del navegador.
    """

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        usuario = services.autenticar(
            serializer.validated_data["email"], serializer.validated_data["password"]
        )
        if usuario is None:
            return Response({"detail": services.MENSAJE_LOGIN}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(UsuarioPublicoSerializer(usuario).data)
