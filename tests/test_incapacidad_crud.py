import io
import os
import secrets
import shutil
import tempfile
import unittest
from datetime import date

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from app import app
from extensions import db
from models import Contrato, Empleado, Empresa, Usuario
from services.auth_service import create_access_token


class IncapacidadCrudTest(unittest.TestCase):
    def setUp(self):
        self.context = app.app_context()
        self.context.push()
        self.upload_dir = tempfile.mkdtemp(prefix="incapacidades-")
        self.previous_upload_dir = app.config.get("UPLOAD_FOLDER")
        app.config["UPLOAD_FOLDER"] = self.upload_dir
        suffix = secrets.token_hex(4)
        self.empresa = Empresa(
            nit=f"820{suffix[:6]}-1",
            razon_social="Empresa incapacidades",
            activa=True,
        )
        db.session.add(self.empresa)
        db.session.flush()
        self.usuario = Usuario(
            correo=f"incapacidad.{suffix}@nomina.local",
            hash_password=generate_password_hash("clave-segura-1"),
            activo=True,
            empresa_id=self.empresa.id,
        )
        self.empleado = Empleado(
            empresa_id=self.empresa.id,
            tipo_documento="CC",
            numero_documento=f"40{suffix}",
            nombres="Marta",
            apellidos="Diaz",
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
        self.headers = {"Authorization": f"Bearer {create_access_token(self.usuario)}"}
        self.payload = {
            "contrato_id": self.contrato.id,
            "tipo": "ENFERMEDAD_GENERAL",
            "fecha_inicio": "2026-04-01",
            "fecha_fin": "2026-04-03",
            "entidad_responsable": "EPS Ejemplo",
            "numero_certificado": "INC-100",
            "porcentaje_reconocimiento": 66.67,
            "valor_estimado": 180000,
            "observaciones": "Gripa",
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
                    "DELETE FROM documentos_incapacidad WHERE incapacidad_id IN "
                    "(SELECT id FROM incapacidades WHERE contrato_id = :contrato_id)",
                    params,
                ),
                ("DELETE FROM incapacidades WHERE contrato_id = :contrato_id", params),
                ("DELETE FROM vacaciones WHERE contrato_id = :contrato_id", params),
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
            app.config["UPLOAD_FOLDER"] = self.previous_upload_dir
            shutil.rmtree(self.upload_dir, ignore_errors=True)
            self.context.pop()

    def _pdf(self, name="certificado.pdf"):
        return (io.BytesIO(b"%PDF-1.4\n%prueba\n"), name)

    def test_incapacidad_sin_soporte_eps(self):
        created = self.client.post(
            "/incapacidades",
            headers=self.headers,
            json={
                "contrato_id": self.contrato.id,
                "tipo": "ENFERMEDAD_GENERAL",
                "fecha_inicio": "2026-05-04",
                "fecha_fin": "2026-05-05",
            },
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        body = created.get_json()["incapacidad"]
        self.assertIsNone(body["entidad_responsable"])
        self.assertIsNone(body["numero_certificado"])
        self.assertEqual(body["documentos"], [])

        validated = self.client.patch(
            f"/incapacidades/{body['id']}",
            headers=self.headers,
            json={"estado": "VALIDADA"},
        )
        self.assertEqual(validated.status_code, 200, validated.get_json())

        url = self.client.post(
            "/incapacidades",
            headers=self.headers,
            json={**self.payload, "documento_soporte_url": "https://example.com/a.pdf"},
        )
        self.assertEqual(url.status_code, 400, url.get_json())

    def test_documentos_se_guardan_en_el_servidor(self):
        created = self.client.post(
            "/incapacidades",
            headers=self.headers,
            data={
                "contrato_id": str(self.contrato.id),
                "tipo": "ENFERMEDAD_GENERAL",
                "fecha_inicio": "2026-04-01",
                "fecha_fin": "2026-04-03",
                "valor_estimado": "180000",
                "entidad_responsable": "",
                "tipo_documento": "CERTIFICADO_EPS",
                "documentos": [self._pdf()],
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        incapacidad = created.get_json()["incapacidad"]
        incapacidad_id = incapacidad["id"]
        self.assertIsNone(incapacidad["entidad_responsable"])
        self.assertEqual(incapacidad["valor_estimado"], 180000.0)
        self.assertEqual(len(incapacidad["documentos"]), 1)
        documento = incapacidad["documentos"][0]
        self.assertEqual(documento["tipo"], "CERTIFICADO_EPS")
        self.assertEqual(documento["nombre_original"], "certificado.pdf")
        stored = os.listdir(os.path.join(self.upload_dir, "incapacidades", str(incapacidad_id)))
        self.assertEqual(len(stored), 1)
        self.assertNotIn("certificado", stored[0])

        uploaded = self.client.post(
            f"/incapacidades/{incapacidad_id}/documentos",
            headers=self.headers,
            data={
                "tipo": "HISTORIA_CLINICA",
                "documentos": [
                    (io.BytesIO(b"\x89PNG\r\n\x1a\nimagen"), "historia.png"),
                    (io.BytesIO(b"\xff\xd8\xff\xe0foto"), "../../soporte.jpg"),
                ],
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(uploaded.status_code, 201, uploaded.get_json())
        nuevos = uploaded.get_json()["documentos"]
        self.assertEqual([d["nombre_original"] for d in nuevos], ["historia.png", "soporte.jpg"])

        listed = self.client.get(f"/incapacidades/{incapacidad_id}/documentos", headers=self.headers)
        self.assertEqual(listed.status_code, 200, listed.get_json())
        self.assertEqual(len(listed.get_json()["items"]), 3)

        downloaded = self.client.get(documento["descarga"], headers=self.headers)
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.data, b"%PDF-1.4\n%prueba\n")
        self.assertEqual(downloaded.mimetype, "application/pdf")
        downloaded.close()

        disfrazado = self.client.post(
            f"/incapacidades/{incapacidad_id}/documentos",
            headers=self.headers,
            data={"documentos": [(io.BytesIO(b"MZ ejecutable"), "falso.pdf")]},
            content_type="multipart/form-data",
        )
        self.assertEqual(disfrazado.status_code, 400, disfrazado.get_json())
        extension = self.client.post(
            f"/incapacidades/{incapacidad_id}/documentos",
            headers=self.headers,
            data={"documentos": [(io.BytesIO(b"hola"), "notas.exe")]},
            content_type="multipart/form-data",
        )
        self.assertEqual(extension.status_code, 400, extension.get_json())
        vacio = self.client.post(
            f"/incapacidades/{incapacidad_id}/documentos",
            headers=self.headers,
            data={"tipo": "OTRO"},
            content_type="multipart/form-data",
        )
        self.assertEqual(vacio.status_code, 400, vacio.get_json())

        invalida = self.client.post(
            "/incapacidades",
            headers=self.headers,
            data={
                "contrato_id": str(self.contrato.id),
                "tipo": "OTRA",
                "fecha_inicio": "2026-09-01",
                "fecha_fin": "2026-09-02",
                "documentos": [(io.BytesIO(b"no es pdf"), "x.pdf")],
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(invalida.status_code, 400, invalida.get_json())
        total = self.client.get(
            f"/incapacidades?contrato_id={self.contrato.id}",
            headers=self.headers,
        )
        self.assertEqual(total.get_json()["pagination"]["total"], 1)

        otra = Empresa(nit=f"730{secrets.token_hex(3)}-4", razon_social="Otra", activa=True)
        db.session.add(otra)
        db.session.flush()
        ajeno = Usuario(
            correo=f"ajeno.doc.{secrets.token_hex(4)}@nomina.local",
            hash_password=generate_password_hash("clave-segura-1"),
            activo=True,
            empresa_id=otra.id,
        )
        db.session.add(ajeno)
        db.session.commit()
        try:
            headers = {"Authorization": f"Bearer {create_access_token(ajeno)}"}
            hidden = self.client.get(documento["descarga"], headers=headers)
            self.assertEqual(hidden.status_code, 404, hidden.get_json())
        finally:
            db.session.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": ajeno.id})
            db.session.execute(text("DELETE FROM empresas WHERE id = :id"), {"id": otra.id})
            db.session.commit()

        removed = self.client.delete(
            f"/incapacidades/{incapacidad_id}/documentos/{documento['id']}",
            headers=self.headers,
        )
        self.assertEqual(removed.status_code, 200, removed.get_json())
        stored = os.listdir(os.path.join(self.upload_dir, "incapacidades", str(incapacidad_id)))
        self.assertEqual(len(stored), 2)
        gone = self.client.get(documento["descarga"], headers=self.headers)
        self.assertEqual(gone.status_code, 404, gone.get_json())

    def test_crud_incapacidad(self):
        created = self.client.post("/incapacidades", headers=self.headers, json=self.payload)
        self.assertEqual(created.status_code, 201, created.get_json())
        incapacidad = created.get_json()["incapacidad"]
        incapacidad_id = incapacidad["id"]
        self.assertEqual(incapacidad["estado"], "REGISTRADA")
        self.assertEqual(incapacidad["porcentaje_reconocimiento"], 66.67)
        self.assertEqual(incapacidad["valor_estimado"], 180000.0)

        listed = self.client.get(
            f"/incapacidades?contrato_id={self.contrato.id}&estado=REGISTRADA&tipo=ENFERMEDAD_GENERAL",
            headers=self.headers,
        )
        self.assertEqual(listed.status_code, 200, listed.get_json())
        self.assertEqual(listed.get_json()["pagination"]["total"], 1)

        shown = self.client.get(f"/incapacidades/{incapacidad_id}", headers=self.headers)
        self.assertEqual(shown.status_code, 200, shown.get_json())
        self.assertEqual(shown.get_json()["incapacidad"]["id"], incapacidad_id)

        updated = self.client.put(
            f"/incapacidades/{incapacidad_id}",
            headers=self.headers,
            json={
                "contrato_id": self.contrato.id,
                "tipo": "ACCIDENTE_LABORAL",
                "fecha_inicio": "2026-04-01",
                "fecha_fin": "2026-04-05",
                "valor_reconocido": 150000,
                "estado": "VALIDADA",
            },
        )
        self.assertEqual(updated.status_code, 200, updated.get_json())
        body = updated.get_json()["incapacidad"]
        self.assertEqual(body["tipo"], "ACCIDENTE_LABORAL")
        self.assertEqual(body["estado"], "VALIDADA")
        self.assertEqual(body["valor_reconocido"], 150000.0)
        self.assertIsNone(body["observaciones"])
        self.assertIsNone(body["entidad_responsable"])
        self.assertIsNone(body["porcentaje_reconocimiento"])

        invalid = self.client.post(
            "/incapacidades",
            headers=self.headers,
            json={"contrato_id": self.contrato.id, "tipo": "OTRA"},
        )
        self.assertEqual(invalid.status_code, 400, invalid.get_json())

        cruce = self.client.post(
            "/incapacidades",
            headers=self.headers,
            json={
                "contrato_id": self.contrato.id,
                "tipo": "OTRA",
                "fecha_inicio": "2026-04-05",
                "fecha_fin": "2026-04-06",
            },
        )
        self.assertEqual(cruce.status_code, 409, cruce.get_json())

        removed = self.client.delete(
            f"/incapacidades/{incapacidad_id}",
            headers=self.headers,
        )
        self.assertEqual(removed.status_code, 200, removed.get_json())
        self.assertEqual(removed.get_json()["incapacidad"]["estado"], "RECHAZADA")

        posterior = self.client.post(
            "/incapacidades",
            headers=self.headers,
            json={
                "contrato_id": self.contrato.id,
                "tipo": "OTRA",
                "fecha_inicio": "2026-04-05",
                "fecha_fin": "2026-04-06",
            },
        )
        self.assertEqual(posterior.status_code, 201, posterior.get_json())

        missing = self.client.get("/incapacidades/999999", headers=self.headers)
        self.assertEqual(missing.status_code, 404, missing.get_json())

    def test_no_cruza_vacacion_ni_otra_empresa(self):
        vacacion = self.client.post(
            "/vacaciones",
            headers=self.headers,
            json={
                "contrato_id": self.contrato.id,
                "fecha_inicio": "2026-08-03",
                "fecha_fin": "2026-08-07",
                "dias_habiles": 5,
            },
        )
        self.assertEqual(vacacion.status_code, 201, vacacion.get_json())

        cruce = self.client.post(
            "/incapacidades",
            headers=self.headers,
            json={
                "contrato_id": self.contrato.id,
                "tipo": "MATERNIDAD",
                "fecha_inicio": "2026-08-07",
                "fecha_fin": "2026-08-10",
            },
        )
        self.assertEqual(cruce.status_code, 409, cruce.get_json())

        created = self.client.post("/incapacidades", headers=self.headers, json=self.payload)
        self.assertEqual(created.status_code, 201, created.get_json())
        incapacidad_id = created.get_json()["incapacidad"]["id"]

        otra = Empresa(nit=f"720{secrets.token_hex(3)}-3", razon_social="Otra", activa=True)
        db.session.add(otra)
        db.session.flush()
        ajeno = Usuario(
            correo=f"ajeno.inc.{secrets.token_hex(4)}@nomina.local",
            hash_password=generate_password_hash("clave-segura-1"),
            activo=True,
            empresa_id=otra.id,
        )
        db.session.add(ajeno)
        db.session.commit()
        try:
            headers = {"Authorization": f"Bearer {create_access_token(ajeno)}"}
            hidden = self.client.get(f"/incapacidades/{incapacidad_id}", headers=headers)
            self.assertEqual(hidden.status_code, 404, hidden.get_json())
        finally:
            db.session.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": ajeno.id})
            db.session.execute(text("DELETE FROM empresas WHERE id = :id"), {"id": otra.id})
            db.session.commit()
