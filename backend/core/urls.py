from django.urls import path

from .views import (
    AdminAuditoriaView,
    AdminEventoDetailView,
    AdminEventosView,
    AsientosEventoView,
    CompraView,
    EventoListView,
    LoginView,
    MisReservasView,
    PerfilView,
    ReservaCreateView,
    ReservaDetailView,
    SaludView,
    UsuarioCreateView,
)

urlpatterns = [
    path("eventos/", EventoListView.as_view(), name="eventos"),
    path("eventos/<uuid:pk>/asientos/", AsientosEventoView.as_view(), name="asientos-evento"),
    path("login/", LoginView.as_view(), name="login"),
    path("salud/", SaludView.as_view(), name="salud"),
    path("usuarios/", UsuarioCreateView.as_view(), name="usuarios"),
    path("reservas/", ReservaCreateView.as_view(), name="reservas"),
    path("reservas/mias/", MisReservasView.as_view(), name="reservas-mias"),
    path("reservas/<uuid:pk>/", ReservaDetailView.as_view(), name="reserva-detalle"),
    path("perfil/", PerfilView.as_view(), name="perfil"),
    path("compras/", CompraView.as_view(), name="compras"),
    path("admin/eventos/", AdminEventosView.as_view(), name="admin-eventos"),
    path("admin/eventos/<uuid:pk>/", AdminEventoDetailView.as_view(), name="admin-evento"),
    path("admin/auditoria/", AdminAuditoriaView.as_view(), name="admin-auditoria"),
]
