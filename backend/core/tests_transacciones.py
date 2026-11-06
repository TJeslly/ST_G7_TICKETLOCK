"""Pruebas de las operaciones transaccionales: reserva, expiración, compra e idempotencia."""
import threading
from datetime import timedelta

from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from . import auth, services
from .models import Asiento, Auditoria, Bloqueo, DetalleCompra, Evento, SolicitudCompra, Usuario


def crear_usuario(email="ana@correo.com", rol="USUARIO"):
    return Usuario.objects.create(nombre="Ana Perez", email=email, password_hash="x", rol=rol)


def crear_evento(n=6, estado="PUBLICADO"):
    ev = Evento.objects.create(nombre="Concierto", fecha=timezone.now() + timedelta(days=10), lugar="Teatro", estado=estado)
    asientos = [Asiento.objects.create(evento=ev, codigo=f"A{i}") for i in range(1, n + 1)]
    return ev, asientos


def cabecera(usuario):
    return {"HTTP_AUTHORIZATION": f"Bearer {auth.crear_token(usuario)}"}


def post(client, url, datos, usuario=None):
    extra = cabecera(usuario) if usuario else {}
    return client.post(url, datos, content_type="application/json", **extra)


class TokenTests(TestCase):
    def test_login_devuelve_token_valido(self):
        r = self.client.post(
            "/api/usuarios/", {"nombre": "Ana Perez", "email": "ana@correo.com", "password": "Clave1234"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)
        r = self.client.post("/api/login/", {"email": "ana@correo.com", "password": "Clave1234"}, content_type="application/json")
        datos = auth.leer_token(r.json()["token"])
        self.assertEqual(datos["rol"], "USUARIO")

    def test_rutas_protegidas_exigen_token(self):
        self.assertEqual(self.client.get("/api/compras/").status_code, 401)
        r = self.client.get("/api/compras/", HTTP_AUTHORIZATION="Bearer basura.token.malo")
        self.assertEqual(r.status_code, 401)

    def test_token_alterado_o_vencido_se_rechaza(self):
        u = crear_usuario()
        token = auth.crear_token(u)
        alterado = token[:-3] + ("AAA" if token[-3:] != "AAA" else "BBB")
        r = self.client.get("/api/compras/", HTTP_AUTHORIZATION=f"Bearer {alterado}")
        self.assertEqual(r.status_code, 401)
        vencido = auth.crear_token(u, segundos=-10)
        r = self.client.get("/api/compras/", HTTP_AUTHORIZATION=f"Bearer {vencido}")
        self.assertEqual(r.status_code, 401)

    def test_admin_requiere_rol(self):
        r = self.client.get("/api/admin/auditoria/", **cabecera(crear_usuario()))
        self.assertEqual(r.status_code, 403)
        r = self.client.get("/api/admin/auditoria/", **cabecera(crear_usuario("admin@correo.com", "ADMIN")))
        self.assertEqual(r.status_code, 200)


class ReservaTests(TestCase):
    def setUp(self):
        self.ana, self.luis = crear_usuario(), crear_usuario("luis@correo.com")
        self.ev, self.asientos = crear_evento()

    def test_reservar_bloquea_el_asiento_con_expiracion(self):
        r = post(self.client, "/api/reservas/", {"asiento_id": str(self.asientos[0].id)}, self.ana)
        self.assertEqual(r.status_code, 201)
        self.asientos[0].refresh_from_db()
        self.assertEqual(self.asientos[0].estado, "BLOQUEADO")
        b = Bloqueo.objects.get(asiento=self.asientos[0])
        self.assertGreater(b.fecha_expiracion, timezone.now())
        self.assertTrue(Auditoria.objects.filter(accion="BLOQUEAR_ASIENTO", resultado="SUCCESS").exists())

    def test_otro_usuario_no_puede_reservar_un_asiento_ocupado(self):
        post(self.client, "/api/reservas/", {"asiento_id": str(self.asientos[0].id)}, self.ana)
        r = post(self.client, "/api/reservas/", {"asiento_id": str(self.asientos[0].id)}, self.luis)
        self.assertEqual(r.status_code, 409)
        self.assertTrue(Auditoria.objects.filter(accion="BLOQUEAR_ASIENTO", resultado="DENIED").exists())

    def test_repetir_la_reserva_propia_no_duplica(self):
        for _ in range(2):
            r = post(self.client, "/api/reservas/", {"asiento_id": str(self.asientos[0].id)}, self.ana)
            self.assertEqual(r.status_code, 201)
        self.assertEqual(Bloqueo.objects.count(), 1)

    def test_maximo_cuatro_reservas_simultaneas(self):
        for a in self.asientos[:4]:
            self.assertEqual(post(self.client, "/api/reservas/", {"asiento_id": str(a.id)}, self.ana).status_code, 201)
        r = post(self.client, "/api/reservas/", {"asiento_id": str(self.asientos[4].id)}, self.ana)
        self.assertEqual(r.status_code, 409)

    def test_reserva_vencida_se_libera_y_otro_puede_tomarla(self):
        post(self.client, "/api/reservas/", {"asiento_id": str(self.asientos[0].id)}, self.ana)
        Bloqueo.objects.update(fecha_expiracion=timezone.now() - timedelta(seconds=1), fecha_inicio=timezone.now() - timedelta(minutes=6))
        r = post(self.client, "/api/reservas/", {"asiento_id": str(self.asientos[0].id)}, self.luis)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Bloqueo.objects.get().usuario_id, self.luis.id)
        self.assertTrue(Auditoria.objects.filter(accion="LIBERAR_BLOQUEO_VENCIDO").exists())

    def test_liberar_vencidos_devuelve_el_asiento_a_disponible(self):
        post(self.client, "/api/reservas/", {"asiento_id": str(self.asientos[0].id)}, self.ana)
        Bloqueo.objects.update(fecha_expiracion=timezone.now() - timedelta(seconds=1), fecha_inicio=timezone.now() - timedelta(minutes=6))
        self.assertEqual(services.liberar_vencidos(), 1)
        self.asientos[0].refresh_from_db()
        self.assertEqual(self.asientos[0].estado, "DISPONIBLE")

    def test_el_usuario_libera_su_reserva_y_no_la_ajena(self):
        r = post(self.client, "/api/reservas/", {"asiento_id": str(self.asientos[0].id)}, self.ana)
        bid = r.json()["id"]
        ajeno = self.client.delete(f"/api/reservas/{bid}/", **cabecera(self.luis))
        self.assertEqual(ajeno.status_code, 404)
        propio = self.client.delete(f"/api/reservas/{bid}/", **cabecera(self.ana))
        self.assertEqual(propio.status_code, 204)
        self.asientos[0].refresh_from_db()
        self.assertEqual(self.asientos[0].estado, "DISPONIBLE")

    def test_no_se_reserva_en_evento_cerrado_ni_asiento_vendido(self):
        ev2, a2 = crear_evento(estado="CERRADO")
        self.assertEqual(post(self.client, "/api/reservas/", {"asiento_id": str(a2[0].id)}, self.ana).status_code, 409)
        Asiento.objects.filter(pk=self.asientos[1].pk).update(estado="VENDIDO")
        self.assertEqual(post(self.client, "/api/reservas/", {"asiento_id": str(self.asientos[1].id)}, self.ana).status_code, 409)

    def test_mis_reservas_lista_solo_las_vigentes_propias(self):
        post(self.client, "/api/reservas/", {"asiento_id": str(self.asientos[0].id)}, self.ana)
        post(self.client, "/api/reservas/", {"asiento_id": str(self.asientos[1].id)}, self.luis)
        r = self.client.get("/api/reservas/mias/", **cabecera(self.ana))
        self.assertEqual([x["codigo"] for x in r.json()], ["A1"])


