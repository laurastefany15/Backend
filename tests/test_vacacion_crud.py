import secrets
import unittest
from datetime import date

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from app import app
from extensions import db
from models import Contrato, Empleado, Empresa, Usuario
from services.auth_service import create_access_token


class VacacionCrudTest(unittest.TestCase):
    def setUp(self):
        self.context = app.app_context()
        self.context.push()
        suffix = secrets.token_hex(4)
        self.empresa = Empresa(
            nit=f"810{suffix[:6]}-1",
            razon_social="Empresa vacaciones",
            activa=True,
        )
        db.session.add(self.empresa)
        db.session.flush()
        self.usuario = Usuario(
            correo=f"vacaciones.{suffix}@nomina.local",
            hash_password=generate_password_hash("clave-segura-1"),
            activo=True,
            empresa_id=self.empresa.id,
        )
        self.empleado = Empleado(
            empresa_id=self.empresa.id,
            tipo_documento="CC",
            numero_documento=f"30{suffix}",
            nombres="Ana",
            apellidos="Ruiz",
            estado="ACTIVO",
        )
        db.session.add_all([self.usuario, self.empleado])
        db.session.flush()
        self.contrato = Contrato(
            empleado_id=self.empleado.id,
            tipo_contrato="INDEFINIDO",
            cargo="Analista",
            fecha_inicio=date(2026, 1, 1),
            salario_mensual=2500000,
            horas_semanales=48,
            estado="ACTIVO",
        )
        db.session.add(self.contrato)
        db.session.commit()
        self.client = app.test_client()
        self.headers = {"Authorization": f"Bearer {create_access_token(self.usuario)}"}
        self.payload = {
            "contrato_id": self.contrato.id,
            "fecha_inicio": "2026-06-01",
            "fecha_fin": "2026-06-05",
            "fecha_reintegro": "2026-06-08",
            "dias_habiles": 5,
            "observaciones": "Descanso anual",
        }

    def tearDown(self):
        try:
            db.session.rollback()
            params = {
                "contrato_id": self.contrato.id,
                "empleado_id": self.empleado.id,
                "usuario_id": self.usuario.id,
                "empresa_id": self.empresa.id,
            }
            statements = [
                (
                    "DELETE FROM movimientos_vacaciones WHERE contrato_id = :contrato_id "
                    "OR vacaciones_id IN (SELECT id FROM vacaciones WHERE contrato_id = :contrato_id)",
                    params,
                ),
                ("DELETE FROM vacaciones WHERE contrato_id = :contrato_id", params),
                ("DELETE FROM incapacidades WHERE contrato_id = :contrato_id", params),
                ("DELETE FROM contratos WHERE id = :contrato_id", params),
                ("DELETE FROM empleados WHERE id = :empleado_id", params),
                ("DELETE FROM usuarios WHERE id = :usuario_id", params),
                ("DELETE FROM empresas WHERE id = :empresa_id", params),
            ]
            for statement, statement_params in statements:
                db.session.execute(text(statement), statement_params)
            db.session.commit()
        except Exception as error:
            db.session.rollback()
            self.fail(f"No se pudo borrar la prueba: {error}")
        finally:
            self.context.pop()

    def test_crud_vacacion_movimiento_y_saldo(self):
        created = self.client.post("/vacaciones", headers=self.headers, json=self.payload)
        self.assertEqual(created.status_code, 201, created.get_json())
        vacacion = created.get_json()["vacacion"]
        vacacion_id = vacacion["id"]
        self.assertEqual(vacacion["estado"], "SOLICITADA")
        self.assertIsNone(vacacion["aprobada_por"])
        self.assertEqual(vacacion["dias_habiles"], 5.0)

        listed = self.client.get(
            f"/vacaciones?contrato_id={self.contrato.id}&estado=SOLICITADA",
            headers=self.headers,
        )
        self.assertEqual(listed.status_code, 200, listed.get_json())
        self.assertEqual(listed.get_json()["pagination"]["total"], 1)

        shown = self.client.get(f"/vacaciones/{vacacion_id}", headers=self.headers)
        self.assertEqual(shown.status_code, 200, shown.get_json())
        self.assertEqual(shown.get_json()["vacacion"]["id"], vacacion_id)

        causacion = self.client.post(
            "/movimientos-vacaciones",
            headers=self.headers,
            json={
                "contrato_id": self.contrato.id,
                "fecha": "2026-05-31",
                "tipo": "CAUSACION",
                "dias": 15,
                "observacion": "Causación del periodo",
            },
        )
        self.assertEqual(causacion.status_code, 201, causacion.get_json())
        movimiento_id = causacion.get_json()["movimiento"]["id"]

        saldo = self.client.get(
            f"/vacaciones/saldos?contrato_id={self.contrato.id}",
            headers=self.headers,
        )
        self.assertEqual(saldo.status_code, 200, saldo.get_json())
        self.assertEqual(saldo.get_json()["items"][0]["dias_saldo"], 15.0)
        self.assertEqual(saldo.get_json()["items"][0]["empleado_id"], self.empleado.id)

        disfrutada = self.client.patch(
            f"/vacaciones/{vacacion_id}",
            headers=self.headers,
            json={"estado": "DISFRUTADA"},
        )
        self.assertEqual(disfrutada.status_code, 200, disfrutada.get_json())
        self.assertEqual(disfrutada.get_json()["vacacion"]["estado"], "DISFRUTADA")
        self.assertEqual(disfrutada.get_json()["vacacion"]["aprobada_por"], self.usuario.id)

        disfrutes = self.client.get(
            f"/movimientos-vacaciones?contrato_id={self.contrato.id}&tipo=DISFRUTE",
            headers=self.headers,
        )
        self.assertEqual(disfrutes.status_code, 200, disfrutes.get_json())
        self.assertEqual(disfrutes.get_json()["pagination"]["total"], 1)
        disfrute = disfrutes.get_json()["items"][0]
        self.assertEqual(disfrute["vacaciones_id"], vacacion_id)
        self.assertEqual(disfrute["dias"], -5.0)

        bloqueado = self.client.delete(
            f"/movimientos-vacaciones/{disfrute['id']}",
            headers=self.headers,
        )
        self.assertEqual(bloqueado.status_code, 409, bloqueado.get_json())

        saldo = self.client.get(
            f"/vacaciones/saldos?contrato_id={self.contrato.id}",
            headers=self.headers,
        )
        self.assertEqual(saldo.get_json()["items"][0]["dias_saldo"], 10.0)

        saldo_negativo = self.client.put(
            f"/movimientos-vacaciones/{movimiento_id}",
            headers=self.headers,
            json={
                "contrato_id": self.contrato.id,
                "fecha": "2026-05-30",
                "tipo": "CAUSACION",
                "dias": 4,
            },
        )
        self.assertEqual(saldo_negativo.status_code, 409, saldo_negativo.get_json())

        conservar_causacion = self.client.delete(
            f"/movimientos-vacaciones/{movimiento_id}",
            headers=self.headers,
        )
        self.assertEqual(conservar_causacion.status_code, 409, conservar_causacion.get_json())

        updated = self.client.patch(
            f"/movimientos-vacaciones/{movimiento_id}",
            headers=self.headers,
            json={"observacion": "Causación ajustada"},
        )
        self.assertEqual(updated.status_code, 200, updated.get_json())
        self.assertEqual(updated.get_json()["movimiento"]["dias"], 15.0)
        self.assertEqual(
            updated.get_json()["movimiento"]["observacion"],
            "Causación ajustada",
        )

        replaced = self.client.put(
            f"/vacaciones/{vacacion_id}",
            headers=self.headers,
            json={
                "contrato_id": self.contrato.id,
                "fecha_inicio": "2026-06-01",
                "fecha_fin": "2026-06-03",
                "dias_habiles": 3,
                "estado": "APROBADA",
            },
        )
        self.assertEqual(replaced.status_code, 200, replaced.get_json())
        body = replaced.get_json()["vacacion"]
        self.assertEqual(body["estado"], "APROBADA")
        self.assertIsNone(body["observaciones"])
        self.assertIsNone(body["fecha_reintegro"])
        self.assertEqual(body["dias_habiles"], 3.0)

        saldo = self.client.get(
            f"/vacaciones/saldos?contrato_id={self.contrato.id}",
            headers=self.headers,
        )
        self.assertEqual(saldo.get_json()["items"][0]["dias_saldo"], 15.0)

        removed_movement = self.client.delete(
            f"/movimientos-vacaciones/{movimiento_id}",
            headers=self.headers,
        )
        self.assertEqual(removed_movement.status_code, 200, removed_movement.get_json())

        removed = self.client.delete(f"/vacaciones/{vacacion_id}", headers=self.headers)
        self.assertEqual(removed.status_code, 200, removed.get_json())
        self.assertEqual(removed.get_json()["vacacion"]["estado"], "CANCELADA")

        missing = self.client.get("/vacaciones/999999", headers=self.headers)
        self.assertEqual(missing.status_code, 404, missing.get_json())

    def test_reglas_de_saldo_fechas_y_cruce(self):
        invalid = self.client.post("/vacaciones", headers=self.headers, json={"contrato_id": 1})
        self.assertEqual(invalid.status_code, 400, invalid.get_json())

        fechas = dict(self.payload)
        fechas["fecha_fin"] = "2026-05-01"
        invalid = self.client.post("/vacaciones", headers=self.headers, json=fechas)
        self.assertEqual(invalid.status_code, 400, invalid.get_json())

        sin_saldo = dict(self.payload)
        sin_saldo["estado"] = "DISFRUTADA"
        denied = self.client.post("/vacaciones", headers=self.headers, json=sin_saldo)
        self.assertEqual(denied.status_code, 409, denied.get_json())

        created = self.client.post("/vacaciones", headers=self.headers, json=self.payload)
        self.assertEqual(created.status_code, 201, created.get_json())

        cruce = dict(self.payload)
        cruce["fecha_inicio"] = "2026-06-05"
        cruce["fecha_fin"] = "2026-06-06"
        cruce["fecha_reintegro"] = "2026-06-07"
        cruce["dias_habiles"] = 1
        overlap = self.client.post("/vacaciones", headers=self.headers, json=cruce)
        self.assertEqual(overlap.status_code, 409, overlap.get_json())

        incapacidad = self.client.post(
            "/incapacidades",
            headers=self.headers,
            json={
                "contrato_id": self.contrato.id,
                "tipo": "ENFERMEDAD_GENERAL",
                "fecha_inicio": "2026-06-03",
                "fecha_fin": "2026-06-04",
            },
        )
        self.assertEqual(incapacidad.status_code, 409, incapacidad.get_json())

        signo = self.client.post(
            "/movimientos-vacaciones",
            headers=self.headers,
            json={
                "contrato_id": self.contrato.id,
                "fecha": "2026-05-31",
                "tipo": "CAUSACION",
                "dias": -1,
            },
        )
        self.assertEqual(signo.status_code, 400, signo.get_json())

        self.contrato.estado = "TERMINADO"
        db.session.commit()
        terminado = self.client.post("/vacaciones", headers=self.headers, json={
            "contrato_id": self.contrato.id,
            "fecha_inicio": "2026-07-01",
            "fecha_fin": "2026-07-02",
            "dias_habiles": 2,
        })
        self.assertEqual(terminado.status_code, 409, terminado.get_json())

    def test_otra_empresa_no_ve_la_vacacion(self):
        created = self.client.post("/vacaciones", headers=self.headers, json=self.payload)
        self.assertEqual(created.status_code, 201, created.get_json())
        vacacion_id = created.get_json()["vacacion"]["id"]

        otra = Empresa(nit=f"710{secrets.token_hex(3)}-2", razon_social="Otra", activa=True)
        db.session.add(otra)
        db.session.flush()
        ajeno = Usuario(
            correo=f"ajeno.vac.{secrets.token_hex(4)}@nomina.local",
            hash_password=generate_password_hash("clave-segura-1"),
            activo=True,
            empresa_id=otra.id,
        )
        db.session.add(ajeno)
        db.session.commit()
        try:
            headers = {"Authorization": f"Bearer {create_access_token(ajeno)}"}
            hidden = self.client.get(f"/vacaciones/{vacacion_id}", headers=headers)
            self.assertEqual(hidden.status_code, 404, hidden.get_json())
            hidden_balance = self.client.get("/vacaciones/saldos", headers=headers)
            self.assertEqual(hidden_balance.status_code, 200, hidden_balance.get_json())
            self.assertEqual(hidden_balance.get_json()["pagination"]["total"], 0)
        finally:
            db.session.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": ajeno.id})
            db.session.execute(text("DELETE FROM empresas WHERE id = :id"), {"id": otra.id})
            db.session.commit()
