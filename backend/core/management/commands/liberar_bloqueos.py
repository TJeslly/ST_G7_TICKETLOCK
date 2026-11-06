from django.core.management.base import BaseCommand

from core import services


class Command(BaseCommand):
    help = "Libera las reservas de asientos cuyo tiempo expiró (RF06). Puede programarse cada minuto."

    def handle(self, *args, **options):
        n = services.liberar_vencidos()
        self.stdout.write(f"Reservas vencidas liberadas: {n}")
