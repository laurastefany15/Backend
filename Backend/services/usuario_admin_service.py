from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from extensions import db
from models import Empresa, Usuario, UsuarioEmpresa
from services.acceso_service import perfil_publico
from services.auth_service import (
    AuthValidationError,
    _normalize_email,
    assign_role,
)


class UsuarioAdminValidationError(ValueError):
    pass


class UsuarioAdminNotFoundError(LookupError):
    pass


class UsuarioAdminForbiddenError(PermissionError):
    pass


class UsuarioAdminConflictError(ValueError):
    pass


def _pagination(page, per_page):
    if page < 1:
        raise UsuarioAdminValidationError("page debe ser mayor que cero.")
    if per_page < 1 or per_page > 100:
        raise UsuarioAdminValidationError("per_page debe estar entre 1 y 100.")


def _empresa_ids(value, required):
    if not isinstance(value, list) or any(
        isinstance(empresa_id, bool) or not isinstance(empresa_id, int) or empresa_id < 1
        for empresa_id in value
    ):
        raise UsuarioAdminValidationError(
            "empresa_ids debe ser una lista de enteros positivos."
        )
    if len(set(value)) != len(value):
        raise UsuarioAdminValidationError("empresa_ids no puede repetir empresas.")
    if required and not value:
        raise UsuarioAdminValidationError("Debe relacionar al menos una empresa.")
    return value


def _empresas_del_admin(admin, empresa_ids):
    if not empresa_ids:
        return []
    empresas = Empresa.query.filter(
        Empresa.id.in_(empresa_ids),
        Empresa.propietario_id == admin.id,
        Empresa.activa.is_(True),
    ).all()
    if len(empresas) != len(empresa_ids):
        raise UsuarioAdminForbiddenError(
            "Solo puede relacionar empresas activas creadas por usted."
        )
    return empresas


def _usuario_creado(admin, usuario_id):
    user = db.session.get(Usuario, usuario_id)
    if user is None or user.creado_por_id != admin.id:
        raise UsuarioAdminNotFoundError("Usuario no encontrado.")
    return user


def _reemplazar_empresas(user, empresa_ids):
    UsuarioEmpresa.query.filter_by(usuario_id=user.id).delete()
    for empresa_id in empresa_ids:
        db.session.add(
            UsuarioEmpresa(usuario_id=user.id, empresa_id=empresa_id)
        )


def list_users(admin, page=1, per_page=20):
    _pagination(page, per_page)
    pagination = (
        Usuario.query.filter_by(creado_por_id=admin.id)
        .order_by(Usuario.id)
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return {
        "items": [
            perfil_publico(user, solo_activas=False) for user in pagination.items
        ],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        },
    }


def get_user(admin, usuario_id):
    return perfil_publico(_usuario_creado(admin, usuario_id), solo_activas=False)


def create_user(admin, data):
    if not isinstance(data, dict) or set(data) != {"correo", "password", "empresa_ids"}:
        raise UsuarioAdminValidationError(
            "El cuerpo debe contener correo, password y empresa_ids."
        )
    try:
        correo = _normalize_email(data["correo"])
    except AuthValidationError as error:
        raise UsuarioAdminValidationError(str(error)) from error
    password = data["password"]
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        raise UsuarioAdminValidationError(
            "La contraseña debe tener entre 8 y 128 caracteres."
        )
    empresa_ids = _empresa_ids(data["empresa_ids"], required=True)
    _empresas_del_admin(admin, empresa_ids)
    if Usuario.query.filter(db.func.lower(Usuario.correo) == correo).first() is not None:
        raise UsuarioAdminConflictError("El correo ya está registrado.")

    user = Usuario(
        correo=correo,
        hash_password=generate_password_hash(password),
        creado_por_id=admin.id,
        activo=True,
    )
    db.session.add(user)
    try:
        db.session.flush()
        assign_role(user, "USUARIO")
        _reemplazar_empresas(user, empresa_ids)
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise UsuarioAdminConflictError("El correo ya está registrado.") from error
    except Exception:
        db.session.rollback()
        raise
    return perfil_publico(user, solo_activas=False)


def update_user_companies(admin, usuario_id, data):
    if not isinstance(data, dict) or set(data) != {"empresa_ids"}:
        raise UsuarioAdminValidationError(
            "El cuerpo debe contener únicamente empresa_ids."
        )
    empresa_ids = _empresa_ids(data["empresa_ids"], required=False)
    _empresas_del_admin(admin, empresa_ids)
    user = _usuario_creado(admin, usuario_id)
    if not user.activo:
        raise UsuarioAdminConflictError(
            "No se pueden cambiar las empresas de un usuario inactivo."
        )
    _reemplazar_empresas(user, empresa_ids)
    db.session.commit()
    return perfil_publico(user, solo_activas=False)


def update_user_status(admin, usuario_id, data):
    if (
        not isinstance(data, dict)
        or set(data) != {"activo"}
        or not isinstance(data["activo"], bool)
    ):
        raise UsuarioAdminValidationError(
            "El cuerpo debe contener únicamente activo con true o false."
        )
    user = _usuario_creado(admin, usuario_id)
    user.activo = data["activo"]
    db.session.commit()
    return perfil_publico(user, solo_activas=False)
