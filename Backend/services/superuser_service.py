from extensions import db
from models import Empleado, Empresa, Nomina, Usuario, UsuarioEmpresa
from services.acceso_service import perfil_detallado, tiene_rol


class SuperuserValidationError(ValueError):
    pass


class SuperuserNotFoundError(LookupError):
    pass


class SuperuserConflictError(ValueError):
    pass


def _pagination(page, per_page):
    if page < 1:
        raise SuperuserValidationError("page debe ser mayor que cero.")
    if per_page < 1 or per_page > 100:
        raise SuperuserValidationError("per_page debe estar entre 1 y 100.")


def _parse_activa(activa):
    if activa is None:
        return None
    if not isinstance(activa, str):
        raise SuperuserValidationError("activa debe ser true o false.")
    normalized = activa.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise SuperuserValidationError("activa debe ser true o false.")


def resumen():
    return {
        "empresas": Empresa.query.count(),
        "empresas_activas": Empresa.query.filter_by(activa=True).count(),
        "usuarios": Usuario.query.count(),
        "usuarios_activos": Usuario.query.filter_by(activo=True).count(),
        "empleados": Empleado.query.count(),
        "nominas": Nomina.query.count(),
    }


def _serialize_empresa(empresa):
    propietario = (
        db.session.get(Usuario, empresa.propietario_id)
        if empresa.propietario_id
        else None
    )
    return {
        "id": empresa.id,
        "nit": empresa.nit,
        "razon_social": empresa.razon_social,
        "direccion": empresa.direccion,
        "telefono": empresa.telefono,
        "correo": empresa.correo,
        "activa": empresa.activa,
        "propietario": (
            None
            if propietario is None
            else {"id": propietario.id, "correo": propietario.correo}
        ),
        "usuarios": UsuarioEmpresa.query.filter_by(empresa_id=empresa.id).count(),
        "empleados": Empleado.query.filter_by(empresa_id=empresa.id).count(),
    }


def list_companies(page=1, per_page=20, activa=None):
    _pagination(page, per_page)
    query = Empresa.query
    parsed = _parse_activa(activa)
    if parsed is not None:
        query = query.filter_by(activa=parsed)
    pagination = query.order_by(Empresa.id).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return {
        "items": [_serialize_empresa(empresa) for empresa in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        },
    }


def get_company(empresa_id):
    empresa = db.session.get(Empresa, empresa_id)
    if empresa is None:
        raise SuperuserNotFoundError("Empresa no encontrada.")
    return _serialize_empresa(empresa)


def list_users(page=1, per_page=20):
    _pagination(page, per_page)
    pagination = Usuario.query.order_by(Usuario.id).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return {
        "items": [perfil_detallado(user) for user in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        },
    }


def update_user_status(actor, usuario_id, data):
    if (
        not isinstance(data, dict)
        or set(data) != {"activo"}
        or not isinstance(data["activo"], bool)
    ):
        raise SuperuserValidationError(
            "El cuerpo debe contener únicamente activo con true o false."
        )
    user = db.session.get(Usuario, usuario_id)
    if user is None:
        raise SuperuserNotFoundError("Usuario no encontrado.")
    if user.id == actor.id:
        raise SuperuserConflictError("No puede cambiar el estado de su propia cuenta.")
    if tiene_rol(user, "SUPERUSER"):
        raise SuperuserConflictError(
            "No se puede cambiar el estado de un superusuario."
        )
    user.activo = data["activo"]
    db.session.commit()
    return perfil_detallado(user)
