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

4. Entrar a la carpeta backend y aplicar las migraciones (las tablas ya existen, por eso se usa --fake-initial):

```
cd backend
python manage.py migrate --fake-initial
```

5. Verificar la conexión (opcional):

```
python manage.py shell
```

```
from core.models import Usuario
Usuario.objects.all()
```

## Estructura del proyecto

```
ST_G7_TICKETLOCK/
├── index.html         Interfaz (catálogo, mapa de asientos, registro e inicio de sesión)
├── backend/           Proyecto Django (API REST)
│   ├── core/          App con modelos, API y pruebas
│   │   ├── management/commands/seed_catalogo.py  Catálogo de eventos de demostración
│   │   ├── models.py       Modelos del dominio (siete tablas)
│   │   ├── serializers.py  Validaciones y conversión de datos
│   │   ├── views.py        Vistas de la API
│   │   ├── urls.py         Rutas de la API
│   │   └── tests.py        Pruebas automáticas
│   └── ticketlock/    Configuración del proyecto
├── database/          Scripts SQL
│   ├── schema.sql      Creación de tablas, PK, FK y restricciones
│   └── seed.sql         Datos iniciales de prueba
├── docs/              Documentación de fases anteriores
└── requirements.txt   Dependencias de Python
```

## Ejecutar el backend y la interfaz

1. Con el entorno virtual activado y la base de datos creada, iniciar el servidor desde la carpeta `backend`:

```
cd backend
python manage.py runserver
```

2. Abrir el archivo `index.html` en el navegador (doble clic). La interfaz consulta la API en `http://127.0.0.1:8000/api` y muestra el estado de conexión en el pie de página. Si el backend no está en ejecución, funciona en modo demostración con datos de ejemplo (es lo que se ve en GitHub Pages).

## API disponible

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/eventos/` | Lista los eventos publicados con su disponibilidad (RF03) |
| GET | `/api/eventos/<id>/asientos/` | Estado de cada asiento de un evento (RF04) |
| POST | `/api/usuarios/` | Registra un usuario con validaciones (RF01) |
| POST | `/api/login/` | Verifica credenciales e inicia sesión; el intento queda en auditoría (RF02) |

Validaciones del registro: nombre de al menos 2 caracteres, correo con formato válido y único (sin distinguir mayúsculas), contraseña de al menos 8 caracteres con una letra y un número. La contraseña se guarda con hash y cada registro queda anotado en la tabla `auditoria` (RF14).

Ejemplo:

```
curl -X POST http://127.0.0.1:8000/api/usuarios/ -H "Content-Type: application/json" -d "{\"nombre\":\"Ana Perez\",\"email\":\"ana@correo.com\",\"password\":\"Clave1234\"}"
```

Inicio de sesión: devuelve los datos públicos del usuario (nunca el hash). Si el correo no existe o la contraseña es incorrecta responde siempre con el mismo mensaje (401) para no revelar qué cuentas existen. Por ahora no emite token: JWT queda para la siguiente entrega.

## Catálogo de demostración

La base trae un solo evento de prueba con 4 asientos (`database/seed.sql`). Para cargar un catálogo más amplio (conciertos y ciclo *Candlelight*) y completar el mapa de asientos de cada evento:

```
cd backend
python manage.py seed_catalogo
```

El comando es idempotente: se puede ejecutar varias veces sin duplicar eventos ni asientos. Los estados *bloqueado* y *vendido* que se ven en el mapa son datos de demostración; la reserva y la compra reales se implementarán con el control de concurrencia.

## Pruebas

```
cd backend
python manage.py test
```

Las pruebas cubren el listado de eventos, el orden de los asientos, el registro de usuarios y sus validaciones (campos obligatorios, correo inválido o duplicado, contraseña débil), el inicio de sesión (credenciales correctas e incorrectas, auditoría) y la carga idempotente del catálogo.

## Estado del proyecto

Fase actual: primera versión funcional. La interfaz consulta eventos y asientos desde PostgreSQL y permite registrar usuarios con validaciones e iniciar sesión. Aún no se han implementado los tokens JWT, el bloqueo temporal de asientos ni la confirmación transaccional de la compra.
