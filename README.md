# API Flask con SQLite

## Iniciar en Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m flask --app app db upgrade
python app.py
```

La aplicación queda disponible en http://127.0.0.1:5000. La base SQLite se
almacena en `instance/nomina.sqlite3`.

Define `JWT_SECRET_KEY` en el entorno antes de usar autenticación. Usa un
secreto aleatorio de al menos 32 bytes y distinto para cada entorno. En
PowerShell, por ejemplo, define `$env:JWT_SECRET_KEY` antes de iniciar Flask.
Los tokens de acceso expiran en una hora.

## Swagger / OpenAPI

- Interfaz interactiva: http://127.0.0.1:5000/apidocs/
- Especificación OpenAPI: http://127.0.0.1:5000/openapi.yaml

## Autenticación

- `POST /auth/register` recibe `{"correo": "usuario@example.com", "password": "una-clave-segura"}`.
- `POST /auth/login` recibe las mismas propiedades y devuelve un token Bearer.
- `GET /auth/me` requiere el encabezado `Authorization: Bearer <access_token>`.

## Empleados

Todas las rutas `/empleados` requieren JWT y limitan el acceso a la empresa
asociada al usuario. Los usuarios que no tengan `empresa_id` asignado reciben
HTTP 403; asigna la empresa desde el proceso administrativo antes de usar estas
rutas.

- `GET /empleados?page=1&per_page=20&estado=ACTIVO`: lista empleados paginados.
- `POST /empleados`: crea un empleado; requiere `tipo_documento`,
  `numero_documento`, `nombres` y `apellidos`.
- `GET /empleados/<id>`: consulta un empleado de la empresa del usuario.
- `PUT /empleados/<id>`: reemplaza los datos; los campos opcionales omitidos se limpian.
- `PATCH /empleados/<id>`: actualiza los campos enviados.
- `DELETE /empleados/<id>`: desactiva el empleado (eliminación lógica) para
  preservar contratos e historial de nómina.

El cuerpo acepta los campos definidos por el modelo `Empleado`, excepto
`id`, `empresa_id` y `creado_en`; la empresa se determina desde el usuario
autenticado. Swagger contiene los esquemas y respuestas detallados.

## Asociación de usuarios con empresas

La administración de la asociación `usuarios.empresa_id` se realiza con rutas
protegidas que requieren JWT y el rol `ADMIN`:

- `GET /admin/usuarios/<usuario_id>/empresa`: consulta la asociación actual.
- `POST /admin/usuarios/<usuario_id>/empresa`: asocia una empresa si aún no
  existe una asociación.
- `PUT /admin/usuarios/<usuario_id>/empresa`: establece o cambia la empresa.
- `DELETE /admin/usuarios/<usuario_id>/empresa`: elimina la asociación y deja
  `empresa_id` en `null`.

Los cuerpos de POST y PUT tienen la forma `{"empresa_id": 3}`. La empresa debe
existir y estar activa; el usuario debe existir y estar activo. Swagger incluye
los códigos de respuesta y ejemplos.

Para aprovisionar el primer administrador, un operador debe asignar el rol
`ADMIN` manualmente una sola vez (el rol se crea con las migraciones). Después,
los cambios de asociación se pueden hacer desde Swagger con el token de ese
administrador. Por ejemplo, usando SQLite:

```sql
INSERT INTO usuarios_roles (usuario_id, rol_id)
SELECT u.id, r.id
FROM usuarios AS u
CROSS JOIN roles AS r
WHERE u.correo = 'admin@example.com'
  AND r.codigo = 'ADMIN'
  AND NOT EXISTS (
    SELECT 1
    FROM usuarios_roles AS ur
    WHERE ur.usuario_id = u.id AND ur.rol_id = r.id
  );
```

## Estructura

- `models/`: un módulo por modelo ORM del sistema de nómina.
- `controllers/`, `services/` y `routes/`: autenticación HTTP, lógica de usuarios y rutas.
- `extensions.py`: configuración de SQLAlchemy y Flask-Migrate.
- `migrations/`: migraciones versionadas, vistas, reglas y catálogos iniciales.
- `app.py`: creación y configuración de la aplicación.

## Modelos y migraciones de nómina

El esquema de `nomina_colombia_completa.sql` se adaptó a SQLite. Para aplicar
la migración inicial (también en una base de datos nueva):

```powershell
python -m flask --app app db upgrade
```

Para generar una migración después de cambiar los modelos:

```powershell
python -m flask --app app db migrate -m "Descripción del cambio"
python -m flask --app app db upgrade
```

La migración inicial crea las tablas, restricciones, índices, vistas, reglas
de vigencia y catálogos de roles, conceptos, parámetros y recargos. Los modelos
se pueden importar desde `models`, por ejemplo `from models import Empleado`.
Una migración posterior elimina la tabla heredada del CRUD anterior.