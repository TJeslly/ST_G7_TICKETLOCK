# Fase 4 — Diseño, navegabilidad e integración con la base de datos

Grupo TicketLock · Sistemas Transaccionales · Universidad Manuela Beltrán (ABP)

Repositorio: https://github.com/TJeslly/ST_G7_TICKETLOCK

## Qué se cambió

| Requisito de la guía | Qué se hizo | Dónde |
|---|---|---|
| 2.1 Diseño | Mensajes de éxito/error en todos los formularios, estado de la base en el pie, estilos de error unificados | `index.html` |
| 2.2 Navegabilidad | Menú Inicio · Eventos · Asientos · Cómo funciona · Cuenta con sección activa, desplazamiento suave y botón «↑ Inicio» | `index.html` |
| 2.3 Conexión a BD | Módulo propio de conexión (`db.py`), endpoint `/api/salud/`, consulta de eventos y asientos, registro e inicio de sesión con validación, errores de conexión tratados (503) | `backend/core/` |
| 3 Organización | Capas separadas: `views` (interfaz) → `services` (negocio) → `repositories` (datos) → `db` (conexión) | `backend/core/` |
| 3 Configuración segura | Credenciales por variables de entorno / `.env` (excluido de Git) y plantilla `.env.example` | `.env.example` |
| 3 Scripts SQL | `database/schema.sql` (tablas) y `database/seed.sql` (datos de prueba), más `seed_catalogo` | `database/` |

## Dificultades técnicas encontradas

1. **Auditoría rechazada por la base.** El código guardaba `OK`/`FALLIDO` en `auditoria.resultado`, pero la tabla real solo admite `SUCCESS`, `DENIED` y `ERROR` (restricción `CHECK`). Las pruebas no lo detectaban porque la base de pruebas se crea con migraciones y no trae ese `CHECK`. Se corrigieron los valores y se agregó una prueba que instala el `CHECK` antes de ejecutar.
2. **Un error se disfrazaba de «correo duplicado».** Cualquier `IntegrityError` se mostraba como «Ya existe una cuenta con este correo». Ahora solo la restricción UNIQUE del correo se informa así; el resto es un error de operación con mensaje propio.
3. **Backend apagado vs. base de datos caída.** La interfaz trataba ambos casos igual (modo demostración). Ahora distingue: sin backend → modo demostración; backend activo pero PostgreSQL caído → aviso de error en rojo.
4. **Pruebas con base real.** La base de pruebas de Django no replica todas las restricciones de `schema.sql`; por eso las pruebas críticas se complementan con una verificación contra PostgreSQL con el esquema real.

## Evidencias

Las capturas están en `docs/evidencias/`:

- `01_inicio_navegacion.png`, `02_eventos_desde_bd.png`, `03_mapa_asientos.png` — interfaz, menú y consulta de eventos y asientos.
- `04_registro_validacion.png`, `05_registro_exitoso.png`, `06_login_exitoso.png`, `07_login_error.png` — formularios, validaciones y mensajes.
- `08_error_bd_eventos.png`, `09_error_bd_estado.png` — manejo del error de conexión.
- `10_bd_consulta_eventos.png`, `11_bd_registro_guardado.png` — consultas SQL: datos del catálogo y el usuario registrado desde la interfaz (solo se muestra el inicio del hash).

## Cómo reproducir

Ver `README.md` (configuración, `.env`, `python manage.py runserver`, `python manage.py test`).