class CompraTests(TestCase):
    def setUp(self):
        self.ana, self.luis = crear_usuario(), crear_usuario("luis@correo.com")
        self.ev, self.asientos = crear_evento()

    def reservar(self, usuario, *indices):
        for i in indices:
            self.assertEqual(
                post(self.client, "/api/reservas/", {"asiento_id": str(self.asientos[i].id)}, usuario).status_code, 201
            )

    def comprar(self, usuario, *indices):
        return post(self.client, "/api/compras/", {"asiento_ids": [str(self.asientos[i].id) for i in indices]}, usuario)

    def test_compra_confirma_todo_en_una_transaccion(self):
        self.reservar(self.ana, 0, 1)
        r = self.comprar(self.ana, 0, 1)
        self.assertEqual(r.status_code, 201)
        datos = r.json()
        self.assertEqual(datos["total"], "360000.00")
        self.assertEqual(len(datos["boletos"]), 2)
        for a in self.asientos[:2]:
            a.refresh_from_db()
            self.assertEqual(a.estado, "VENDIDO")
        self.assertEqual(SolicitudCompra.objects.count(), 1)
        self.assertEqual(DetalleCompra.objects.count(), 2)
        self.assertEqual(Bloqueo.objects.filter(estado="CONFIRMADO").count(), 2)
        self.assertTrue(Auditoria.objects.filter(accion="CONFIRMAR_COMPRA", resultado="SUCCESS", solicitud__isnull=False).exists())

    def test_repetir_la_compra_no_cobra_dos_veces(self):
        self.reservar(self.ana, 0)
        primera = self.comprar(self.ana, 0)
        segunda = self.comprar(self.ana, 0)
        self.assertEqual((primera.status_code, segunda.status_code), (201, 200))
        self.assertTrue(segunda.json()["ya_procesada"])
        self.assertEqual(primera.json()["id"], segunda.json()["id"])
        self.assertEqual(SolicitudCompra.objects.count(), 1)

    def test_no_se_compra_sin_reserva_ni_con_reserva_ajena(self):
        self.assertEqual(self.comprar(self.ana, 0).status_code, 409)
        self.reservar(self.luis, 1)
        self.assertEqual(self.comprar(self.ana, 1).status_code, 409)
        self.assertEqual(SolicitudCompra.objects.count(), 0)
        self.assertTrue(Auditoria.objects.filter(accion="CONFIRMAR_COMPRA", resultado="DENIED").exists())

    def test_compra_con_reserva_vencida_se_rechaza(self):
        self.reservar(self.ana, 0)
        Bloqueo.objects.update(fecha_expiracion=timezone.now() - timedelta(seconds=1), fecha_inicio=timezone.now() - timedelta(minutes=6))
        self.assertEqual(self.comprar(self.ana, 0).status_code, 409)
        self.assertEqual(DetalleCompra.objects.count(), 0)

    def test_si_un_asiento_falla_no_se_compra_ninguno(self):
        self.reservar(self.ana, 0)  # el asiento 1 no está reservado
        r = self.comprar(self.ana, 0, 1)
        self.assertEqual(r.status_code, 409)
        self.asientos[0].refresh_from_db()
        self.assertEqual(self.asientos[0].estado, "BLOQUEADO")  # nada quedó a medias
        self.assertEqual(SolicitudCompra.objects.count(), 0)

    def test_historial_de_compras(self):
        self.reservar(self.ana, 0)
        self.comprar(self.ana, 0)
        r = self.client.get("/api/compras/", **cabecera(self.ana))
        self.assertEqual(len(r.json()), 1)
        self.assertEqual(r.json()[0]["boletos"][0]["codigo"], "A1")
        self.assertEqual(self.client.get("/api/compras/", **cabecera(self.luis)).json(), [])

    def test_mas_de_cuatro_boletos_se_rechaza(self):
        r = post(self.client, "/api/compras/", {"asiento_ids": [str(a.id) for a in self.asientos[:5]]}, self.ana)
        self.assertEqual(r.status_code, 400)


