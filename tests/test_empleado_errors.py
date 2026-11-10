"""
test_empleado_errors.py - Pruebas de las respuestas de error del módulo empleados.
Entradas: ninguna; usa la app en modo testing (base en memoria) y crea sus propios datos.
Esperado: 401, 403, 404, 400 y 409 responden JSON con {"error": mensaje} y el código HTTP correcto.
Cambios: 2026-11-10 | Stiven B | creación de pruebas de errores de empleados
"""
import secrets

import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app
from extensions import db
from models import Empresa, Usuario
from services.auth_service import create_access_token


def _headers_para(usuario):
    return {"Authorization": f"Bearer {create_access_token(usuario)}"}


@pytest.fixture()
def client():
    return flask_app.test_client()


@pytest.fixture()
def headers():
    """Usuario con empresa activa."""
    suffix = secrets.token_hex(4)
    with flask_app.app_context():
        empresa = Empresa(
            nit=f"900{suffix[:6]}-1", razon_social="Empresa errores", activa=True
        )
        db.session.add(empresa)
        db.session.flush()
        usuario = Usuario(
            correo=f"errores.{suffix}@test.local",
            hash_password=generate_password_hash("clave-segura-1"),
            activo=True,
            empresa_id=empresa.id,
        )
        db.session.add(usuario)
        db.session.commit()
        return _headers_para(usuario)


@pytest.fixture()
def headers_sin_empresa():
    """Usuario sin empresa asociada."""
    suffix = secrets.token_hex(4)
    with flask_app.app_context():
        usuario = Usuario(
            correo=f"sinempresa.{suffix}@test.local",
            hash_password=generate_password_hash("clave-segura-1"),
            activo=True,
        )
        db.session.add(usuario)
        db.session.commit()
        return _headers_para(usuario)


def test_sin_token_responde_401(client):
    r = client.get("/empleados")
    assert r.status_code == 401
    assert r.get_json() == {"error": "Se requiere un token Bearer válido."}


def test_usuario_sin_empresa_responde_403(client, headers_sin_empresa):
    r = client.get("/empleados", headers=headers_sin_empresa)
    assert r.status_code == 403
    assert r.get_json() == {"error": "El usuario no está asociado a una empresa."}


def test_empleado_inexistente_responde_404(client, headers):
    r = client.get("/empleados/999999", headers=headers)
    assert r.status_code == 404
    assert r.get_json() == {"error": "Empleado no encontrado."}


def test_cuerpo_vacio_responde_400(client, headers):
    r = client.post("/empleados", json={}, headers=headers)
    assert r.status_code == 400
    assert r.get_json() == {"error": "Debe enviar al menos un campo."}


def test_faltan_campos_obligatorios_responde_400(client, headers):
    r = client.post("/empleados", json={"nombres": "Ana"}, headers=headers)
    assert r.status_code == 400
    assert r.get_json() == {
        "error": "Faltan campos obligatorios: apellidos, numero_documento, tipo_documento."
    }


def test_paginacion_no_numerica_responde_400(client, headers):
    r = client.get("/empleados?page=abc", headers=headers)
    assert r.status_code == 400
    assert r.get_json() == {"error": "page y per_page deben ser números enteros."}


def test_documento_duplicado_responde_409(client, headers):
    payload = {
        "tipo_documento": "CC",
        "numero_documento": f"77{secrets.token_hex(4)}",
        "nombres": "Ana",
        "apellidos": "Pérez",
    }
    primero = client.post("/empleados", json=payload, headers=headers)
    assert primero.status_code == 201

    segundo = client.post("/empleados", json=payload, headers=headers)
    assert segundo.status_code == 409
    assert segundo.get_json() == {
        "error": "Ya existe un empleado con ese documento en la empresa."
    }