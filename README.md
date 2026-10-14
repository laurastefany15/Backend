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

## Estructura

- `models/`: un módulo por modelo ORM del sistema de nómina.
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