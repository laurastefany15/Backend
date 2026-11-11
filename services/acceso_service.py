from flask import request

from extensions import db
from models import Empresa, Rol, Usuario, UsuarioEmpresa, UsuarioRol


EMPRESA_HEADER = "X-Empresa-Id"


class AccesoDenegadoError(PermissionError):
    pass


class EmpresaNoIndicadaError(ValueError):
    pass


def codigos_rol(user):
    rows = (
        db.session.query(Rol.codigo)
        .join(UsuarioRol, UsuarioRol.rol_id == Rol.id)
        .filter(UsuarioRol.usuario_id == user.id)
        .all()
    )
    return {codigo for (codigo,) in rows}


def tiene_rol(user, *codigos):
    return bool(codigos_rol(user).intersection(codigos))


def empresas_de(user, solo_activas=False):
    query = (
        Empresa.query.join(UsuarioEmpresa, UsuarioEmpresa.empresa_id == Empresa.id)
        .filter(UsuarioEmpresa.usuario_id == user.id)
        .order_by(Empresa.id)
    )
    if solo_activas:
        query = query.filter(Empresa.activa.is_(True))
    return query.all()


def serialize_empresa_breve(empresa):
    return {
        "id": empresa.id,
        "nit": empresa.nit,
        "razon_social": empresa.razon_social,
        "activa": empresa.activa,
    }


def perfil_publico(user, solo_activas=False):
    return {
        "id": user.id,
        "correo": user.correo,
        "activo": user.activo,
        "roles": sorted(codigos_rol(user)),
        "empresas": [
            serialize_empresa_breve(empresa)
            for empresa in empresas_de(user, solo_activas=solo_activas)
        ],
    }


def perfil_detallado(user):
    perfil = perfil_publico(user)
    creador = (
        db.session.get(Usuario, user.creado_por_id) if user.creado_por_id else None
    )
    perfil["creado_por"] = (
        None
        if creador is None
        else {"id": creador.id, "correo": creador.correo}
    )
    return perfil


def _requested_empresa_id():
    raw = request.headers.get(EMPRESA_HEADER)
    if raw is None or raw == "":
        return None
    if not raw.isdigit():
        raise EmpresaNoIndicadaError("X-Empresa-Id debe ser un entero positivo.")
    return int(raw)


def resolve_empresa_id(user):
    requested = _requested_empresa_id()
    allowed = empresas_de(user, solo_activas=True)
    allowed_ids = {empresa.id for empresa in allowed}
    if requested is not None:
        if requested in allowed_ids:
            return requested
        link = UsuarioEmpresa.query.filter_by(
            usuario_id=user.id,
            empresa_id=requested,
        ).first()
        if link is None:
            raise AccesoDenegadoError("No tiene acceso a esa empresa.")
        raise AccesoDenegadoError("La empresa no está disponible.")
    if len(allowed) == 1:
        return allowed[0].id
    if not allowed:
        raise AccesoDenegadoError(
            "El usuario no está asociado a una empresa activa."
        )
    raise EmpresaNoIndicadaError(
        "El usuario tiene varias empresas. Indique el encabezado X-Empresa-Id."
    )


def empresa_id_or_raise(user, forbidden_type, validation_type):
    try:
        return resolve_empresa_id(user)
    except AccesoDenegadoError as error:
        raise forbidden_type(str(error)) from error
    except EmpresaNoIndicadaError as error:
        raise validation_type(str(error)) from error
