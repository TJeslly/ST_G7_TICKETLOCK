from django.contrib import admin

from .models import (
    Asiento,
    Auditoria,
    Bloqueo,
    DetalleCompra,
    Evento,
    SolicitudCompra,
    Usuario,
)

admin.site.register(Usuario)
admin.site.register(Evento)
admin.site.register(Asiento)
admin.site.register(Bloqueo)
admin.site.register(SolicitudCompra)
admin.site.register(DetalleCompra)
admin.site.register(Auditoria)
