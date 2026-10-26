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

Copia `.env.example` a `.env` y define `JWT_SECRET_KEY` con un secreto
aleatorio de al menos 32 bytes, distinto para cada entorno. Ese archivo está
en `.gitignore` y la aplicación lo carga al arrancar. Los tokens de acceso
expiran en una hora.

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

## Contratos

Las rutas `/contratos` requieren JWT y solo muestran contratos de empleados de
la empresa del usuario.

- `GET /contratos?page=1&per_page=20&empleado_id=1&estado=ACTIVO`: lista contratos.
- `POST /contratos`: crea un contrato. Requiere `empleado_id`, `tipo_contrato`,
  `cargo`, `fecha_inicio`, `salario_mensual` y `horas_semanales`.
- `GET /contratos/<id>`: consulta un contrato.
- `PUT /contratos/<id>`: reemplaza el contrato; los campos opcionales omitidos se limpian.
- `PATCH /contratos/<id>`: actualiza solo los campos enviados.
- `DELETE /contratos/<id>`: marca el contrato como `TERMINADO`.

`tipo_contrato` admite `INDEFINIDO`, `FIJO`, `OBRA_LABOR`, `APRENDIZAJE` y `OTRO`.
`estado` admite `ACTIVO` y `TERMINADO`. `dia_descanso` va de 1 a 7.

## Asistencias

Las rutas `/asistencias` requieren JWT y solo muestran registros de contratos
de la empresa del usuario. La asistencia se asocia al contrato, que ya pertenece
a un empleado.

- `GET /asistencias?page=1&per_page=20&contrato_id=1&estado=REGISTRADA`: lista asistencias.
- `POST /asistencias`: crea un registro. Requiere `contrato_id` y `entrada`.
- `GET /asistencias/<id>`: consulta un registro.
- `PUT /asistencias/<id>`: reemplaza el registro; los campos opcionales omitidos se limpian.
- `PATCH /asistencias/<id>`: actualiza solo los campos enviados.
- `DELETE /asistencias/<id>`: anula el registro (`estado` queda en `ANULADA`).

`entrada` y `salida` usan fecha y hora ISO 8601. `salida` debe ser posterior a
`entrada`. `estado` admite `REGISTRADA`, `VALIDADA` y `ANULADA`. El contrato
debe pertenecer a la empresa del usuario y estar activo para crear un registro.

## Vacaciones

Las rutas requieren JWT y solo operan sobre contratos de la empresa del usuario.
El saldo sigue la vista `vw_saldo_vacaciones`: la suma de los días de
`movimientos_vacaciones` del contrato.

- `GET /vacaciones?page=1&per_page=20&contrato_id=1&estado=SOLICITADA`: lista vacaciones.
- `POST /vacaciones`: crea una vacación. Requiere `contrato_id`, `fecha_inicio`,
  `fecha_fin` y `dias_habiles`.
- `GET /vacaciones/saldos?contrato_id=1`: consulta el saldo por contrato.
- `GET /vacaciones/<id>`: consulta una vacación.
- `PUT /vacaciones/<id>`: reemplaza la vacación; los campos opcionales omitidos se limpian.
- `PATCH /vacaciones/<id>`: actualiza solo los campos enviados.
- `DELETE /vacaciones/<id>`: cancela la vacación (`estado` queda en `CANCELADA`).

`estado` admite `SOLICITADA`, `APROBADA`, `DISFRUTADA` y `CANCELADA`.
`aprobada_por` lo asigna el sistema al pasar a `APROBADA` o `DISFRUTADA`.
Al marcar `DISFRUTADA` se registra un movimiento de tipo `DISFRUTE` con los días
en negativo, si el saldo alcanza. Al salir de ese estado, ese movimiento se retira.
Las fechas no pueden cruzarse con otra vacación activa ni con una incapacidad
vigente del mismo contrato. `fecha_reintegro`, si se envía, debe ser posterior a
`fecha_fin`.

## Movimientos de vacaciones

- `GET /movimientos-vacaciones?contrato_id=1&vacaciones_id=1&tipo=CAUSACION`: lista movimientos.
- `POST /movimientos-vacaciones`: crea un movimiento. Requiere `contrato_id`,
  `fecha`, `tipo` y `dias`.
