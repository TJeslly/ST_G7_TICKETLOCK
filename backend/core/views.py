import re

from django.contrib.auth.hashers import check_password
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from .cors import CorsAPIView
from .models import Auditoria, Evento, Usuario
from .serializers import (
    AsientoSerializer,
    EventoSerializer,
    LoginSerializer,
    RegistroUsuarioSerializer,
    UsuarioPublicoSerializer,
)


def _clave_natural(codigo):
    """Ordena A1, A2, ..., A10 (y no A1, A10, A2)."""
    m = re.match(r"^([A-Za-z]+)(\d+)$", codigo)
    return (m.group(1), int(m.group(2))) if m else (codigo, 0)


class EventoListView(CorsAPIView):
    """GET /api/eventos/ — catálogo público de eventos publicados (RF03)."""

    def get(self, request):
        eventos = Evento.objects.filter(estado="PUBLICADO").order_by("fecha")
        return Response(EventoSerializer(eventos, many=True).data)


class AsientosEventoView(CorsAPIView):
    """GET /api/eventos/<id>/asientos/ — estado de cada asiento del evento (RF04)."""

    def get(self, request, pk):
        evento = get_object_or_404(Evento, pk=pk, estado="PUBLICADO")
        asientos = sorted(evento.asientos.all(), key=lambda a: _clave_natural(a.codigo))
        return Response(
            {
                "evento": EventoSerializer(evento).data,
                "asientos": AsientoSerializer(asientos, many=True).data,
            }
        )


class UsuarioCreateView(CorsAPIView):
    """POST /api/usuarios/ — registro de usuario con validaciones (RF01)."""

    def post(self, request):
        serializer = RegistroUsuarioSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                usuario = serializer.save()
                Auditoria.objects.create(
                    accion="REGISTRAR_USUARIO",
                    recurso=f"usuarios/{usuario.id}",
                    resultado="OK",
                )
        except IntegrityError:
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

    MENSAJE = "Correo o contraseña incorrectos."

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"].strip().lower()
        password = serializer.validated_data["password"]
        usuario = Usuario.objects.filter(email__iexact=email).first()
        # Mismo mensaje si el correo no existe o la contraseña falla (no revela cuentas).
        ok = usuario is not None and check_password(password, usuario.password_hash)

        Auditoria.objects.create(
            accion="INICIAR_SESION",
            recurso=f"usuarios/{usuario.id}" if usuario else "usuarios/desconocido",
            resultado="OK" if ok else "FALLIDO",
        )
        if not ok:
            return Response({"detail": self.MENSAJE}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(UsuarioPublicoSerializer(usuario).data)
