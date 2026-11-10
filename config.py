"""
config.py - Configuración por entornos (development, testing, production).
Entradas: APP_ENV (entorno), DATABASE_URL (opcional, URI de la base de datos).
Esperado: falla al arrancar si la configuración de producción es insegura.
Cambios: 2026-11-10 | Stiven B | creación (paso 1)
"""
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

INSTANCE_DIR = BASE_DIR / "instance"
MIN_JWT_SECRET_BYTES = 32


def _sqlite_uri(filename):
    return "sqlite:///" + (INSTANCE_DIR / filename).as_posix()


class BaseConfig:
    DEBUG = False
    TESTING = False
    # DATABASE_URL permitirá pasar a PostgreSQL sin tocar código.
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or _sqlite_uri(
        "nomina.sqlite3"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    JWT_ACCESS_TOKEN_EXPIRES = 3600
    UPLOAD_FOLDER = str(INSTANCE_DIR / "uploads")
    MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024

    @classmethod
    def validate(cls):
        """Falla al arrancar si la configuración es insegura."""


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    # Base en memoria: los tests nunca tocan la base de desarrollo.
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_SECRET_KEY = "clave-solo-para-pruebas-0123456789-abcdef"
    UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), "idisena_test_uploads")


class ProductionConfig(BaseConfig):
    DEBUG = False

    @classmethod
    def validate(cls):
        secret = cls.JWT_SECRET_KEY
        if not secret or len(secret.encode("utf-8")) < MIN_JWT_SECRET_BYTES:
            raise RuntimeError(
                "En producción, JWT_SECRET_KEY debe tener al menos "
                f"{MIN_JWT_SECRET_BYTES} bytes."
            )


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name):
    try:
        return CONFIGS[name]
    except KeyError:
        valid = ", ".join(sorted(CONFIGS))
        raise RuntimeError(f"APP_ENV '{name}' no es válido. Opciones: {valid}.")