class AdminTests(TestCase):
    def setUp(self):
        self.admin = crear_usuario("admin@correo.com", "ADMIN")

    def test_crear_evento_genera_la_cuadricula_de_asientos(self):
        r = post(self.client, "/api/admin/eventos/", {
            "nombre": "Nuevo Concierto", "fecha": "2026-12-20T20:00:00-05:00", "lugar": "Teatro Mayor",
            "filas": 3, "columnas": 4}, self.admin)
        self.assertEqual(r.status_code, 201)
        ev = Evento.objects.get(nombre="Nuevo Concierto")
        self.assertEqual(ev.asientos.count(), 12)
        self.assertTrue(ev.asientos.filter(codigo="C4").exists())

    def test_cambiar_estado_y_validar_datos(self):
        ev, _ = crear_evento()
        r = self.client.patch(f"/api/admin/eventos/{ev.id}/", {"estado": "CERRADO"}, content_type="application/json", **cabecera(self.admin))
        self.assertEqual(r.status_code, 200)
        ev.refresh_from_db()
        self.assertEqual(ev.estado, "CERRADO")
        r = self.client.patch(f"/api/admin/eventos/{ev.id}/", {"estado": "XYZ"}, content_type="application/json", **cabecera(self.admin))
        self.assertEqual(r.status_code, 400)
        r = post(self.client, "/api/admin/eventos/", {"nombre": "x"}, self.admin)
        self.assertEqual(r.status_code, 400)

    def test_un_usuario_normal_no_administra(self):
        r = post(self.client, "/api/admin/eventos/", {}, crear_usuario())
        self.assertEqual(r.status_code, 403)


