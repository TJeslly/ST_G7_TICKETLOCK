"""Carga un catálogo de eventos de demostración con su mapa de asientos.

Uso:  python manage.py seed_catalogo

- Es idempotente: puede ejecutarse varias veces sin duplicar eventos ni asientos.
- Completa la cuadrícula de asientos (filas A, B, C… × columnas 1–10) solo donde falten.
- Los estados BLOQUEADO / VENDIDO de la demostración son visuales (se generan de forma
  determinista); la reserva y compra reales se implementarán con el control de concurrencia.
"""
import random
from datetime import datetime, timedelta, timezone as dt_timezone

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Asiento, Evento

BOGOTA = dt_timezone(timedelta(hours=-5))
COLUMNAS = 10

# (nombre, lugar, fecha local, filas)
CATALOGO = [
    # Evento de database/seed.sql: solo se completa su cuadrícula de asientos (4 filas × 10).
    ("Concierto de prueba", "Movistar Arena, Bogotá", datetime(2026, 12, 1, 20, 0), 4),
    ("Noche de Rock Sinfónico", "Teatro Mayor, Bogotá", datetime(2026, 11, 7, 20, 0), 4),
    ("Candlelight: Tributo a Queen", "Teatro Colón, Bogotá", datetime(2026, 11, 14, 19, 30), 5),
    ("Candlelight: Las Cuatro Estaciones de Vivaldi", "Teatro Mayor, Bogotá", datetime(2026, 11, 21, 20, 0), 6),
    ("Candlelight: Tributo a Coldplay", "Teatro Metropolitano, Medellín", datetime(2026, 11, 28, 19, 30), 5),
    ("Candlelight: Música de Studio Ghibli", "Teatro Municipal, Cali", datetime(2026, 12, 5, 19, 0), 5),
    ("Candlelight: Tributo a Taylor Swift", "Teatro Colón, Bogotá", datetime(2026, 12, 12, 20, 0), 6),
    ("Candlelight: Navidad con Cuerdas", "Teatro Mayor, Bogotá", datetime(2026, 12, 19, 19, 30), 5),
    ("Festival de Jazz Bajo las Estrellas", "Auditorio León de Greiff, Bogotá", datetime(2027, 1, 16, 19, 0), 4),
    ("Noche de Salsa Sinfónica", "Teatro Metropolitano, Medellín", datetime(2027, 1, 23, 20, 30), 5),
    ("Orquesta Filarmónica: Novena de Beethoven", "Teatro Mayor, Bogotá", datetime(2027, 2, 6, 19, 30), 6),
]


def _estado_demo(nombre, codigo):
    """Estado determinista: ~72 % disponible, ~16 % vendido, ~12 % bloqueado."""
    x = random.Random(f"{nombre}|{codigo}").random()
    if x < 0.16:
        return "VENDIDO"
    if x < 0.28:
        return "BLOQUEADO"
    return "DISPONIBLE"


class Command(BaseCommand):
    help = "Carga el catálogo de eventos de demostración y completa sus asientos."

    @transaction.atomic
    def handle(self, *args, **options):
        eventos_nuevos = asientos_nuevos = 0
        for nombre, lugar, fecha, filas in CATALOGO:
            evento = Evento.objects.filter(nombre=nombre).first()
            if evento is None:
                evento = Evento.objects.create(
                    nombre=nombre,
                    lugar=lugar,
                    fecha=fecha.replace(tzinfo=BOGOTA),
                    estado="PUBLICADO",
                )
                eventos_nuevos += 1

            existentes = set(evento.asientos.values_list("codigo", flat=True))
            faltantes = []
            for f in range(filas):
                for c in range(1, COLUMNAS + 1):
                    codigo = f"{chr(65 + f)}{c}"
                    if codigo not in existentes:
                        faltantes.append(
                            Asiento(evento=evento, codigo=codigo, estado=_estado_demo(nombre, codigo))
                        )
            Asiento.objects.bulk_create(faltantes)
            asientos_nuevos += len(faltantes)

        self.stdout.write(
            self.style.SUCCESS(
                f"Catálogo listo: {eventos_nuevos} evento(s) nuevo(s), {asientos_nuevos} asiento(s) creados."
            )
        )
