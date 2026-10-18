from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Empresa


REQUIRED_FIELDS = {"nit", "razon_social"}
STRING_LIMITS = {
    "nit": 30,
    "razon_social": 200,
    "telefono": 30,
    "correo": 150,
}
TEXT_FIELDS = {"direccion"}
WRITABLE_FIELDS = REQUIRED_FIELDS | set(STRING_LIMITS) | TEXT_FIELDS | {"activa"}


class EmpresaValidationError(ValueError):
    pass


class EmpresaNotFoundError(LookupError):
    pass


class EmpresaConflictError(ValueError):
    pass


def _validate_payload(data, partial=False):
    if not isinstance(data, dict):
        raise EmpresaValidationError("El cuerpo debe ser un objeto JSON.")
    if not data:
        raise EmpresaValidationError("Debe enviar al menos un campo.")

    unknown_fields = set(data) - WRITABLE_FIELDS
    if unknown_fields:
        fields = ", ".join(sorted(unknown_fields))
        raise EmpresaValidationError(f"Campos no permitidos: {fields}.")

    if not partial:
        missing_fields = REQUIRED_FIELDS - set(data)
        if missing_fields:
            fields = ", ".join(sorted(missing_fields))
            raise EmpresaValidationError(f"Faltan campos obligatorios: {fields}.")

    values = {}
    for field, value in data.items():
        if field in STRING_LIMITS:
            if value is None and field not in REQUIRED_FIELDS:
                values[field] = None
                continue
            if not isinstance(value, str):
                raise EmpresaValidationError(f"{field} debe ser texto.")
            value = value.strip()
            if field in REQUIRED_FIELDS and not value:
                raise EmpresaValidationError(f"{field} no puede estar vacío.")
            if len(value) > STRING_LIMITS[field]:
                raise EmpresaValidationError(
                    f"{field} no puede superar {STRING_LIMITS[field]} caracteres."
                )
            if field == "correo" and value and (
                value.count("@") != 1
                or "." not in value.rsplit("@", 1)[-1]
                or any(character.isspace() for character in value)
            ):
                raise EmpresaValidationError("El correo no tiene un formato válido.")
            if field == "nit":
                value = value.upper()
            values[field] = value or None if field not in REQUIRED_FIELDS else value
        elif field in TEXT_FIELDS:
            if value is not None and not isinstance(value, str):
                raise EmpresaValidationError(f"{field} debe ser texto o null.")
            values[field] = value.strip() if isinstance(value, str) else None
            if values[field] == "":
                values[field] = None
        elif field == "activa":
            if not isinstance(value, bool):
                raise EmpresaValidationError("activa debe ser true o false.")
            values[field] = value

    if not partial:
        values.setdefault("activa", True)
    return values


def _serialize_empresa(empresa):
    return {
        "id": empresa.id,
        "nit": empresa.nit,
        "razon_social": empresa.razon_social,
        "direccion": empresa.direccion,
        "telefono": empresa.telefono,
        "correo": empresa.correo,
        "activa": empresa.activa,
    }


def _find_empresa(empresa_id):
    empresa = db.session.get(Empresa, empresa_id)
    if empresa is None:
        raise EmpresaNotFoundError("Empresa no encontrada.")
    return empresa


def _commit_empresa(empresa):
    nit = empresa.nit
    try:
        db.session.flush()
    except IntegrityError as error:
        db.session.rollback()
        raise EmpresaConflictError("Ya existe una empresa con ese NIT.") from error

    duplicate = Empresa.query.filter(
        db.func.upper(Empresa.nit) == nit.upper(),
        Empresa.id != empresa.id,
    ).first()
    if duplicate is not None:
        db.session.rollback()
        raise EmpresaConflictError("Ya existe una empresa con ese NIT.")
    db.session.commit()


def _parse_activa(activa):
    if activa is None:
        return None
    if not isinstance(activa, str):
        raise EmpresaValidationError("activa debe ser true o false.")
    normalized = activa.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise EmpresaValidationError("activa debe ser true o false.")


def list_companies(page=1, per_page=20, activa=None):
    if page < 1:
        raise EmpresaValidationError("page debe ser mayor que cero.")
    if per_page < 1 or per_page > 100:
        raise EmpresaValidationError("per_page debe estar entre 1 y 100.")

    query = Empresa.query
    parsed_activa = _parse_activa(activa)
    if parsed_activa is not None:
        query = query.filter_by(activa=parsed_activa)
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
    return _serialize_empresa(_find_empresa(empresa_id))


def create_company(data):
    values = _validate_payload(data)
    empresa = Empresa(**values)
    db.session.add(empresa)
    _commit_empresa(empresa)
    return _serialize_empresa(empresa)


def update_company(empresa_id, data, replace=False):
    empresa = _find_empresa(empresa_id)
    values = _validate_payload(data, partial=not replace)
    if replace:
        for field in WRITABLE_FIELDS - REQUIRED_FIELDS - {"activa"}:
            if field not in values:
                values[field] = None
        values.setdefault("activa", True)
    for field, value in values.items():
        setattr(empresa, field, value)
    _commit_empresa(empresa)
    return _serialize_empresa(empresa)


def delete_company(empresa_id):
    empresa = _find_empresa(empresa_id)
    empresa.activa = False
    _commit_empresa(empresa)
    return _serialize_empresa(empresa)
