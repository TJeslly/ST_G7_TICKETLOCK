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
    return repo.eventos_publicados()


def asientos_ordenados(evento):
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
