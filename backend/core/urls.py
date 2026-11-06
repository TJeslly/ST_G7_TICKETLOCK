from django.urls import path

from .views import AsientosEventoView, EventoListView, LoginView, SaludView, UsuarioCreateView

urlpatterns = [
    path("eventos/", EventoListView.as_view(), name="eventos"),
    path("eventos/<uuid:pk>/asientos/", AsientosEventoView.as_view(), name="asientos-evento"),
    path("login/", LoginView.as_view(), name="login"),
    path("salud/", SaludView.as_view(), name="salud"),
    path("usuarios/", UsuarioCreateView.as_view(), name="usuarios"),
]
