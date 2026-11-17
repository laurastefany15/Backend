import secrets
import unittest

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from app import app
from extensions import db
from models import Rol, Usuario, UsuarioRol
from services.auth_service import create_access_token


class AccesoUsuariosTest(unittest.TestCase):
    def setUp(self):
        self.context = app.app_context()
        self.context.push()
        self.client = app.test_client()
        self.suffix = secrets.token_hex(4)
        self.user_ids = []
        self.empresa_ids = []
        self.empleado_ids = []

    def tearDown(self):
        try:
            db.session.rollback()
            for empleado_id in self.empleado_ids:
                db.session.execute(
                    text("DELETE FROM empleados WHERE id = :id"),
                    {"id": empleado_id},
                )
            for user_id in self.user_ids:
                db.session.execute(
                    text("DELETE FROM usuarios_empresas WHERE usuario_id = :id"),
                    {"id": user_id},
                )
            for empresa_id in self.empresa_ids:
                db.session.execute(
                    text("DELETE FROM empresas WHERE id = :id"),
                    {"id": empresa_id},
                )
            for user_id in self.user_ids:
                db.session.execute(
                    text("DELETE FROM usuarios_roles WHERE usuario_id = :id"),
                    {"id": user_id},
                )
                db.session.execute(
                    text("DELETE FROM usuarios WHERE id = :id"),
                    {"id": user_id},
                )
            db.session.commit()
        except Exception as error:
            db.session.rollback()
            self.fail(f"No se pudo borrar la prueba: {error}")
        finally:
            self.context.pop()

    def _headers(self, token, empresa_id=None):
        headers = {"Authorization": f"Bearer {token}"}
        if empresa_id is not None:
            headers["X-Empresa-Id"] = str(empresa_id)
        return headers

    def _registrar_admin(self, nombre):
        correo = f"{nombre}.{self.suffix}@nomina.local"
        creado = self.client.post(
            "/auth/register",
            json={"correo": correo, "password": "clave-segura-1"},
        )
        self.assertEqual(creado.status_code, 201, creado.get_json())
        usuario = creado.get_json()["user"]
        self.user_ids.append(usuario["id"])
        self.assertEqual(usuario["roles"], ["ADMIN"])
        login = self.client.post(
            "/auth/login",
            json={"correo": correo, "password": "clave-segura-1"},
        )
        self.assertEqual(login.status_code, 200, login.get_json())
        return login.get_json()["access_token"], usuario

    def _crear_empresa(self, token, nit):
        creada = self.client.post(
            "/admin/empresas",
            headers=self._headers(token),
            json={"nit": nit, "razon_social": f"Tienda {nit}"},
        )
        self.assertEqual(creada.status_code, 201, creada.get_json())
        empresa = creada.get_json()["empresa"]
        self.empresa_ids.append(empresa["id"])
        return empresa

    def _crear_empleado(self, token, empresa_id, documento):
        creado = self.client.post(
            "/empleados",
            headers=self._headers(token, empresa_id),
            json={
                "tipo_documento": "CC",
                "numero_documento": documento,
                "nombres": "Ana",
                "apellidos": "Paz",
            },
        )
        self.assertEqual(creado.status_code, 201, creado.get_json())
        empleado_id = creado.get_json()["empleado"]["id"]
        self.empleado_ids.append(empleado_id)
        return empleado_id

    def test_admin_crea_empresa_usuarios_y_limita_el_acceso(self):
        token, admin = self._registrar_admin("admin")
        empresa = self._crear_empresa(token, f"900{self.suffix[:6]}-1")
        self.assertEqual(empresa["propietario_id"], admin["id"])
        self._crear_empleado(token, None, f"60{self.suffix}")

        creado = self.client.post(
            "/admin/usuarios",
            headers=self._headers(token),
            json={
                "correo": f"cajero.{self.suffix}@nomina.local",
                "password": "clave-segura-1",
                "empresa_ids": [empresa["id"]],
            },
        )
        self.assertEqual(creado.status_code, 201, creado.get_json())
        usuario = creado.get_json()["usuario"]
        self.user_ids.append(usuario["id"])
        self.assertEqual(usuario["roles"], ["USUARIO"])
        self.assertEqual(usuario["empresas"][0]["id"], empresa["id"])

        login = self.client.post(
            "/auth/login",
            json={
                "correo": f"cajero.{self.suffix}@nomina.local",
                "password": "clave-segura-1",
            },
        )
        self.assertEqual(login.status_code, 200, login.get_json())
        token_usuario = login.get_json()["access_token"]
        propios = self.client.get("/empleados", headers=self._headers(token_usuario))
        self.assertEqual(propios.status_code, 200, propios.get_json())
        self.assertEqual(propios.get_json()["pagination"]["total"], 1)

        self.assertEqual(
            self.client.post(
                "/admin/empresas",
                headers=self._headers(token_usuario),
                json={"nit": f"901{self.suffix[:6]}-9", "razon_social": "Ajena"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/admin/usuarios",
                headers=self._headers(token_usuario),
                json={
                    "correo": f"otro.{self.suffix}@nomina.local",
                    "password": "clave-segura-1",
                    "empresa_ids": [empresa["id"]],
                },
            ).status_code,
            403,
        )

        otra = self._crear_empresa(token, f"901{self.suffix[:6]}-2")
        self._crear_empleado(token, otra["id"], f"61{self.suffix}")
        ajeno = self.client.get(
            "/empleados",
            headers=self._headers(token_usuario, otra["id"]),
        )
        self.assertEqual(ajeno.status_code, 403, ajeno.get_json())

        asignada = self.client.put(
            f"/admin/usuarios/{usuario['id']}/empresas",
            headers=self._headers(token),
            json={"empresa_ids": [empresa["id"], otra["id"]]},
        )
        self.assertEqual(asignada.status_code, 200, asignada.get_json())
        sin_empresa = self.client.get(
            "/empleados",
            headers=self._headers(token_usuario),
        )
        self.assertEqual(sin_empresa.status_code, 400, sin_empresa.get_json())
        self.assertIn("X-Empresa-Id", sin_empresa.get_json()["error"])
        de_otra = self.client.get(
            "/empleados",
            headers=self._headers(token_usuario, otra["id"]),
        )
        self.assertEqual(de_otra.status_code, 200, de_otra.get_json())
        self.assertEqual(de_otra.get_json()["pagination"]["total"], 1)

        token_otro, _otro = self._registrar_admin("dueno")
        oculta = self.client.get(
            f"/admin/empresas/{empresa['id']}",
            headers=self._headers(token_otro),
        )
        self.assertEqual(oculta.status_code, 404, oculta.get_json())

    def test_superusuario_ve_el_resumen_y_no_opera_como_admin(self):
        token_admin, _admin = self._registrar_admin("local")
        self._crear_empresa(token_admin, f"910{self.suffix[:6]}-1")
        rol = Rol.query.filter_by(codigo="SUPERUSER").one()
        superuser = Usuario(
            correo=f"super.{self.suffix}@nomina.local",
            hash_password=generate_password_hash("clave-segura-1"),
            activo=True,
        )
        db.session.add(superuser)
        db.session.flush()
        db.session.add(UsuarioRol(usuario_id=superuser.id, rol_id=rol.id))
        db.session.commit()
        self.user_ids.append(superuser.id)
        token = create_access_token(superuser)

        resumen = self.client.get("/superuser/resumen", headers=self._headers(token))
        self.assertEqual(resumen.status_code, 200, resumen.get_json())
        self.assertGreaterEqual(resumen.get_json()["empresas"], 1)
        self.assertGreaterEqual(resumen.get_json()["usuarios"], 2)

        empresas = self.client.get("/superuser/empresas", headers=self._headers(token))
        self.assertEqual(empresas.status_code, 200, empresas.get_json())
        self.assertGreaterEqual(empresas.get_json()["pagination"]["total"], 1)

        prohibido = self.client.get(
            "/superuser/resumen",
            headers=self._headers(token_admin),
        )
        self.assertEqual(prohibido.status_code, 403, prohibido.get_json())
        self.assertEqual(
            self.client.post(
                "/admin/empresas",
                headers=self._headers(token),
                json={"nit": f"910{self.suffix[:6]}-8", "razon_social": "No"},
            ).status_code,
            403,
        )


if __name__ == "__main__":
    unittest.main()
