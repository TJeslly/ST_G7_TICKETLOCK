"""Capa de lógica de negocio (Fase 4).

Aquí viven las reglas del sistema: cómo se registra un usuario, cómo se verifica un
inicio de sesión y cómo se ordenan los asientos. No conoce HTTP (eso es de las vistas)
ni escribe consultas (eso es de ``repositories``).
"""
import re

from django.contrib.auth.hashers import check_password, make_password

from . import repositories as repo

MENSAJE_LOGIN = "Correo o contraseña incorrectos."


def clave_natural(codigo):
    """Ordena A1, A2, ..., A10 (y no A1, A10, A2)."""
    m = re.match(r"^([A-Za-z]+)(\d+)$", codigo)
    return (m.group(1), int(m.group(2))) if m else (codigo, 0)


def listar_eventos():
    liberar_vencidos()
    return repo.eventos_publicados()


def asientos_ordenados(evento):
    liberar_vencidos()
    return sorted(repo.asientos_de_evento(evento), key=lambda a: clave_natural(a.codigo))


def registrar_usuario(datos):
    """Guarda el usuario con la contraseña cifrada. ``None`` si el correo ya existe."""
    return repo.crear_usuario_con_auditoria(
        nombre=datos["nombre"],
        email=datos["email"],
        password_hash=make_password(datos["password"]),
    )


def autenticar(email, password):
    """Verifica credenciales y deja constancia en auditoría. Devuelve el usuario o None.

    Mismo resultado si el correo no existe o la contraseña falla (no revela cuentas).
    """
    usuario = repo.usuario_por_email(email.strip().lower())
    ok = usuario is not None and check_password(password, usuario.password_hash)
    repo.registrar_auditoria(
        "INICIAR_SESION",
        f"usuarios/{usuario.id}" if usuario else "usuarios/desconocido",
        "SUCCESS" if ok else "DENIED",
    )
    return usuario if ok else None


# ---------------------------------------------------------------------------
# Reserva temporal de asientos (RF05, RF06) y compra atómica (RF07, RF08)
# ---------------------------------------------------------------------------
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .errores import ErrorNegocio


def _cfg(nombre, defecto):
    return getattr(settings, nombre, defecto)


def minutos_bloqueo():
    return _cfg("BLOQUEO_MINUTOS", 5)


def max_boletos():
    return _cfg("MAX_BOLETOS", 4)


def precio_boleto():
    return Decimal(str(_cfg("PRECIO_BOLETO", 180000)))


def liberar_vencidos():
    """Libera los bloqueos cuyo tiempo expiró (RF06). Devuelve cuántos liberó."""
    with transaction.atomic():
        vencidos = repo.bloqueos_vencidos_para_actualizar()
        for b in vencidos:
            repo.liberar_bloqueo(b, "LIBERAR_BLOQUEO_VENCIDO")
        return len(vencidos)


def _id_valido(valor):
    try:
        return str(uuid.UUID(str(valor)))
    except (ValueError, AttributeError):
        raise ErrorNegocio("Identificador no válido.", 400)


def reservar_asiento(usuario, asiento_id):
    """Bloquea un asiento para el usuario durante unos minutos (RF05)."""
    asiento_id = _id_valido(asiento_id)
    try:
        with transaction.atomic():
            return _reservar(usuario, asiento_id)
    except ErrorNegocio:
        repo.registrar_auditoria("BLOQUEAR_ASIENTO", f"asientos/{asiento_id}", "DENIED")
        raise


def _reservar(usuario, asiento_id):
    liberar_vencidos()
    asiento = repo.asiento_para_actualizar(asiento_id)  # SELECT ... FOR UPDATE
    if asiento is None:
        raise ErrorNegocio("El asiento no existe.", 404)
    if asiento.evento.estado != "PUBLICADO":
        raise ErrorNegocio("El evento no está disponible para la venta.", 409)
    if asiento.estado == "VENDIDO":
        raise ErrorNegocio("Ese asiento ya fue vendido.", 409)
    if asiento.estado == "BLOQUEADO":
        actual = repo.bloqueo_de_asiento(asiento)
        if actual and actual.estado == "ACTIVO" and actual.usuario_id == usuario.id:
            return actual  # ya lo tenías reservado: la operación se repite sin efecto
        raise ErrorNegocio("Ese asiento está reservado por otra persona.", 409)
    if repo.contar_bloqueos_vigentes(usuario) >= max_boletos():
        raise ErrorNegocio(f"Solo puedes reservar hasta {max_boletos()} asientos a la vez.", 409)
    expira = timezone.now() + timedelta(minutes=minutos_bloqueo())
    bloqueo = repo.guardar_bloqueo(asiento, usuario, expira)
    repo.cambiar_estado_asiento(asiento, "BLOQUEADO")
    repo.registrar_auditoria("BLOQUEAR_ASIENTO", f"asientos/{asiento.id}", "SUCCESS", bloqueo=bloqueo)
    return bloqueo


