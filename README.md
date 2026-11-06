# TicketLock

Sistema transaccional de compra de boletos para conciertos.

🔗 Ver interfaz en vivo: https://tjeslly.github.io/ST_G7_TICKETLOCK/

## Descripción

Prototipo académico que implementa el control de concurrencia y las propiedades ACID necesarias para evitar la sobreventa y duplicidad de boletos, desarrollado para las asignaturas de Sistemas Transaccionales y Arquitectura de Software.

## Tecnologías

- Backend: Python + Django REST Framework
- Base de datos: PostgreSQL
- Frontend: React + Vite (fases posteriores)

## Requisitos previos

- Python 3.10+
- PostgreSQL 15+
- pip

## Configuración de la base de datos

1. Crear la base de datos en PostgreSQL (puede hacerse desde pgAdmin o por consola):

```
CREATE DATABASE ticketlock;
```

2. Ejecutar el script de creación de tablas (database/schema.sql) contra esa base de datos, usando pgAdmin (Query Tool) o la terminal:

```
psql -U postgres -d ticketlock -f database/schema.sql
```

3. Cargar los datos de prueba:

```
psql -U postgres -d ticketlock -f database/seed.sql
```

## Configuración del backend

1. Crear y activar un entorno virtual:

```
python -m venv venv
venv\Scripts\Activate.ps1      # Windows
source venv/bin/activate       # macOS/Linux
```

2. Instalar las dependencias:

```
pip install -r requirements.txt
```

3. Crear un archivo .env en la raíz del proyecto con las credenciales de la base de datos:

```
DB_NAME=ticketlock
DB_USER=postgres
DB_PASSWORD=tu_contraseña
DB_HOST=localhost
DB_PORT=5432
```

Hay una plantilla en `.env.example`: cópiala como `.env` y cambia los valores. El archivo `.env` está en `.gitignore` y **nunca debe subirse al repositorio** (ni contraseñas ni datos personales reales).

4. Entrar a la carpeta backend y aplicar las migraciones (las tablas ya existen, por eso se usa --fake-initial):

```
cd backend
python manage.py migrate --fake-initial
```

5. Verificar la conexión (opcional), con el servidor en marcha:

```
curl http://127.0.0.1:8000/api/salud/
```

Responde `200` con el motor, el nombre de la base, la latencia y el total de registros de las tablas principales. Si PostgreSQL no responde, devuelve `503` con un mensaje claro.

## Estructura del proyecto

```
ST_G7_TICKETLOCK/
├── index.html         Interfaz (catálogo, mapa de asientos, registro e inicio de sesión)
├── backend/           Proyecto Django (API REST)
│   ├── core/          App con modelos, API y pruebas
│   │   ├── db.py            Conexión a la base de datos: verificación, errores y estadísticas
│   │   ├── repositories.py  Acceso a datos (única capa que consulta la base)
│   │   ├── services.py      Lógica de negocio (registro, inicio de sesión, orden de asientos)
│   │   ├── views.py         Interfaz HTTP: recibe la petición y responde
│   │   ├── serializers.py   Validación de los datos antes de guardarlos
│   │   ├── cors.py          Vista base: CORS y respuesta 503 si la base falla
│   │   ├── models.py        Modelos del dominio (siete tablas)
│   │   ├── urls.py          Rutas de la API
│   │   ├── tests.py         Pruebas automáticas
│   │   └── management/commands/seed_catalogo.py  Catálogo de eventos de demostración
│   └── ticketlock/    Configuración del proyecto
├── .env.example       Plantilla de variables de entorno (copiar como .env)
├── database/          Scripts SQL
│   ├── schema.sql      Creación de tablas, PK, FK y restricciones
│   └── seed.sql         Datos iniciales de prueba
├── docs/              Documentación de fases anteriores y de la Fase 4 (cambios y evidencias)
└── requirements.txt   Dependencias de Python
```

## Ejecutar el backend y la interfaz

1. Con el entorno virtual activado y la base de datos creada, iniciar el servidor desde la carpeta `backend`:

```
cd backend
python manage.py runserver
```

2. Abrir el archivo `index.html` en el navegador (doble clic). La interfaz consulta la API en `http://127.0.0.1:8000/api` y muestra el estado de conexión en el pie de página. Si el backend no está en ejecución, funciona en modo demostración con datos de ejemplo (es lo que se ve en GitHub Pages).

## Arquitectura por capas (Fase 4)

```
Interfaz web (index.html)  →  views.py  →  services.py  →  repositories.py  →  db.py / PostgreSQL
   formularios y mensajes     HTTP         reglas           consultas ORM       conexión y errores
```

- **Interfaz:** `index.html` (menú, catálogo, mapa de asientos, registro e inicio de sesión) y `views.py` (HTTP).
- **Lógica de negocio:** `services.py` (registro, inicio de sesión, reserva temporal de asientos, compra atómica, administración de eventos).
- **Seguridad:** `auth.py` (token firmado tipo JWT, HS256) y `cors.py` (valida el token y el rol en cada ruta protegida).
- **Acceso a datos:** `repositories.py` (consultas) y `db.py` (conexión, verificación, errores).

