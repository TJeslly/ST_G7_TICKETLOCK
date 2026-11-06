"""Borra los datos de prueba: compras, reservas y auditoría, y libera los asientos.

    python manage.py limpiar_datos_prueba              # conserva los usuarios
    python manage.py limpiar_datos_prueba --usuarios   # además borra los usuarios normales (conserva ADMIN)
    python manage.py limpiar_datos_prueba --si         # sin pedir confirmación

Todo ocurre en una sola transacción: o se borra todo o no se borra nada.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Asiento, Auditoria, Bloqueo, DetalleCompra, SolicitudCompra, Usuario


class Command(BaseCommand):
    help = "Borra compras, reservas y auditoría de prueba y deja todos los asientos disponibles."

    def add_arguments(self, parser):
        parser.add_argument("--usuarios", action="store_true", help="Borra también los usuarios que no son ADMIN.")
        parser.add_argument("--si", action="store_true", help="No pide confirmación.")

    def handle(self, *args, **opciones):
        aviso = "Se borrarán TODAS las compras, reservas y registros de auditoría y los asientos quedarán disponibles"
        if opciones["usuarios"]:
            aviso += ", y los usuarios que no sean ADMIN"
        self.stdout.write(self.style.WARNING(aviso + ". Esto no se puede deshacer."))
        if not opciones["si"] and input("Escribe SI para continuar: ").strip().upper() != "SI":
            self.stdout.write("Cancelado. No se borró nada.")
            return
        with transaction.atomic():
            n_aud = Auditoria.objects.all().delete()[0]
            n_det = DetalleCompra.objects.all().delete()[0]
            n_com = SolicitudCompra.objects.all().delete()[0]
            n_blo = Bloqueo.objects.all().delete()[0]
            n_asi = Asiento.objects.exclude(estado="DISPONIBLE").update(estado="DISPONIBLE")
            n_usu = Usuario.objects.exclude(rol="ADMIN").delete()[0] if opciones["usuarios"] else 0
        self.stdout.write(self.style.SUCCESS(
            f"Listo. Compras: {n_com} · boletos: {n_det} · reservas: {n_blo} · auditoría: {n_aud} · "
            f"asientos liberados: {n_asi} · usuarios borrados: {n_usu}"))