def liberar_reserva(usuario, bloqueo_id):
    """El usuario libera su propia reserva antes de que expire."""
    bloqueo_id = _id_valido(bloqueo_id)
    with transaction.atomic():
        bloqueo = repo.bloqueo_por_id(bloqueo_id, para_actualizar=True)
        if bloqueo is None or bloqueo.usuario_id != usuario.id:
            raise ErrorNegocio("La reserva no existe.", 404)
        if bloqueo.estado != "ACTIVO":
            return bloqueo
        repo.liberar_bloqueo(bloqueo, "LIBERAR_BLOQUEO")
        bloqueo.estado = "LIBERADO"
        return bloqueo


def mis_reservas(usuario):
    liberar_vencidos()
    return repo.bloqueos_vigentes_de_usuario(usuario)


def comprar(usuario, asiento_ids):
    """Confirma la compra de asientos reservados por el usuario (RF07, RF08).

    Todo ocurre en UNA transacción: se verifican las reservas, se crea la compra con
    su detalle, los asientos pasan a VENDIDO y se audita. Si algo falla, no queda nada
    a medias. Repetir la misma petición devuelve la compra ya hecha, sin cobrar dos veces.
    Devuelve ``(solicitud, creada)``.
    """
    if not isinstance(asiento_ids, list) or not asiento_ids:
        raise ErrorNegocio("Selecciona al menos un asiento.", 400)
    ids = sorted({_id_valido(i) for i in asiento_ids})
    if len(ids) > max_boletos():
        raise ErrorNegocio(f"Máximo {max_boletos()} boletos por compra.", 400)
    try:
        with transaction.atomic():
            return _comprar(usuario, ids)
    except ErrorNegocio:
        repo.registrar_auditoria("CONFIRMAR_COMPRA", f"usuarios/{usuario.id}", "DENIED")
        raise


def _comprar(usuario, ids):
    liberar_vencidos()
    asientos = repo.asientos_para_actualizar(ids)  # SELECT ... FOR UPDATE, en orden fijo
    if len(asientos) != len(ids):
        raise ErrorNegocio("Alguno de los asientos no existe.", 404)
    previa = repo.solicitud_de_asientos_vendidos(asientos)
    if previa is not None:
        if previa.usuario_id == usuario.id:
            return previa, False  # idempotencia: ya estaba comprada
        raise ErrorNegocio("Esos asientos ya fueron vendidos.", 409)
    for a in asientos:
        if a.evento.estado != "PUBLICADO":
            raise ErrorNegocio("El evento no está disponible para la venta.", 409)
        if a.estado != "BLOQUEADO":
            raise ErrorNegocio(f"El asiento {a.codigo} no está reservado; vuelve a seleccionarlo.", 409)
        b = repo.bloqueo_de_asiento(a)
        if b is None or b.estado != "ACTIVO" or b.usuario_id != usuario.id:
            raise ErrorNegocio(f"El asiento {a.codigo} no está reservado a tu nombre.", 409)
        if b.fecha_expiracion <= timezone.now():
            raise ErrorNegocio(f"La reserva del asiento {a.codigo} expiró.", 409)
    solicitud = repo.crear_compra(usuario, asientos, precio_boleto())
    repo.registrar_auditoria("CONFIRMAR_COMPRA", f"solicitudes_compra/{solicitud.id}", "SUCCESS", solicitud=solicitud)
    return solicitud, True


def mis_compras(usuario):
    return repo.compras_de_usuario(usuario)


# ---------------------------------------------------------------------------
# Administración de eventos (RF11–RF13)
# ---------------------------------------------------------------------------
ESTADOS_EVENTO = ("BORRADOR", "PUBLICADO", "CERRADO", "CANCELADO")


def crear_evento(datos):
    filas, columnas = datos["filas"], datos["columnas"]
    codigos = [f"{chr(65 + f)}{c}" for f in range(filas) for c in range(1, columnas + 1)]
    return repo.crear_evento_con_asientos(
        datos["nombre"], datos["fecha"], datos["lugar"], datos.get("estado", "PUBLICADO"), codigos
    )


def cambiar_estado_evento(evento_id, estado):
    if estado not in ESTADOS_EVENTO:
        raise ErrorNegocio("Estado no válido.", 400)
    evento = repo.evento_por_id(evento_id)
    if evento is None:
        raise ErrorNegocio("El evento no existe.", 404)
    return repo.cambiar_estado_evento(evento, estado)


# ---------------------------------------------------------------------------
# Perfil del usuario
# ---------------------------------------------------------------------------
def actualizar_perfil(usuario, datos):
    """Cambia nombre, correo y/o contraseña. Para cambiar la contraseña exige la actual."""
    nuevo_hash = None
    if "password_nueva" in datos:
        if not check_password(datos["password_actual"], usuario.password_hash):
            repo.registrar_auditoria("ACTUALIZAR_PERFIL", f"usuarios/{usuario.id}", "DENIED")
            raise ErrorNegocio("La contraseña actual es incorrecta.", 400)
        nuevo_hash = make_password(datos["password_nueva"])
    actualizado = repo.actualizar_usuario(
        usuario, nombre=datos.get("nombre"), email=datos.get("email"), password_hash=nuevo_hash
    )
    if actualizado is None:
        raise ErrorNegocio("Ya existe una cuenta con este correo.", 400)
    return actualizado