Los errores de conexión llegan a la interfaz como `503` con el mensaje «No se pudo conectar con la base de datos…», y la interfaz los muestra sin romperse.

## API disponible

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/salud/` | Estado de la conexión con PostgreSQL, latencia y total de registros (200, o 503 si la base no responde) |
| GET | `/api/eventos/` | Lista los eventos publicados con su disponibilidad (RF03) |
| GET | `/api/eventos/<id>/asientos/` | Estado de cada asiento de un evento (RF04) |
| POST | `/api/usuarios/` | Registra un usuario con validaciones (RF01) |
| POST | `/api/login/` | Verifica credenciales, devuelve los datos públicos y un **token** (JWT); el intento queda en auditoría (RF02) |
| GET/PATCH | `/api/perfil/` 🔒 | Consulta o modifica el nombre, el correo y la contraseña (esta última exige la contraseña actual) |
| POST | `/api/reservas/` 🔒 | Bloquea un asiento durante 5 minutos para el usuario (RF05) |
| GET | `/api/reservas/mias/` 🔒 | Reservas vigentes del usuario, con su hora de expiración |
| DELETE | `/api/reservas/<id>/` 🔒 | El usuario libera su reserva antes de que expire |
| POST | `/api/compras/` 🔒 | Paga (simulado) y confirma la compra de los asientos reservados, en una sola transacción (RF07, RF08). Body: `asiento_ids` y `pago` (`numero`, `titular`, `vencimiento` MM/AA, `cvv`). Responde 201 con el comprobante, 400 si la tarjeta es inválida, 402 si el pago es rechazado y 409 si la reserva no es válida |
| GET | `/api/compras/` 🔒 | Historial de compras del usuario (RF09) |
| GET/POST | `/api/admin/eventos/` 🔒 ADMIN | Lista todos los eventos y crea uno con su cuadrícula de asientos (RF11, RF12) |
| PATCH | `/api/admin/eventos/<id>/` 🔒 ADMIN | Publica, cierra o cancela un evento (RF13) |
| GET | `/api/admin/auditoria/` 🔒 ADMIN | Últimos 50 registros de auditoría (RF15) |

🔒 = exige la cabecera `Authorization: Bearer <token>` (el token dura 2 horas). Sin token responde 401; con un rol insuficiente, 403.

Validaciones del registro: nombre de al menos 2 caracteres, correo con formato válido y único (sin distinguir mayúsculas), contraseña de al menos 8 caracteres con una letra y un número. La contraseña se guarda con hash y cada registro queda anotado en la tabla `auditoria` (RF14), con los resultados que admite su restricción `CHECK` (`SUCCESS`, `DENIED`, `ERROR`).

Ejemplo:

```
curl -X POST http://127.0.0.1:8000/api/usuarios/ -H "Content-Type: application/json" -d "{\"nombre\":\"Ana Perez\",\"email\":\"ana@correo.com\",\"password\":\"Clave1234\"}"
```

Inicio de sesión: devuelve los datos públicos del usuario (nunca el hash) y un token firmado. Si el correo no existe o la contraseña es incorrecta responde siempre con el mismo mensaje (401) para no revelar qué cuentas existen.

## Cómo se garantiza la transacción de compra

| Propiedad | Cómo se logra |
|-----------|---------------|
| Atomicidad | Comprar crea la solicitud y su detalle, pasa los asientos a `VENDIDO`, confirma los bloqueos y escribe la auditoría dentro de un único `transaction.atomic()`; si algo falla, no queda nada a medias. |
| Consistencia | Restricciones de la base: un solo bloqueo activo por asiento, un asiento en un solo detalle de compra, máximo 4 boletos por solicitud (trigger) y valores de estado con `CHECK`. |
| Aislamiento | Los asientos se leen con `SELECT ... FOR UPDATE` y siempre en el mismo orden: dos personas no pueden reservar ni comprar el mismo asiento a la vez, y no hay interbloqueos. |
| Durabilidad | PostgreSQL confirma (`COMMIT`) antes de responder; cada operación deja su registro en `auditoria`. |
| Idempotencia | Repetir una compra ya hecha devuelve la misma compra (200, `ya_procesada: true`) sin cobrar dos veces. |
| Expiración | Las reservas duran 5 minutos (`BLOQUEO_MINUTOS`). Los bloqueos vencidos se liberan al consultar eventos o asientos, al reservar o comprar, y con `python manage.py liberar_bloqueos`. |

El precio del boleto (180.000 COP) y los límites se pueden cambiar en `settings.py` con `PRECIO_BOLETO`, `BLOQUEO_MINUTOS` y `MAX_BOLETOS`.

## Catálogo de demostración

La base trae un solo evento de prueba con 4 asientos (`database/seed.sql`). Para cargar un catálogo más amplio (conciertos y ciclo *Candlelight*) y completar el mapa de asientos de cada evento:

```
cd backend
python manage.py seed_catalogo
```

El comando es idempotente: se puede ejecutar varias veces sin duplicar eventos ni asientos. Los estados *bloqueado* y *vendido* que ya trae el catálogo son datos de demostración; las reservas y compras que se hacen desde la interfaz son reales y quedan en las tablas `bloqueos`, `solicitudes_compra` y `detalle_compra`.

## Pruebas

```
cd backend
python manage.py test
```

Para entrar como administrador: `python manage.py crear_admin tu@correo.com TuClave123` (el usuario del `seed.sql` tiene una contraseña ficticia).

Para borrar los datos de prueba (compras, reservas y auditoría, dejando los asientos disponibles): `python manage.py limpiar_datos_prueba`. Con `--usuarios` borra también los usuarios que no son ADMIN. Pide confirmación antes de borrar.

Hay 73 pruebas. Cubren la conexión (`/api/salud/`, errores 503), la restricción `CHECK` de la auditoría, el registro y el inicio de sesión, el token (alterado, vencido, rol), la reserva (conflicto, expiración, límite de 4, liberación), la compra (atomicidad, idempotencia, reservas ajenas o vencidas, historial), el perfil (edición de datos, cambio de contraseña, correo repetido), los permisos (un usuario normal no puede ver la auditoría, no puede darse el rol ADMIN al registrarse ni con un token falsificado), la administración de eventos y, con hilos reales sobre PostgreSQL, la **concurrencia**: 10 personas reservando el mismo asiento (solo una lo logra), 6 compras simultáneas del mismo asiento (una sola venta) y compras cruzadas sin interbloqueo. También se prueba el simulador de pago: tarjeta aprobada, rechazada por el banco, fondos insuficientes (la reserva se conserva y se puede reintentar), validación de Luhn, vencimiento y CVV, y que los datos de la tarjeta no se guardan.

## Simulador de pago

Al pulsar **Confirmar compra** se abre una ventana de pago que pide los datos de una **tarjeta ficticia**. Es una pasarela simulada (`backend/core/pagos.py`): no se conecta a ningún banco ni cobra dinero real.

| Tarjeta de prueba | Resultado |
|---|---|
| `4242 4242 4242 4242` | Aprobada |
| `4000 0000 0000 0002` | Rechazada por el banco emisor (402) |
| `4000 0000 0000 9995` | Rechazada por fondos insuficientes (402) |
| Cualquier otra con número válido (Luhn), p. ej. `5555 5555 5555 4444` | Aprobada |

Cómo funciona: el servidor valida el número (Luhn), el vencimiento (futuro, formato MM/AA) y el CVV (3 o 4 dígitos); luego, dentro de la misma transacción de la compra y **después** de verificar las reservas, simula la autorización. Si se rechaza, no se vende nada y la reserva se conserva para reintentar con otra tarjeta. Si se aprueba, se confirma la compra atómica y se muestra un comprobante (código de compra, tarjeta `•••• 4242`, número de autorización simulado). Los datos de la tarjeta **no se guardan** en la base de datos, ni en la auditoría, ni en los registros; del pago solo se devuelve la marca y los últimos 4 dígitos.

## Despliegue con Docker y NGINX

Con Docker Desktop instalado, desde la raíz del proyecto:

```
copy .env.example .env      (y cambia DB_PASSWORD y DJANGO_SECRET_KEY)
docker compose up --build
```

Levanta PostgreSQL (con `schema.sql` y `seed.sql`), una tarea que prepara la base y carga el catálogo, **3 réplicas del backend** (Gunicorn) y NGINX como balanceador en `http://localhost:8080`, que también sirve la interfaz. Para que las réplicas compartan el mismo estado, toda la concurrencia se resuelve en PostgreSQL y no en la memoria de cada réplica.

## Estado del proyecto

Funcionalidades implementadas: registro e inicio de sesión en vistas separadas, con token y roles, perfil del usuario (editar datos, cambiar contraseña, próximas entradas e historial de compras), catálogo de eventos con ilustración propia y mapa de asientos desde PostgreSQL, reserva temporal de asientos con cuenta regresiva y liberación automática, simulador de pago con tarjeta ficticia y comprobante, compra atómica con idempotencia, historial de compras, administración de eventos y auditoría (solo ADMIN), control de concurrencia verificado con pruebas, y despliegue con Docker y NGINX. El detalle de la Fase 4 (diseño, navegabilidad y base de datos) está en `docs/FASE4_CAMBIOS.md`.

Pendientes y limitaciones conocidas: el pago es una simulación con tarjetas ficticias (no hay pasarela real), el token no se renueva (dura 2 horas), el CORS está abierto para desarrollo y la configuración de Docker se validó solo en su sintaxis: falta probarla en ejecución en tu equipo.
