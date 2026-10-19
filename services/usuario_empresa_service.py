from extensions import db
from models import Empresa, Usuario


class UsuarioEmpresaNotFoundError(LookupError):
    pass


class UsuarioEmpresaConflictError(ValueError):
    pass


class UsuarioEmpresaValidationError(ValueError):
    pass


def _serialize_empresa(empresa):
    if empresa is None:
        return None
    return {
        "id": empresa.id,
        "nit": empresa.nit,
        "razon_social": empresa.razon_social,
        "activa": empresa.activa,
    }


def _serialize_user_company(user):
    return {
        "usuario": {"id": user.id, "correo": user.correo},
        "empresa": _serialize_empresa(
            db.session.get(Empresa, user.empresa_id) if user.empresa_id else None
        ),
    }


def _get_user(user_id):
    user = db.session.get(Usuario, user_id)
    if user is None:
        raise UsuarioEmpresaNotFoundError("Usuario no encontrado.")
    return user


def _get_active_company(empresa_id):
    if isinstance(empresa_id, bool) or not isinstance(empresa_id, int) or empresa_id < 1:
        raise UsuarioEmpresaValidationError("empresa_id debe ser un entero positivo.")
    empresa = db.session.get(Empresa, empresa_id)
    if empresa is None:
        raise UsuarioEmpresaNotFoundError("Empresa no encontrada.")
    if not empresa.activa:
        raise UsuarioEmpresaConflictError("No se puede asignar una empresa inactiva.")
    return empresa


def get_user_company(user_id):
    return _serialize_user_company(_get_user(user_id))


def create_user_company(user_id, empresa_id):
    user = _get_user(user_id)
    empresa = _get_active_company(empresa_id)
    if not user.activo:
        raise UsuarioEmpresaConflictError("No se puede asociar un usuario inactivo.")
    if user.empresa_id is not None:
        raise UsuarioEmpresaConflictError(
            "El usuario ya tiene una empresa; use PUT para cambiarla."
        )
    user.empresa_id = empresa.id
    db.session.commit()
    return _serialize_user_company(user)


def update_user_company(user_id, empresa_id):
    user = _get_user(user_id)
    empresa = _get_active_company(empresa_id)
    if not user.activo:
        raise UsuarioEmpresaConflictError("No se puede asociar un usuario inactivo.")
    user.empresa_id = empresa.id
    db.session.commit()
    return _serialize_user_company(user)


def delete_user_company(user_id):
    user = _get_user(user_id)
    if user.empresa_id is None:
        raise UsuarioEmpresaNotFoundError("El usuario no tiene una empresa asociada.")
    user.empresa_id = None
    db.session.commit()
    return _serialize_user_company(user)
