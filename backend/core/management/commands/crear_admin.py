from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from core.models import Usuario


class Command(BaseCommand):
    help = "Crea (o actualiza) un usuario administrador. Uso: python manage.py crear_admin correo@dominio.com Clave1234"

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("password")
        parser.add_argument("--nombre", default="Administrador TicketLock")

    def handle(self, *args, **o):
        if len(o["password"]) < 8:
            raise CommandError("La contraseña debe tener al menos 8 caracteres.")
        u, creado = Usuario.objects.update_or_create(
            email=o["email"].strip().lower(),
            defaults={"nombre": o["nombre"], "rol": "ADMIN", "password_hash": make_password(o["password"])},
        )
        self.stdout.write(("Administrador creado: " if creado else "Administrador actualizado: ") + u.email)