class ConcurrenciaTests(TransactionTestCase):
    """Varias personas intentan el mismo asiento a la vez: solo una debe lograrlo."""

    def correr_en_paralelo(self, funciones):
        resultados, errores = [], []
        barrera = threading.Barrier(len(funciones))

        def envoltura(f):
            try:
                barrera.wait()
                resultados.append(f())
            except Exception as exc:  # noqa: BLE001
                errores.append(exc)
            finally:
                connection.close()

        hilos = [threading.Thread(target=envoltura, args=(f,)) for f in funciones]
        [h.start() for h in hilos]
        [h.join() for h in hilos]
        return resultados, errores

    def test_diez_personas_reservan_el_mismo_asiento(self):
        ev, asientos = crear_evento(2)
        usuarios = [crear_usuario(f"u{i}@correo.com") for i in range(10)]

        def intento(u):
            def f():
                try:
                    services.reservar_asiento(u, asientos[0].id)
                    return "ok"
                except services.ErrorNegocio:
                    return "rechazado"
            return f

        res, err = self.correr_en_paralelo([intento(u) for u in usuarios])
        self.assertEqual(err, [])
        self.assertEqual(res.count("ok"), 1)
        self.assertEqual(res.count("rechazado"), 9)
        self.assertEqual(Bloqueo.objects.filter(asiento=asientos[0], estado="ACTIVO").count(), 1)

    def test_dos_compras_simultaneas_del_mismo_asiento_no_producen_doble_venta(self):
        ev, asientos = crear_evento(2)
        ana = crear_usuario()
        services.reservar_asiento(ana, asientos[0].id)

        def comprar():
            try:
                _, creada = services.comprar(ana, [str(asientos[0].id)])
                return "creada" if creada else "repetida"
            except services.ErrorNegocio:
                return "rechazada"

        res, err = self.correr_en_paralelo([comprar for _ in range(6)])
        self.assertEqual(err, [])
        self.assertEqual(res.count("creada"), 1)
        self.assertEqual(SolicitudCompra.objects.count(), 1)
        self.assertEqual(DetalleCompra.objects.filter(asiento=asientos[0]).count(), 1)
        self.assertEqual(SolicitudCompra.objects.get().total, services.precio_boleto())

    def test_compradores_distintos_peleando_por_asientos_cruzados(self):
        """Dos usuarios piden los mismos dos asientos en distinto orden: sin interbloqueo ni doble venta."""
        ev, asientos = crear_evento(2)
        ana, luis = crear_usuario(), crear_usuario("luis@correo.com")
        services.reservar_asiento(ana, asientos[0].id)
        services.reservar_asiento(luis, asientos[1].id)

        def comprar(u, ids):
            def f():
                try:
                    services.comprar(u, [str(i) for i in ids])
                    return "ok"
                except services.ErrorNegocio:
                    return "rechazada"
            return f

        res, err = self.correr_en_paralelo([
            comprar(ana, [asientos[0].id, asientos[1].id]),
            comprar(luis, [asientos[1].id, asientos[0].id]),
        ])
        self.assertEqual(err, [])
        self.assertEqual(res.count("ok"), 0)  # cada quien solo tiene reservado uno de los dos
        self.assertEqual(DetalleCompra.objects.count(), 0)


