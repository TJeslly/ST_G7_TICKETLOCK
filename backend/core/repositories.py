"""Capa de acceso a datos (Fase 4).

Es la única capa que construye consultas con el ORM. Las vistas (interfaz HTTP) y los
servicios (lógica de negocio) piden aquí lo que necesitan y no tocan los modelos
directamente. Cada función está protegida con ``proteger_bd``: si PostgreSQL no
responde, lanza ``ConexionBDError`` en lugar de un error técnico del motor.
"""
from django.db import IntegrityError, transaction
from django.utils import timezone

from .db import proteger_bd
from .models import Asiento, Auditoria, Bloqueo, DetalleCompra, Evento, SolicitudCompra, Usuario


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
def usuario_por_id(pk):
    try:
        return Usuario.objects.filter(pk=pk).first()
    except (ValueError, TypeError):
        return None


@proteger_bd
def registrar_auditoria(accion, recurso, resultado, solicitud=None, bloqueo=None):
    return Auditoria.objects.create(
        accion=accion, recurso=recurso, resultado=resultado, solicitud=solicitud, bloqueo=bloqueo
    )


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


# ---------------------------------------------------------------------------
# Reservas (bloqueos) y compras. Las funciones con "para_actualizar" toman un
# bloqueo de fila (SELECT ... FOR UPDATE) y deben llamarse dentro de una
# transacción: así dos personas no pueden modificar el mismo asiento a la vez.
# ---------------------------------------------------------------------------


@proteger_bd
def asiento_para_actualizar(pk):
    try:
        return Asiento.objects.select_for_update(of=("self",)).select_related("evento").filter(pk=pk).first()
    except (ValueError, TypeError):
        return None


@proteger_bd
def asientos_para_actualizar(ids):
    """Bloquea varios asientos siempre en el mismo orden (evita interbloqueos)."""
    return list(
        Asiento.objects.select_for_update(of=("self",)).select_related("evento").filter(pk__in=ids).order_by("pk")
    )


@proteger_bd
def bloqueo_de_asiento(asiento):
    return Bloqueo.objects.filter(asiento=asiento).first()


@proteger_bd
def contar_bloqueos_vigentes(usuario):
    return Bloqueo.objects.filter(usuario=usuario, estado="ACTIVO", fecha_expiracion__gt=timezone.now()).count()


@proteger_bd
def guardar_bloqueo(asiento, usuario, expira):
    """Crea el bloqueo del asiento o renueva el existente (hay uno solo por asiento)."""
    ahora = timezone.now()
    existente = Bloqueo.objects.filter(asiento=asiento).first()
    if existente is None:
        return Bloqueo.objects.create(asiento=asiento, usuario=usuario, fecha_expiracion=expira)
    Bloqueo.objects.filter(pk=existente.pk).update(
        usuario=usuario, fecha_inicio=ahora, fecha_expiracion=expira, estado="ACTIVO"
    )
    existente.refresh_from_db()
    return existente


@proteger_bd
def cambiar_estado_asiento(asiento, estado):
    Asiento.objects.filter(pk=asiento.pk).update(estado=estado)
    asiento.estado = estado


@proteger_bd
def bloqueo_por_id(pk, para_actualizar=False):
    qs = Bloqueo.objects.select_related("asiento__evento")
    if para_actualizar:
        qs = qs.select_for_update(of=("self",))
    try:
        return qs.filter(pk=pk).first()
    except (ValueError, TypeError):
        return None


@proteger_bd
def liberar_bloqueo(bloqueo, motivo_accion):
    """Marca el bloqueo como liberado, devuelve el asiento a DISPONIBLE y lo audita."""
    Bloqueo.objects.filter(pk=bloqueo.pk).update(estado="LIBERADO")
    Asiento.objects.filter(pk=bloqueo.asiento_id).update(estado="DISPONIBLE")
    Auditoria.objects.create(
        accion=motivo_accion, recurso=f"asientos/{bloqueo.asiento_id}", resultado="SUCCESS", bloqueo=bloqueo
    )


