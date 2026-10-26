import secrets
import unittest
from datetime import date, timedelta

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from app import app
from extensions import db
from models import (
    ConceptoNomina,
    Contrato,
    DeduccionEmpleado,
    Empleado,
    Empresa,
    HoraExtra,
    Licencia,
    Usuario,
)
from services.auth_service import create_access_token
from services.nomina_service import day_weight, quincena_bounds


def _sum_weights(start, end):
    total = 0
    while start <= end:
        total += day_weight(start)
        start += timedelta(days=1)
    return total


class DiasComercialesTest(unittest.TestCase):
    def test_cada_quincena_vale_15_dias(self):
        for anio, mes in ((2026, 1), (2026, 2), (2028, 2), (2026, 4), (2026, 8)):
            for quincena in (1, 2):
                start, end = quincena_bounds(anio, mes, quincena)
                self.assertEqual(_sum_weights(start, end), 15, (anio, mes, quincena))


class NominaTest(unittest.TestCase):
    def setUp(self):
        self.context = app.app_context()
        self.context.push()
        suffix = secrets.token_hex(4)
        self.empresa = Empresa(nit=f"830{suffix[:6]}-1", razon_social="Empresa nómina", activa=True)
        db.session.add(self.empresa)
        db.session.flush()
        self.usuario = Usuario(
            correo=f"nomina.{suffix}@nomina.local",
            hash_password=generate_password_hash("clave-segura-1"),
            activo=True,
            empresa_id=self.empresa.id,
        )
        self.empleado = Empleado(
            empresa_id=self.empresa.id,
            tipo_documento="CC",
            numero_documento=f"50{suffix}",
            nombres="Carlos",
            apellidos="Pérez",
            estado="ACTIVO",
        )
        self.empleado2 = Empleado(
            empresa_id=self.empresa.id,
            tipo_documento="CC",
            numero_documento=f"51{suffix}",
            nombres="Laura",
            apellidos="Gómez",
            estado="ACTIVO",
        )
        db.session.add_all([self.usuario, self.empleado, self.empleado2])
        db.session.flush()
        self.contrato = Contrato(
            empleado_id=self.empleado.id,
            tipo_contrato="INDEFINIDO",
            cargo="Operario",
            fecha_inicio=date(2026, 1, 1),
            salario_mensual=1800000,
            horas_semanales=42,
            estado="ACTIVO",
        )
        self.contrato2 = Contrato(
            empleado_id=self.empleado2.id,
            tipo_contrato="INDEFINIDO",
            cargo="Auxiliar",
            fecha_inicio=date(2026, 1, 1),
            salario_mensual=1750905,
            horas_semanales=42,
            estado="ACTIVO",
        )
        db.session.add_all([self.contrato, self.contrato2])
        db.session.commit()
        self.client = app.test_client()
        self.headers = {"Authorization": f"Bearer {create_access_token(self.usuario)}"}

    def tearDown(self):
        try:
            db.session.rollback()
            params = {
                "empresa_id": self.empresa.id,
                "c1": self.contrato.id,
                "c2": self.contrato2.id,
                "e1": self.empleado.id,
                "e2": self.empleado2.id,
                "usuario_id": self.usuario.id,
            }
            contratos = "(:c1, :c2)"
            statements = [
                f"UPDATE nominas SET estado = 'BORRADOR' WHERE contrato_id IN {contratos}",
                "DELETE FROM detalles_nomina WHERE nomina_id IN "
                f"(SELECT id FROM nominas WHERE contrato_id IN {contratos})",
                "DELETE FROM pagos_nomina WHERE nomina_id IN "
                f"(SELECT id FROM nominas WHERE contrato_id IN {contratos})",
                f"DELETE FROM nominas WHERE contrato_id IN {contratos}",
                "DELETE FROM periodos_nomina WHERE empresa_id = :empresa_id",
                f"DELETE FROM horas_extras WHERE contrato_id IN {contratos}",
                f"DELETE FROM deducciones_empleado WHERE contrato_id IN {contratos}",
                f"DELETE FROM licencias WHERE contrato_id IN {contratos}",
                f"DELETE FROM movimientos_vacaciones WHERE contrato_id IN {contratos}",
                f"DELETE FROM vacaciones WHERE contrato_id IN {contratos}",
                f"DELETE FROM incapacidades WHERE contrato_id IN {contratos}",
                f"DELETE FROM contratos WHERE id IN {contratos}",
                "DELETE FROM empleados WHERE id IN (:e1, :e2)",
                "DELETE FROM usuarios WHERE id = :usuario_id",
                "DELETE FROM empresas WHERE id = :empresa_id",
            ]
            for statement in statements:
                db.session.execute(text(statement), params)
            db.session.commit()
        except Exception as error:
            db.session.rollback()
            self.fail(f"No se pudo borrar la prueba: {error}")
        finally:
            self.context.pop()

    def _novedades(self):
        hora_extra = self.client.post(
            "/horas-extras",
            headers=self.headers,
            json={
                "contrato_id": self.contrato.id,
                "tipo_codigo": "HED",
                "fecha": "2026-08-05",
                "cantidad_horas": 2,
                "estado": "APROBADA",
            },
        )
        self.assertEqual(hora_extra.status_code, 201, hora_extra.get_json())
        pendiente = self.client.post(
            "/horas-extras",
            headers=self.headers,
            json={
                "contrato_id": self.contrato.id,
                "tipo_codigo": "HEN",
                "fecha": "2026-08-06",
                "cantidad_horas": 1,
            },
        )
        self.assertEqual(pendiente.status_code, 201, pendiente.get_json())
        incapacidad = self.client.post(
            "/incapacidades",
            headers=self.headers,
            json={
                "contrato_id": self.contrato.id,
                "tipo": "ENFERMEDAD_GENERAL",
                "fecha_inicio": "2026-08-10",
                "fecha_fin": "2026-08-12",
            },
        )
        self.assertEqual(incapacidad.status_code, 201, incapacidad.get_json())
        vacacion = self.client.post(
            "/vacaciones",
            headers=self.headers,
            json={
                "contrato_id": self.contrato.id,
                "fecha_inicio": "2026-08-13",
                "fecha_fin": "2026-08-15",
                "dias_habiles": 3,
                "estado": "APROBADA",
            },
        )
        self.assertEqual(vacacion.status_code, 201, vacacion.get_json())
        prestamo = ConceptoNomina.query.filter_by(codigo="PRESTAMO").one()
        self.deduccion = DeduccionEmpleado(
            contrato_id=self.contrato.id,
            concepto_id=prestamo.id,
            descripcion="Préstamo empresa",
            monto_original=80000,
            saldo_pendiente=80000,
            valor_cuota=50000,
            vigente_desde=date(2026, 8, 1),
            periodicidad="POR_PERIODO",
            activa=True,
        )
        db.session.add(self.deduccion)
        db.session.add(
            Licencia(
                contrato_id=self.contrato2.id,
                tipo="PERSONAL",
                remunerada=False,
                fecha_inicio=date(2026, 8, 3),
                fecha_fin=date(2026, 8, 4),
                estado="APROBADA",
            )
        )
        db.session.commit()
        return hora_extra.get_json()["hora_extra"]["id"]

    def _valores(self, nomina):
        valores = {}
        for detalle in nomina["detalles"]:
            valores[detalle["concepto"]] = valores.get(detalle["concepto"], 0) + detalle["valor"]
        return valores

    def test_liquidacion_quincenal(self):
        hora_extra_id = self._novedades()

        individual = self.client.post(
            "/nominas/generar",
            headers=self.headers,
            json={"anio": 2026, "mes": 8, "quincena": 1, "empleado_id": self.empleado.id},
        )
        self.assertEqual(individual.status_code, 201, individual.get_json())
        body = individual.get_json()
        self.assertEqual(body["periodo"]["fecha_inicio"], "2026-08-01")
        self.assertEqual(body["periodo"]["fecha_fin"], "2026-08-15")
        self.assertEqual(len(body["nominas"]), 1)
        self.assertEqual(body["errores"], [])
        nomina = body["nominas"][0]
        valores = self._valores(nomina)
        self.assertAlmostEqual(valores["SALARIO"], 540000.00, places=2)
        self.assertAlmostEqual(valores["HED"], 21428.57, places=2)
        self.assertNotIn("HEN", valores)
        self.assertAlmostEqual(valores["INCAPACIDAD"], 175090.50, places=2)
        self.assertAlmostEqual(valores["VACACIONES"], 180000.00, places=2)
        self.assertAlmostEqual(valores["AUX_TRANSPORTE"], 74728.50, places=2)
        self.assertAlmostEqual(valores["SALUD"], 36660.76, places=2)
        self.assertAlmostEqual(valores["PENSION"], 36660.76, places=2)
        self.assertAlmostEqual(valores["PRESTAMO"], 50000.00, places=2)
        self.assertAlmostEqual(nomina["total_devengado"], 991247.57, places=2)
        self.assertAlmostEqual(nomina["total_deducciones"], 123321.52, places=2)
        self.assertAlmostEqual(nomina["neto_pagar"], 867926.05, places=2)
        self.assertEqual(nomina["estado"], "BORRADOR")
        nomina_id = nomina["id"]
        periodo_id = body["periodo"]["id"]

        todos = self.client.post(
            "/nominas/generar",
            headers=self.headers,
            json={"fecha": "2026-08-10"},
        )
        self.assertEqual(todos.status_code, 201, todos.get_json())
        nominas = {n["contrato_id"]: n for n in todos.get_json()["nominas"]}
        self.assertEqual(set(nominas), {self.contrato.id, self.contrato2.id})
        self.assertEqual(nominas[self.contrato.id]["id"], nomina_id)
        segunda = nominas[self.contrato2.id]
        valores = self._valores(segunda)
        self.assertAlmostEqual(valores["SALARIO"], 758725.50, places=2)
        self.assertAlmostEqual(valores["AUX_TRANSPORTE"], 107941.17, places=2)
        self.assertAlmostEqual(valores["SALUD"], 30349.02, places=2)
        self.assertAlmostEqual(segunda["neto_pagar"], 805968.63, places=2)
        self.assertIn("Licencia no remunerada", segunda["observaciones"])

        aprobada = self.client.post(f"/nominas/{nomina_id}/aprobar", headers=self.headers)
        self.assertEqual(aprobada.status_code, 200, aprobada.get_json())
        self.assertEqual(aprobada.get_json()["nomina"]["estado"], "APROBADA")
        db.session.expire_all()
        self.assertEqual(db.session.get(HoraExtra, hora_extra_id).estado, "LIQUIDADA")
        self.assertEqual(float(db.session.get(DeduccionEmpleado, self.deduccion.id).saldo_pendiente), 30000)
        bloqueada = self.client.patch(
            f"/horas-extras/{hora_extra_id}",
            headers=self.headers,
            json={"cantidad_horas": 3},
        )
        self.assertEqual(bloqueada.status_code, 409, bloqueada.get_json())

        otra_vez = self.client.post(
            "/nominas/generar",
            headers=self.headers,
            json={"fecha": "2026-08-01"},
        )
        self.assertEqual(otra_vez.status_code, 201, otra_vez.get_json())
        self.assertEqual(otra_vez.get_json()["omitidas"][0]["nomina_id"], nomina_id)

        no_cierra = self.client.post(f"/nominas/periodos/{periodo_id}/cerrar", headers=self.headers)
        self.assertEqual(no_cierra.status_code, 409, no_cierra.get_json())
        por_periodo = self.client.post(f"/nominas/periodos/{periodo_id}/aprobar", headers=self.headers)
        self.assertEqual(por_periodo.status_code, 200, por_periodo.get_json())
        self.assertEqual(por_periodo.get_json()["aprobadas"], [segunda["id"]])

        pagada = self.client.post(
            f"/nominas/{nomina_id}/pagar",
            headers=self.headers,
            json={"medio": "TRANSFERENCIA", "referencia": "TRX-1"},
        )
        self.assertEqual(pagada.status_code, 200, pagada.get_json())
        self.assertEqual(pagada.get_json()["nomina"]["estado"], "PAGADA")
        self.assertAlmostEqual(pagada.get_json()["nomina"]["pagos"][0]["valor"], 867926.05, places=2)
        no_anula = self.client.post(f"/nominas/{nomina_id}/anular", headers=self.headers)
        self.assertEqual(no_anula.status_code, 409, no_anula.get_json())

        anulada = self.client.post(f"/nominas/{segunda['id']}/anular", headers=self.headers)
        self.assertEqual(anulada.status_code, 200, anulada.get_json())
        self.assertEqual(anulada.get_json()["nomina"]["estado"], "ANULADA")

        periodo = self.client.get(f"/nominas/periodos/{periodo_id}", headers=self.headers)
        resumen = periodo.get_json()["periodo"]["resumen"]
        self.assertEqual(resumen["por_estado"], {"PAGADA": 1, "ANULADA": 1})
        self.assertAlmostEqual(resumen["neto_pagar"], 867926.05, places=2)

        listado = self.client.get(
            f"/nominas?periodo_id={periodo_id}&empleado_id={self.empleado.id}",
            headers=self.headers,
        )
        self.assertEqual(listado.get_json()["pagination"]["total"], 1)

        cerrado = self.client.post(f"/nominas/periodos/{periodo_id}/cerrar", headers=self.headers)
        self.assertEqual(cerrado.status_code, 200, cerrado.get_json())
        bloqueado = self.client.post(
            "/nominas/generar",
            headers=self.headers,
            json={"fecha": "2026-08-01"},
        )
        self.assertEqual(bloqueado.status_code, 409, bloqueado.get_json())

    def test_anular_aprobada_revierte_novedades_y_otra_empresa_no_ve(self):
        hora_extra_id = self._novedades()
        generada = self.client.post(
            "/nominas/generar",
            headers=self.headers,
            json={"anio": 2026, "mes": 8, "quincena": 1, "contrato_id": self.contrato.id},
        )
        nomina_id = generada.get_json()["nominas"][0]["id"]
        self.client.post(f"/nominas/{nomina_id}/aprobar", headers=self.headers)
        anulada = self.client.post(f"/nominas/{nomina_id}/anular", headers=self.headers)
        self.assertEqual(anulada.status_code, 200, anulada.get_json())
        db.session.expire_all()
        self.assertEqual(db.session.get(HoraExtra, hora_extra_id).estado, "APROBADA")
        self.assertEqual(float(db.session.get(DeduccionEmpleado, self.deduccion.id).saldo_pendiente), 80000)

        regenerada = self.client.post(
            "/nominas/generar",
            headers=self.headers,
            json={"anio": 2026, "mes": 8, "quincena": 1, "contrato_id": self.contrato.id},
        )
        self.assertEqual(regenerada.status_code, 201, regenerada.get_json())
        self.assertEqual(regenerada.get_json()["nominas"][0]["id"], nomina_id)
        self.assertEqual(regenerada.get_json()["nominas"][0]["estado"], "BORRADOR")

        otra = Empresa(nit=f"740{secrets.token_hex(3)}-5", razon_social="Otra", activa=True)
        db.session.add(otra)
        db.session.flush()
        ajeno = Usuario(
            correo=f"ajeno.nom.{secrets.token_hex(4)}@nomina.local",
            hash_password=generate_password_hash("clave-segura-1"),
            activo=True,
            empresa_id=otra.id,
        )
        db.session.add(ajeno)
        db.session.commit()
        try:
            headers = {"Authorization": f"Bearer {create_access_token(ajeno)}"}
            hidden = self.client.get(f"/nominas/{nomina_id}", headers=headers)
            self.assertEqual(hidden.status_code, 404, hidden.get_json())
            ajena = self.client.post(
                "/nominas/generar",
                headers=headers,
                json={"fecha": "2026-08-01", "empleado_id": self.empleado.id},
            )
            self.assertEqual(ajena.status_code, 404, ajena.get_json())
        finally:
            db.session.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": ajeno.id})
            db.session.execute(text("DELETE FROM empresas WHERE id = :id"), {"id": otra.id})
            db.session.commit()

    def test_reporta_parametros_faltantes_y_valida_entrada(self):
        sin_smmlv = self.client.post(
            "/nominas/generar",
            headers=self.headers,
            json={"anio": 2026, "mes": 1, "quincena": 1},
        )
        self.assertEqual(sin_smmlv.status_code, 200, sin_smmlv.get_json())
        errores = sin_smmlv.get_json()["errores"]
        self.assertEqual(len(errores), 2)
        self.assertIn("SMMLV", errores[0]["error"])

        invalida = self.client.post(
            "/nominas/generar",
            headers=self.headers,
            json={"anio": 2026, "mes": 13, "quincena": 1},
        )
        self.assertEqual(invalida.status_code, 400, invalida.get_json())
        incompleta = self.client.post("/nominas/generar", headers=self.headers, json={"mes": 8})
        self.assertEqual(incompleta.status_code, 400, incompleta.get_json())


if __name__ == "__main__":
    unittest.main()