- `GET /movimientos-vacaciones/<id>`: consulta un movimiento.
- `PUT /movimientos-vacaciones/<id>`: reemplaza el movimiento.
- `PATCH /movimientos-vacaciones/<id>`: actualiza solo los campos enviados.
- `DELETE /movimientos-vacaciones/<id>`: elimina el movimiento.

`tipo` admite `CAUSACION` (días positivos), `DISFRUTE` y `COMPENSACION` (días
negativos) y `AJUSTE`. El saldo resultante no puede quedar negativo. El disfrute
generado por una vacación `DISFRUTADA` se modifica desde la vacación.

## Incapacidades

- `GET /incapacidades?page=1&per_page=20&contrato_id=1&estado=REGISTRADA&tipo=ENFERMEDAD_GENERAL`:
  lista incapacidades.
- `POST /incapacidades`: crea una incapacidad. Requiere `contrato_id`, `tipo`,
  `fecha_inicio` y `fecha_fin`.
- `GET /incapacidades/<id>`: consulta una incapacidad.
- `PUT /incapacidades/<id>`: reemplaza la incapacidad; los campos opcionales omitidos se limpian.
- `PATCH /incapacidades/<id>`: actualiza solo los campos enviados.
- `DELETE /incapacidades/<id>`: rechaza la incapacidad (`estado` queda en `RECHAZADA`).

`tipo` admite `ENFERMEDAD_GENERAL`, `ACCIDENTE_LABORAL`, `ENFERMEDAD_LABORAL`,
`MATERNIDAD`, `PATERNIDAD` y `OTRA`. `estado` admite `REGISTRADA`, `VALIDADA`,
`EN_COBRO`, `PAGADA` y `RECHAZADA`. `porcentaje_reconocimiento` va de 0 a 100.
Las fechas no pueden cruzarse con otra incapacidad vigente ni con una vacación
activa del mismo contrato.

La incapacidad no exige soporte de la EPS: `entidad_responsable`,
`numero_certificado` y los documentos son opcionales.

### Documentos de incapacidad

Los documentos se suben como archivos y quedan guardados en el servidor, en
`instance/uploads/incapacidades/<id>/`, con un nombre aleatorio. La API no
recibe URLs.

- `POST /incapacidades` con `multipart/form-data`: crea la incapacidad y adjunta
  los archivos del campo `documentos` en la misma petición. `tipo_documento`
  es opcional.
- `GET /incapacidades/<id>/documentos`: lista los documentos.
- `POST /incapacidades/<id>/documentos`: sube uno o varios archivos en el campo
  `documentos` (`multipart/form-data`). `tipo` es opcional.
- `GET /incapacidades/<id>/documentos/<doc_id>`: consulta los datos del documento.
- `GET /incapacidades/<id>/documentos/<doc_id>/archivo`: descarga el archivo
  (`?inline=1` para verlo en el navegador).
- `DELETE /incapacidades/<id>/documentos/<doc_id>`: borra el documento y su archivo.

El tipo de documento admite `CERTIFICADO_EPS`, `HISTORIA_CLINICA`,
`TRANSCRIPCION` y `OTRO` (por defecto). Se aceptan PDF, PNG y JPG de hasta
10 MB por archivo y 50 MB por petición; el contenido se verifica, no solo la
extensión.

## Empresas

El CRUD de empresas está en rutas protegidas que requieren JWT y el rol `ADMIN`:

- `GET /admin/empresas?page=1&per_page=20&activa=true`: lista empresas paginadas.
- `POST /admin/empresas`: crea una empresa; requiere `nit` y `razon_social`.
- `GET /admin/empresas/<id>`: consulta una empresa.
- `PUT /admin/empresas/<id>`: reemplaza los datos; los campos opcionales omitidos se limpian.
- `PATCH /admin/empresas/<id>`: actualiza solo los campos enviados.
- `DELETE /admin/empresas/<id>`: desactiva la empresa (eliminación lógica).

El cuerpo acepta `nit`, `razon_social`, `direccion`, `telefono`, `correo` y `activa`.
El NIT es único. Una empresa inactiva no se puede asignar a un usuario.

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