@proteger_bd
def bloqueos_vencidos_para_actualizar():
    return list(
        Bloqueo.objects.select_for_update(skip_locked=True, of=("self",)).filter(
            estado="ACTIVO", fecha_expiracion__lte=timezone.now()
        )
    )


@proteger_bd
def bloqueos_vigentes_de_usuario(usuario):
    return list(
        Bloqueo.objects.select_related("asiento__evento")
        .filter(usuario=usuario, estado="ACTIVO", fecha_expiracion__gt=timezone.now())
        .order_by("fecha_expiracion")
    )


@proteger_bd
def crear_compra(usuario, asientos, precio):
    solicitud = SolicitudCompra.objects.create(usuario=usuario, estado="CONFIRMADA", total=precio * len(asientos))
    for a in asientos:
        DetalleCompra.objects.create(solicitud=solicitud, asiento=a, precio_unitario=precio)
        Asiento.objects.filter(pk=a.pk).update(estado="VENDIDO")
        a.estado = "VENDIDO"
        Bloqueo.objects.filter(asiento=a).update(estado="CONFIRMADO")
    return solicitud


@proteger_bd
def solicitud_de_asientos_vendidos(asientos):
    """Si todos los asientos ya se vendieron en UNA misma solicitud, la devuelve."""
    detalles = list(DetalleCompra.objects.select_related("solicitud").filter(asiento__in=asientos))
    if len(detalles) != len(asientos):
        return None
    solicitudes = {d.solicitud_id for d in detalles}
    return detalles[0].solicitud if len(solicitudes) == 1 else None


@proteger_bd
def compras_de_usuario(usuario):
    return list(
        SolicitudCompra.objects.filter(usuario=usuario)
        .prefetch_related("detalles__asiento__evento")
        .order_by("-fecha_hora")
    )


@proteger_bd
def detalle_de_solicitud(solicitud):
    return list(solicitud.detalles.select_related("asiento__evento").all())


@proteger_bd
def todos_los_eventos():
    return list(Evento.objects.order_by("fecha"))


@proteger_bd
def evento_por_id(pk):
    try:
        return Evento.objects.filter(pk=pk).first()
    except (ValueError, TypeError):
        return None


@proteger_bd
def crear_evento_con_asientos(nombre, fecha, lugar, estado, codigos):
    with transaction.atomic():
        evento = Evento.objects.create(nombre=nombre, fecha=fecha, lugar=lugar, estado=estado)
        Asiento.objects.bulk_create([Asiento(evento=evento, codigo=c) for c in codigos])
        Auditoria.objects.create(accion="CREAR_EVENTO", recurso=f"eventos/{evento.id}", resultado="SUCCESS")
    return evento


@proteger_bd
def cambiar_estado_evento(evento, estado):
    with transaction.atomic():
        Evento.objects.filter(pk=evento.pk).update(estado=estado)
        evento.estado = estado
        Auditoria.objects.create(accion="CAMBIAR_ESTADO_EVENTO", recurso=f"eventos/{evento.id}", resultado="SUCCESS")
    return evento


@proteger_bd
def auditoria_reciente(limite=50):
    return list(Auditoria.objects.order_by("-id")[:limite])


@proteger_bd
def actualizar_usuario(usuario, nombre=None, email=None, password_hash=None):
    """Actualiza el perfil y registra la auditoría en una sola transacción.

    Devuelve ``None`` si el correo nuevo ya lo tiene otra cuenta (restricción UNIQUE).
    """
    try:
        with transaction.atomic():
            campos = {}
            if nombre is not None:
                campos["nombre"] = nombre
            if email is not None:
                campos["email"] = email
            if password_hash is not None:
                campos["password_hash"] = password_hash
            Usuario.objects.filter(pk=usuario.pk).update(**campos)
            Auditoria.objects.create(
                accion="ACTUALIZAR_PERFIL", recurso=f"usuarios/{usuario.pk}", resultado="SUCCESS"
            )
    except IntegrityError as exc:
        texto = str(exc).lower()
        if "unique" in texto and "email" in texto:
            return None
        raise
    usuario.refresh_from_db()
    return usuario
