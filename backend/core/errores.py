"""Errores de negocio con el código HTTP que les corresponde."""


class ErrorNegocio(Exception):
    """Regla del sistema que no se cumple (no autenticado, asiento ocupado, etc.)."""

    def __init__(self, detalle, estado=409):
        super().__init__(detalle)
        self.detalle = detalle
        self.estado = estado
