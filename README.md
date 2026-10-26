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

## Horas extras

- `GET /horas-extras?contrato_id=1&estado=APROBADA&desde=2026-08-01&hasta=2026-08-15`: lista registros.
- `POST /horas-extras`: registra horas. Requiere `contrato_id`, `tipo_codigo`, `fecha` y
  `cantidad_horas` (máximo 24). `asistencia_id` es opcional.
- `GET /horas-extras/<id>`, `PUT /horas-extras/<id>`, `PATCH /horas-extras/<id>`.
- `DELETE /horas-extras/<id>`: rechaza el registro (`estado` queda en `RECHAZADA`).

`tipo_codigo` admite los tipos de recargo activos: `HED`, `HEN`, `RN`, `RDD`, `RDN`,
`HEDD` y `HEDN`. `estado` admite `PENDIENTE`, `APROBADA` y `RECHAZADA`; solo las
aprobadas entran en la nómina. Al aprobarse la nómina pasan a `LIQUIDADA` y ya no
se pueden modificar.

## Nómina quincenal

La nómina se liquida por quincenas: del 1 al 15 y del 16 al último día del mes.
Cada quincena vale 15 días comerciales (mes de 30 días): el día 31 no suma y el
último día de febrero completa los días que faltan.

- `POST /nominas/generar`: liquida una quincena. Indique `{"fecha": "2026-08-10"}`
  o `{"anio": 2026, "mes": 8, "quincena": 1}`. Sin más campos liquida todos los
  contratos de la empresa vigentes en la quincena. Con `empleado_id` o
  `contrato_id` liquida solo ese empleado o contrato. `fecha_pago` es opcional
  (por defecto, el último día de la quincena).
- `GET /nominas?periodo_id=1&empleado_id=1&contrato_id=1&estado=BORRADOR`: lista nóminas.
- `GET /nominas/<id>`: nómina con el detalle de conceptos y pagos.
- `GET /nominas/<id>/recibo`: descarga el recibo de nómina del empleado en PDF.
  Por defecto se descarga como adjunto; use `?inline=1` para abrirlo en el navegador.
- `GET /nominas/reporte?formato=pdf|excel`: descarga un reporte general de las
  nóminas de la empresa en PDF o Excel. Acepta los filtros `periodo_id`, `estado`,
  `desde` y `hasta` (por fecha del periodo). Los totales excluyen las nóminas
  anuladas; use `?inline=1` para abrir el PDF en el navegador.
- `POST /nominas/<id>/aprobar`: pasa de `BORRADOR` a `APROBADA`.
- `POST /nominas/<id>/anular`: anula una nómina en `BORRADOR` o `APROBADA`.
- `POST /nominas/<id>/pagar`: registra el pago del neto (`medio`, `referencia`,
  `fecha_pago` opcionales) y la deja en `PAGADA`.
- `GET /nominas/periodos` y `GET /nominas/periodos/<id>`: periodos con totales.
- `POST /nominas/periodos/<id>/aprobar`: aprueba todas las nóminas en borrador.
- `POST /nominas/periodos/<id>/cerrar`: cierra el periodo si no quedan borradores.

Volver a generar una quincena recalcula las nóminas en `BORRADOR` o `ANULADA` y
omite las `APROBADA` o `PAGADA`. Si a un contrato le falta un parámetro o una
tarifa vigente, se informa en `errores` y los demás contratos se liquidan igual.

### Qué se liquida

- **Salario**: salario diario (salario mensual / 30) por los días trabajados. Si
  hay cambios en `historial_salarios`, se usa el salario vigente de cada día.
- **Vacaciones** `APROBADA` o `DISFRUTADA`: los días del rango se pagan con el
  salario diario, en el concepto `VACACIONES`.
- **Incapacidades** no rechazadas: enfermedad general y `OTRA` al 66,67 % hasta el
  día 90 y al 50 % desde el 91, nunca por debajo del SMMLV diario durante los
  primeros 180 días. Accidente o enfermedad laboral, maternidad y paternidad al
  100 %. Si la incapacidad tiene `porcentaje_reconocimiento`, se usa ese.
- **Licencias** `APROBADA`: las remuneradas se pagan como salario; las no
  remuneradas descuentan los días.
- **Horas extras y recargos** aprobados: valor hora = salario / divisor
  (`DIVISOR_HORA_MENSUAL` vigente o `horas_semanales × 5`). Los tipos `COMPLETO`
  pagan la hora más el recargo y los `ADICIONAL` solo el recargo, con la tarifa
  vigente en la fecha de la hora.
- **Auxilio de transporte**: por días trabajados, si el contrato lo tiene y el
  salario no supera `LIMITE_AUX_TRANSPORTE_SMMLV` veces el SMMLV.
- **Salud y pensión** del trabajador sobre el IBC (conceptos que integran la
  base de seguridad social), con mínimo de un SMMLV y máximo de 25,
  proporcionales a los días pagados. **Fondo de solidaridad pensional** desde 4
  SMMLV (1 % a 2 %). Los contratos de aprendizaje no tienen estos descuentos.
- **Deducciones del empleado** (`deducciones_empleado`) activas y vigentes:
  embargos, libranzas, préstamos y otras, en ese orden. Ninguna deja el neto en
  negativo; si se recorta una cuota, queda anotado en `observaciones`.

Al aprobar, las horas extras pasan a `LIQUIDADA` y baja el saldo de las
deducciones; al anular una nómina aprobada se revierte. Si las novedades cambian
después de generar la nómina, la aprobación pide volver a generarla.

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