from datetime import timedelta
from io import StringIO

from django.contrib.auth.hashers import check_password
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from .models import Asiento, Auditoria, Evento, Usuario


class EventosApiTests(TestCase):
    def setUp(self):
        self.evento = Evento.objects.create(
            nombre="Concierto de prueba",
            fecha=timezone.now() + timedelta(days=10),
            lugar="Teatro Mayor",
        )
        for codigo, estado in [("A1", "DISPONIBLE"), ("A2", "VENDIDO"), ("A10", "BLOQUEADO"), ("A3", "DISPONIBLE")]:
            Asiento.objects.create(evento=self.evento, codigo=codigo, estado=estado)
        Evento.objects.create(
            nombre="Evento cerrado",
            fecha=timezone.now(),
            lugar="Otro lugar",
            estado="CERRADO",
        )

    def test_lista_solo_eventos_publicados_con_disponibilidad(self):
        r = self.client.get("/api/eventos/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 1)
        self.assertEqual(r.json()[0]["nombre"], "Concierto de prueba")
        self.assertEqual(r.json()[0]["asientos_disponibles"], 2)

    def test_asientos_del_evento_en_orden_natural(self):
        r = self.client.get(f"/api/eventos/{self.evento.id}/asientos/")
        self.assertEqual(r.status_code, 200)
        codigos = [a["codigo"] for a in r.json()["asientos"]]
        self.assertEqual(codigos, ["A1", "A2", "A3", "A10"])

    def test_evento_inexistente_devuelve_404(self):
        r = self.client.get("/api/eventos/00000000-0000-0000-0000-000000000000/asientos/")
        self.assertEqual(r.status_code, 404)

    def test_respuesta_incluye_cabecera_cors(self):
        r = self.client.get("/api/eventos/")
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")


class RegistroUsuarioTests(TestCase):
    URL = "/api/usuarios/"

    def _post(self, **datos):
        base = {"nombre": "Ana Pérez", "email": "ana@correo.com", "password": "Clave1234"}
        base.update(datos)
        return self.client.post(self.URL, base, content_type="application/json")

    def test_registro_valido_crea_usuario_con_hash_y_auditoria(self):
        r = self._post()
        self.assertEqual(r.status_code, 201)
        self.assertNotIn("password", r.json())
        self.assertNotIn("password_hash", r.json())
        u = Usuario.objects.get(email="ana@correo.com")
        self.assertEqual(u.rol, "USUARIO")
        self.assertNotEqual(u.password_hash, "Clave1234")
        self.assertTrue(check_password("Clave1234", u.password_hash))
        self.assertTrue(Auditoria.objects.filter(accion="REGISTRAR_USUARIO", resultado="OK").exists())

    def test_campos_obligatorios(self):
        r = self.client.post(self.URL, {}, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        for campo in ("nombre", "email", "password"):
            self.assertIn(campo, r.json())
        self.assertEqual(Usuario.objects.count(), 0)

    def test_correo_invalido(self):
        r = self._post(email="no-es-correo")
        self.assertEqual(r.status_code, 400)
        self.assertIn("email", r.json())

    def test_contrasena_corta_o_sin_numero(self):
        self.assertEqual(self._post(password="corta1").status_code, 400)
        self.assertEqual(self._post(password="sololetrasaaa").status_code, 400)

    def test_correo_duplicado_sin_importar_mayusculas(self):
        self.assertEqual(self._post().status_code, 201)
        r = self._post(email="ANA@correo.com")
        self.assertEqual(r.status_code, 400)
        self.assertIn("email", r.json())
        self.assertEqual(Usuario.objects.count(), 1)

    def test_preflight_options(self):
        r = self.client.options(self.URL)
        self.assertEqual(r.status_code, 200)
        self.assertIn("POST", r["Access-Control-Allow-Methods"])


class LoginTests(TestCase):
    URL = "/api/login/"

    def setUp(self):
        self.client.post(
            "/api/usuarios/",
            {"nombre": "Ana Pérez", "email": "ana@correo.com", "password": "Clave1234"},
            content_type="application/json",
        )

    def _login(self, email="ana@correo.com", password="Clave1234"):
        return self.client.post(self.URL, {"email": email, "password": password}, content_type="application/json")

    def test_login_correcto_devuelve_datos_publicos_y_audita(self):
        r = self._login(email="ANA@correo.com")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["nombre"], "Ana Pérez")
        self.assertNotIn("password_hash", r.json())
        self.assertTrue(Auditoria.objects.filter(accion="INICIAR_SESION", resultado="OK").exists())

    def test_contrasena_incorrecta_y_correo_inexistente_dan_el_mismo_mensaje(self):
        a = self._login(password="Equivocada1")
        b = self._login(email="nadie@correo.com")
        self.assertEqual(a.status_code, 401)
        self.assertEqual(b.status_code, 401)
        self.assertEqual(a.json(), b.json())
        self.assertEqual(Auditoria.objects.filter(accion="INICIAR_SESION", resultado="FALLIDO").count(), 2)

    def test_campos_obligatorios(self):
        r = self.client.post(self.URL, {}, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("email", r.json())
        self.assertIn("password", r.json())


class CatalogoDemoTests(TestCase):
    def test_seed_completa_asientos_y_es_idempotente(self):
        evento = Evento.objects.create(
            nombre="Concierto de prueba",
            fecha=timezone.now() + timedelta(days=30),
            lugar="Movistar Arena, Bogotá",
        )
        for c in ("A1", "A2", "A3", "A4"):
            Asiento.objects.create(evento=evento, codigo=c)

        call_command("seed_catalogo", stdout=StringIO())
        eventos = Evento.objects.count()
        asientos = Asiento.objects.count()
        self.assertGreaterEqual(eventos, 10)
        self.assertEqual(evento.asientos.count(), 40)  # 4 filas × 10 columnas
        self.assertEqual(Evento.objects.filter(nombre__startswith="Candlelight").count() >= 5, True)
        # Los asientos que ya existían no cambian de estado
        self.assertEqual(evento.asientos.get(codigo="A1").estado, "DISPONIBLE")

        call_command("seed_catalogo", stdout=StringIO())
        self.assertEqual(Evento.objects.count(), eventos)
        self.assertEqual(Asiento.objects.count(), asientos)

    def test_mapa_incluye_los_tres_estados(self):
        call_command("seed_catalogo", stdout=StringIO())
        evento = Evento.objects.get(nombre="Candlelight: Tributo a Queen")
        estados = {a["estado"] for a in self.client.get(f"/api/eventos/{evento.id}/asientos/").json()["asientos"]}
        self.assertEqual(estados, {"DISPONIBLE", "BLOQUEADO", "VENDIDO"})