class PerfilYPermisosTests(TestCase):
    def setUp(self):
        from django.contrib.auth.hashers import make_password

        self.ana = Usuario.objects.create(nombre="Ana Perez", email="ana@correo.com", password_hash=make_password("Clave1234"))
        self.luis = crear_usuario("luis@correo.com")

    def patch(self, datos, usuario=None):
        return self.client.patch("/api/perfil/", datos, content_type="application/json", **cabecera(usuario or self.ana))

    def test_ver_perfil_requiere_sesion(self):
        self.assertEqual(self.client.get("/api/perfil/").status_code, 401)
        r = self.client.get("/api/perfil/", **cabecera(self.ana))
        self.assertEqual(r.json()["email"], "ana@correo.com")
        self.assertNotIn("password", str(r.json()).lower())

    def test_modificar_nombre_y_correo(self):
        r = self.patch({"nombre": "  Ana   María  Pérez ", "email": "NUEVO@correo.com"})
        self.assertEqual(r.status_code, 200)
        self.ana.refresh_from_db()
        self.assertEqual((self.ana.nombre, self.ana.email), ("Ana María Pérez", "nuevo@correo.com"))
        self.assertTrue(Auditoria.objects.filter(accion="ACTUALIZAR_PERFIL", resultado="SUCCESS").exists())

    def test_correo_de_otra_cuenta_se_rechaza(self):
        r = self.patch({"email": "luis@correo.com"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("email", r.json())

    def test_cambiar_contrasena_exige_la_actual(self):
        self.assertEqual(self.patch({"password_nueva": "Nueva12345"}).status_code, 400)
        r = self.patch({"password_actual": "Equivocada1", "password_nueva": "Nueva12345"})
        self.assertEqual(r.status_code, 400)
        self.assertTrue(Auditoria.objects.filter(accion="ACTUALIZAR_PERFIL", resultado="DENIED").exists())
        r = self.patch({"password_actual": "Clave1234", "password_nueva": "Nueva12345"})
        self.assertEqual(r.status_code, 200)
        ok = self.client.post("/api/login/", {"email": "ana@correo.com", "password": "Nueva12345"}, content_type="application/json")
        viejo = self.client.post("/api/login/", {"email": "ana@correo.com", "password": "Clave1234"}, content_type="application/json")
        self.assertEqual((ok.status_code, viejo.status_code), (200, 401))

    def test_contrasena_nueva_debil_y_sin_cambios(self):
        self.assertEqual(self.patch({"password_actual": "Clave1234", "password_nueva": "sololetras"}).status_code, 400)
        self.assertEqual(self.patch({}).status_code, 400)

    def test_no_se_puede_cambiar_el_rol_desde_el_perfil(self):
        self.patch({"nombre": "Ana Perez", "rol": "ADMIN"})
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.rol, "USUARIO")

    def test_registro_no_permite_elegirse_administrador(self):
        r = self.client.post(
            "/api/usuarios/", {"nombre": "Mala Idea", "email": "mala@correo.com", "password": "Clave1234", "rol": "ADMIN"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Usuario.objects.get(email="mala@correo.com").rol, "USUARIO")

    def test_auditoria_solo_para_administradores(self):
        # sin sesión, con sesión de usuario normal y con administrador
        self.assertEqual(self.client.get("/api/admin/auditoria/").status_code, 401)
        self.assertEqual(self.client.get("/api/admin/auditoria/", **cabecera(self.ana)).status_code, 403)
        admin = crear_usuario("admin@correo.com", "ADMIN")
        self.assertEqual(self.client.get("/api/admin/auditoria/", **cabecera(admin)).status_code, 200)

    def test_un_token_con_rol_falsificado_no_da_acceso(self):
        """El rol se lee siempre de la base de datos, no del token."""
        import base64, hashlib, hmac, json, time

        from django.conf import settings

        b64 = lambda d: base64.urlsafe_b64encode(d).rstrip(b"=").decode()
        cab = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        cuerpo = b64(json.dumps({"sub": str(self.ana.id), "rol": "ADMIN", "exp": int(time.time()) + 600}).encode())
        firma = b64(hmac.new(settings.SECRET_KEY.encode(), f"{cab}.{cuerpo}".encode(), hashlib.sha256).digest())
        r = self.client.get("/api/admin/auditoria/", HTTP_AUTHORIZATION=f"Bearer {cab}.{cuerpo}.{firma}")
        self.assertEqual(r.status_code, 403)
        sin_firma = self.client.get("/api/admin/auditoria/", HTTP_AUTHORIZATION=f"Bearer {cab}.{cuerpo}.")
        self.assertEqual(sin_firma.status_code, 401)
