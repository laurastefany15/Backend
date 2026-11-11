"""
conftest.py - Preparación compartida de pytest (entorno y base de datos de pruebas).
Entradas: ninguna; pytest lo carga automáticamente antes de los tests.
Esperado: los tests usan SQLite en memoria con el esquema de las migraciones; nunca tocan instance/nomina.sqlite3.
Cambios: 2026-11-10 | Stiven B | creación de la base de datos de pruebas en memoria
"""
import os
from pathlib import Path

# Debe ir ANTES de importar la app: así se carga TestingConfig.
os.environ["APP_ENV"] = "testing"

import pytest  # noqa: E402
from flask_migrate import upgrade  # noqa: E402

from app import app as flask_app  # noqa: E402

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


@pytest.fixture(scope="session", autouse=True)
def database():
    uri = flask_app.config["SQLALCHEMY_DATABASE_URI"]
    # Seguro anti-accidentes: nunca correr tests contra una base real.
    assert flask_app.config["TESTING"] and ":memory:" in uri, (
        f"Los tests deben usar una base en memoria, no: {uri}"
    )
    with flask_app.app_context():
        upgrade(directory=str(MIGRATIONS_DIR))
    yield