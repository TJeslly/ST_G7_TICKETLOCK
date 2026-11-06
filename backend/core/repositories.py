"""Capa de acceso a datos (Fase 4).

Es la única capa que construye consultas con el ORM. Las vistas (interfaz HTTP) y los
servicios (lógica de negocio) piden aquí lo que necesitan y no tocan los modelos
directamente. Cada función está protegida con ``proteger_bd``: si PostgreSQL no
responde, lanza ``ConexionBDError`` en lugar de un error técnico del motor.
"""
from django.db import IntegrityError, transaction

from .db import proteger_bd
from .models import Asiento, Auditoria, Evento, SolicitudCompra, Usuario


@proteger_bd
def eventos_publicados():
    return list(Evento.objects.filter(estado="PUBLICADO").order_by("fecha"))


@proteger_bd
def evento_publicado(pk):
    return Evento.objects.filter(pk=pk, estado="PUBLICADO").first()


@proteger_bd
def asientos_de_evento(evento):
    return list(evento.asientos.all())


@proteger_bd
def usuario_por_email(email):
    return Usuario.objects.filter(email__iexact=email).first()


@proteger_bd
def existe_email(email):
    return Usuario.objects.filter(email__iexact=email).exists()


@proteger_bd
def registrar_auditoria(accion, recurso, resultado):
    return Auditoria.objects.create(accion=accion, recurso=recurso, resultado=resultado)


@proteger_bd
def crear_usuario_con_auditoria(nombre, email, password_hash):
    """Inserta el usuario y su registro de auditoría en una sola transacción.

    Devuelve ``None`` si el correo ya existe (restricción UNIQUE de la base).
    Los resultados de auditoría usan los valores que admite el CHECK de la tabla
    (SUCCESS, DENIED, ERROR).
    """
    try:
        with transaction.atomic():
            usuario = Usuario.objects.create(
                nombre=nombre, email=email, password_hash=password_hash, rol="USUARIO"
            )
            Auditoria.objects.create(
                accion="REGISTRAR_USUARIO", recurso=f"usuarios/{usuario.id}", resultado="SUCCESS"
            )
    except IntegrityError as exc:
        # Solo la restricción UNIQUE del correo se informa como "correo duplicado";
        # cualquier otra violación es un fallo de la operación y no debe disfrazarse.
        texto = str(exc).lower()
        if "unique" in texto and "email" in texto:
            return None
        raise
    return usuario


@proteger_bd
def contar_registros():
    """Totales de las tablas principales (no expone datos personales)."""
    return {
        "eventos": Evento.objects.count(),
        "asientos": Asiento.objects.count(),
        "usuarios": Usuario.objects.count(),
        "solicitudes_compra": SolicitudCompra.objects.count(),
    }
