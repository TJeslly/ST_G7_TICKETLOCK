"""Capa de interfaz HTTP (Fase 4): recibe la petición, valida y responde.

La lógica de negocio está en ``services`` y las consultas en ``repositories``;
la conexión a la base de datos, en ``db``.
"""
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response

from . import db, repositories as repo, services
from .cors import CorsAPIView
from . import auth
from .errores import ErrorNegocio
from .serializers import (
    AsientoSerializer,
    CompraInSerializer,
    EventoAdminSerializer,
    EventoSerializer,
    LoginSerializer,
    PerfilSerializer,
    RegistroUsuarioSerializer,
    ReservaInSerializer,
    UsuarioPublicoSerializer,
    bloqueo_a_dict,
    compra_a_dict,
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

    Devuelve los datos públicos del usuario y un token firmado (JWT) que la interfaz
    envía en la cabecera ``Authorization: Bearer`` en las operaciones protegidas.
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
        datos = UsuarioPublicoSerializer(usuario).data
        datos["token"] = auth.crear_token(usuario)
        return Response(datos)


class ReservaCreateView(CorsAPIView):
    """POST /api/reservas/ — bloquea un asiento unos minutos para el usuario (RF05)."""

    requiere_auth = True

    def post(self, request):
        serializer = ReservaInSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        bloqueo = services.reservar_asiento(self.usuario, serializer.validated_data["asiento_id"])
        bloqueo = repo.bloqueo_por_id(bloqueo.id)
        return Response(bloqueo_a_dict(bloqueo), status=status.HTTP_201_CREATED)


class MisReservasView(CorsAPIView):
    """GET /api/reservas/mias/ — reservas vigentes del usuario (con su hora de expiración)."""

    requiere_auth = True

    def get(self, request):
        return Response([bloqueo_a_dict(b) for b in services.mis_reservas(self.usuario)])


class ReservaDetailView(CorsAPIView):
    """DELETE /api/reservas/<id>/ — el usuario libera su reserva antes de que expire."""

    requiere_auth = True

    def delete(self, request, pk):
        services.liberar_reserva(self.usuario, pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CompraView(CorsAPIView):
    """POST /api/compras/ — confirma la compra de los asientos reservados (RF07, RF08).
    GET /api/compras/ — historial de compras del usuario (RF09)."""

    requiere_auth = True

    def post(self, request):
        serializer = CompraInSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        solicitud, creada = services.comprar(
            self.usuario, [str(i) for i in serializer.validated_data["asiento_ids"]]
        )
        datos = compra_a_dict(solicitud, repo.detalle_de_solicitud(solicitud))
        datos["ya_procesada"] = not creada
        return Response(datos, status=status.HTTP_201_CREATED if creada else status.HTTP_200_OK)

    def get(self, request):
        return Response([compra_a_dict(c, list(c.detalles.all())) for c in services.mis_compras(self.usuario)])


class AdminEventosView(CorsAPIView):
    """GET/POST /api/admin/eventos/ — listar todos los eventos y crear uno (solo ADMIN)."""

    requiere_auth = True
    rol_requerido = "ADMIN"

    def get(self, request):
        return Response(EventoSerializer(repo.todos_los_eventos(), many=True).data)

    def post(self, request):
        serializer = EventoAdminSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        evento = services.crear_evento(serializer.validated_data)
        return Response(EventoSerializer(evento).data, status=status.HTTP_201_CREATED)


class AdminEventoDetailView(CorsAPIView):
    """PATCH /api/admin/eventos/<id>/ — publicar, cerrar o cancelar un evento (solo ADMIN)."""

    requiere_auth = True
    rol_requerido = "ADMIN"

    def patch(self, request, pk):
        evento = services.cambiar_estado_evento(pk, request.data.get("estado"))
        return Response(EventoSerializer(evento).data)


class AdminAuditoriaView(CorsAPIView):
    """GET /api/admin/auditoria/ — últimos 50 registros de auditoría (RF15, solo ADMIN)."""

    requiere_auth = True
    rol_requerido = "ADMIN"

    def get(self, request):
        return Response(
            [
                {"id": a.id, "accion": a.accion, "recurso": a.recurso, "resultado": a.resultado,
                 "fecha_hora": a.fecha_hora.isoformat()}
                for a in repo.auditoria_reciente()
            ]
        )


class PerfilView(CorsAPIView):
    """GET /api/perfil/ — datos del usuario con sesión iniciada.
    PATCH /api/perfil/ — modifica nombre, correo o contraseña (esta última exige la actual)."""

    requiere_auth = True

    def get(self, request):
        return Response(UsuarioPublicoSerializer(self.usuario).data)

    def patch(self, request):
        serializer = PerfilSerializer(data=request.data, context={"usuario": self.usuario})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        usuario = services.actualizar_perfil(self.usuario, serializer.validated_data)
        return Response(UsuarioPublicoSerializer(usuario).data)
