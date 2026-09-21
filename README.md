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
├── backend/          Proyecto Django (API REST)
│   ├── core/          App con los modelos del dominio
│   └── ticketlock/    Configuración del proyecto
├── database/          Scripts SQL
│   ├── schema.sql      Creación de tablas, PK, FK y restricciones
│   └── seed.sql         Datos iniciales de prueba
├── docs/              Documentación de fases anteriores
└── requirements.txt   Dependencias de Python
```

## Estado del proyecto

Fase actual: estructura de base de datos y backend inicial. Aún no se han implementado las operaciones CRUD ni la lógica transaccional de compra.
