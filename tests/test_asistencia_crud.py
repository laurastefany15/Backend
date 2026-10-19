import secrets
import unittest
from datetime import date

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from app import app
from extensions import db
from models import Contrato, Empleado, Empresa, Usuario
from services.auth_service import create_access_token


class AsistenciaCrudTest(unittest.TestCase):
    def setUp(self):
        self.context = app.app_context()
        self.context.push()
        suffix = secrets.token_hex(4)
        self.empresa = Empresa(
            nit=f"800{suffix[:6]}-1",
            razon_social="Empresa asistencia",
            activa=True,
        )
        db.session.add(self.empresa)
        db.session.flush()
        self.usuario = Usuario(
            correo=f"asistencia.{suffix}@nomina.local",
            hash_password=generate_password_hash("clave-segura-1"),
            activo=True,
            empresa_id=self.empresa.id,
        )
        self.empleado = Empleado(
            empresa_id=self.empresa.id,
            tipo_documento="CC",
            numero_documento=f"20{suffix}",
            nombres="Luis",
            apellidos="Gomez",
            estado="ACTIVO",
        )
        db.session.add_all([self.usuario, self.empleado])
        db.session.flush()
        self.contrato = Contrato(
            empleado_id=self.empleado.id,
            tipo_contrato="INDEFINIDO",
            cargo="Auxiliar",
            fecha_inicio=date(2026, 1, 1),
            salario_mensual=1800000,
            horas_semanales=48,
            estado="ACTIVO",
        )
        db.session.add(self.contrato)
        db.session.commit()
        self.client = app.test_client()
        self.headers = {
            "Authorization": f"Bearer {create_access_token(self.usuario)}"
        }
        self.payload = {
            "contrato_id": self.contrato.id,
            "entrada": "2026-03-02T08:00:00-05:00",
            "salida": "2026-03-02T17:00:00-05:00",
            "minutos_descanso": 60,
            "observacion": "Jornada ordinaria",
        }

    def tearDown(self):
        leftover = []
        try:
            db.session.rollback()
            contrato_id = self.contrato.id
            empleado_id = self.empleado.id
            usuario_id = self.usuario.id
            empresa_id = self.empresa.id
            statements = [
                (
                    "DELETE FROM horas_extras WHERE asistencia_id IN "
                    "(SELECT id FROM asistencias WHERE contrato_id = :contrato_id)",
                    {"contrato_id": contrato_id},
                ),
                (
                    "DELETE FROM asistencias WHERE contrato_id = :contrato_id",
                    {"contrato_id": contrato_id},
                ),
                ("DELETE FROM contratos WHERE id = :id", {"id": contrato_id}),
                ("DELETE FROM empleados WHERE id = :id", {"id": empleado_id}),
                ("DELETE FROM usuarios WHERE id = :id", {"id": usuario_id}),
                ("DELETE FROM empresas WHERE id = :id", {"id": empresa_id}),
            ]
            for statement, params in statements:
                db.session.execute(text(statement), params)
            db.session.commit()
        except Exception as error:
            db.session.rollback()
            leftover = self._remaining_rows()
            self.fail(f"No se pudo borrar la prueba: {error}. Datos restantes: {leftover}")
        finally:
            self.context.pop()

    def _remaining_rows(self):
        rows = {}
        queries = {
            "asistencias": "SELECT id, contrato_id, estado FROM asistencias WHERE contrato_id = :contrato_id",
            "contratos": "SELECT id, empleado_id, estado FROM contratos WHERE id = :contrato_id",
            "empleados": "SELECT id, empresa_id FROM empleados WHERE id = :empleado_id",
            "usuarios": "SELECT id, correo, empresa_id FROM usuarios WHERE id = :usuario_id",
            "empresas": "SELECT id, nit FROM empresas WHERE id = :empresa_id",
        }
        params = {
            "contrato_id": self.contrato.id,
            "empleado_id": self.empleado.id,
            "usuario_id": self.usuario.id,
            "empresa_id": self.empresa.id,
        }
        for name, statement in queries.items():
            found = db.session.execute(text(statement), params).all()
            if found:
                rows[name] = [tuple(row) for row in found]
        return rows

    def test_crud_asistencia(self):
        created = self.client.post("/asistencias", headers=self.headers, json=self.payload)
        self.assertEqual(created.status_code, 201, created.get_json())
        asistencia = created.get_json()["asistencia"]
        asistencia_id = asistencia["id"]
        self.assertEqual(asistencia["estado"], "REGISTRADA")
        self.assertEqual(asistencia["minutos_descanso"], 60)

        listed = self.client.get(
            f"/asistencias?contrato_id={self.contrato.id}&estado=REGISTRADA",
            headers=self.headers,
        )
        self.assertEqual(listed.status_code, 200, listed.get_json())
        self.assertEqual(listed.get_json()["pagination"]["total"], 1)

        shown = self.client.get(f"/asistencias/{asistencia_id}", headers=self.headers)
        self.assertEqual(shown.status_code, 200, shown.get_json())
        self.assertEqual(shown.get_json()["asistencia"]["id"], asistencia_id)

        updated = self.client.put(
            f"/asistencias/{asistencia_id}",
            headers=self.headers,
            json={
                "contrato_id": self.contrato.id,
                "entrada": "2026-03-02T08:00:00-05:00",
                "salida": "2026-03-02T17:30:00-05:00",
                "minutos_descanso": 30,
                "estado": "VALIDADA",
            },
        )
        self.assertEqual(updated.status_code, 200, updated.get_json())
        self.assertEqual(updated.get_json()["asistencia"]["estado"], "VALIDADA")
        self.assertEqual(updated.get_json()["asistencia"]["minutos_descanso"], 30)
        self.assertIsNone(updated.get_json()["asistencia"]["observacion"])

        invalid = self.client.post("/asistencias", headers=self.headers, json={"contrato_id": 1})
        self.assertEqual(invalid.status_code, 400, invalid.get_json())

        removed = self.client.delete(
            f"/asistencias/{asistencia_id}",
            headers=self.headers,
        )
        self.assertEqual(removed.status_code, 200, removed.get_json())
        self.assertEqual(removed.get_json()["asistencia"]["estado"], "ANULADA")

        missing = self.client.get("/asistencias/999999", headers=self.headers)
        self.assertEqual(missing.status_code, 404, missing.get_json())

    def test_otra_empresa_no_ve_la_asistencia(self):
        created = self.client.post("/asistencias", headers=self.headers, json=self.payload)
        self.assertEqual(created.status_code, 201, created.get_json())
        asistencia_id = created.get_json()["asistencia"]["id"]

        otra = Empresa(nit=f"700{secrets.token_hex(3)}-2", razon_social="Otra", activa=True)
        db.session.add(otra)
        db.session.flush()
        ajeno = Usuario(
            correo=f"ajeno.{secrets.token_hex(4)}@nomina.local",
            hash_password=generate_password_hash("clave-segura-1"),
            activo=True,
            empresa_id=otra.id,
        )
        db.session.add(ajeno)
        db.session.commit()
        try:
            headers = {"Authorization": f"Bearer {create_access_token(ajeno)}"}
            hidden = self.client.get(f"/asistencias/{asistencia_id}", headers=headers)
            self.assertEqual(hidden.status_code, 404, hidden.get_json())
        finally:
            db.session.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": ajeno.id})
            db.session.execute(text("DELETE FROM empresas WHERE id = :id"), {"id": otra.id})
            db.session.commit()


if __name__ == "__main__":
    unittest.main()
