from datetime import date

from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Empleado, Empresa


REQUIRED_FIELDS = {
    "tipo_documento",
    "numero_documento",
    "nombres",
    "apellidos",
}
STRING_LIMITS = {
    "tipo_documento": 10,
    "numero_documento": 30,
    "nombres": 100,
    "apellidos": 100,
    "telefono": 30,
    "correo": 150,
    "contacto_emergencia": 150,
    "telefono_emergencia": 30,
    "banco": 120,
    "tipo_cuenta": 25,
    "numero_cuenta": 60,
    "eps": 120,
    "fondo_pension": 120,
    "fondo_cesantias": 120,
    "arl": 120,
    "caja_compensacion": 120,
}
TEXT_FIELDS = {"direccion"}
WRITABLE_FIELDS = REQUIRED_FIELDS | set(STRING_LIMITS) | TEXT_FIELDS | {
    "fecha_nacimiento",
    "estado",
}


class EmpleadoValidationError(ValueError):
    pass


class EmpleadoNotFoundError(LookupError):
    pass


class EmpleadoForbiddenError(PermissionError):
    pass


class EmpleadoConflictError(ValueError):
    pass


def _empresa_id_for_user(current_user):
    empresa_id = current_user.empresa_id
    if empresa_id is None:
        raise EmpleadoForbiddenError(
            "El usuario no está asociado a una empresa."
        )

    empresa = db.session.get(Empresa, empresa_id)
    if empresa is None or not empresa.activa:
        raise EmpleadoForbiddenError(
            "La empresa del usuario no está disponible."
        )
    return empresa_id


def _validate_payload(data, partial=False):
    if not isinstance(data, dict):
        raise EmpleadoValidationError("El cuerpo debe ser un objeto JSON.")
    if not data:
        raise EmpleadoValidationError("Debe enviar al menos un campo.")

    unknown_fields = set(data) - WRITABLE_FIELDS
    if unknown_fields:
        fields = ", ".join(sorted(unknown_fields))
        raise EmpleadoValidationError(f"Campos no permitidos: {fields}.")

    if not partial:
        missing_fields = REQUIRED_FIELDS - set(data)
        if missing_fields:
            fields = ", ".join(sorted(missing_fields))
            raise EmpleadoValidationError(f"Faltan campos obligatorios: {fields}.")

    values = {}
    for field, value in data.items():
        if field in STRING_LIMITS:
            if value is None and field not in REQUIRED_FIELDS:
                values[field] = None
                continue
            if not isinstance(value, str):
                raise EmpleadoValidationError(f"{field} debe ser texto.")
            value = value.strip()
            if field in REQUIRED_FIELDS and not value:
                raise EmpleadoValidationError(f"{field} no puede estar vacío.")
            if len(value) > STRING_LIMITS[field]:
                raise EmpleadoValidationError(
                    f"{field} no puede superar {STRING_LIMITS[field]} caracteres."
                )
            if field == "correo" and value and (
                value.count("@") != 1
                or "." not in value.rsplit("@", 1)[-1]
                or any(character.isspace() for character in value)
            ):
                raise EmpleadoValidationError("El correo no tiene un formato válido.")
            values[field] = value or None if field not in REQUIRED_FIELDS else value
        elif field in TEXT_FIELDS:
            if value is not None and not isinstance(value, str):
                raise EmpleadoValidationError(f"{field} debe ser texto o null.")
            values[field] = value
        elif field == "fecha_nacimiento":
            if value is None:
                values[field] = None
                continue
            if not isinstance(value, str):
                raise EmpleadoValidationError(
                    "fecha_nacimiento debe usar el formato YYYY-MM-DD."
                )
            try:
                values[field] = date.fromisoformat(value)
            except ValueError as error:
                raise EmpleadoValidationError(
                    "fecha_nacimiento debe usar el formato YYYY-MM-DD."
                ) from error
        elif field == "estado":
            if not isinstance(value, str) or value not in {"ACTIVO", "INACTIVO"}:
                raise EmpleadoValidationError(
                    "estado debe ser ACTIVO o INACTIVO."
                )
            values[field] = value

    if not partial:
        values.setdefault("estado", "ACTIVO")
    return values


def _serialize_employee(empleado):
    return {
        "id": empleado.id,
        "empresa_id": empleado.empresa_id,
        "tipo_documento": empleado.tipo_documento,
        "numero_documento": empleado.numero_documento,
        "nombres": empleado.nombres,
        "apellidos": empleado.apellidos,
        "fecha_nacimiento": (
            empleado.fecha_nacimiento.isoformat()
            if empleado.fecha_nacimiento
            else None
        ),
        "telefono": empleado.telefono,
        "correo": empleado.correo,
        "direccion": empleado.direccion,
        "contacto_emergencia": empleado.contacto_emergencia,
        "telefono_emergencia": empleado.telefono_emergencia,
        "banco": empleado.banco,
        "tipo_cuenta": empleado.tipo_cuenta,
        "numero_cuenta": empleado.numero_cuenta,
        "eps": empleado.eps,
        "fondo_pension": empleado.fondo_pension,
        "fondo_cesantias": empleado.fondo_cesantias,
        "arl": empleado.arl,
        "caja_compensacion": empleado.caja_compensacion,
        "estado": empleado.estado,
        "creado_en": empleado.creado_en.isoformat() if empleado.creado_en else None,
    }


def _find_employee(current_user, empleado_id):
    empresa_id = _empresa_id_for_user(current_user)
    empleado = Empleado.query.filter_by(
        id=empleado_id,
        empresa_id=empresa_id,
    ).first()
    if empleado is None:
        raise EmpleadoNotFoundError("Empleado no encontrado.")
    return empleado


def _commit_employee(empleado):
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        duplicate = Empleado.query.filter_by(
            empresa_id=empleado.empresa_id,
            tipo_documento=empleado.tipo_documento,
            numero_documento=empleado.numero_documento,
        ).first()
        if duplicate is not None and duplicate.id != empleado.id:
            raise EmpleadoConflictError(
                "Ya existe un empleado con ese documento en la empresa."
            ) from error
        raise


def list_employees(current_user, page=1, per_page=20, estado=None):
    empresa_id = _empresa_id_for_user(current_user)
    if page < 1:
        raise EmpleadoValidationError("page debe ser mayor que cero.")
    if per_page < 1 or per_page > 100:
        raise EmpleadoValidationError("per_page debe estar entre 1 y 100.")
    if estado is not None and estado not in {"ACTIVO", "INACTIVO"}:
        raise EmpleadoValidationError("estado debe ser ACTIVO o INACTIVO.")

    query = Empleado.query.filter_by(empresa_id=empresa_id)
    if estado:
        query = query.filter_by(estado=estado)
    pagination = query.order_by(Empleado.id).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return {
        "items": [_serialize_employee(empleado) for empleado in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        },
    }


def get_employee(current_user, empleado_id):
    return _serialize_employee(_find_employee(current_user, empleado_id))


def create_employee(current_user, data):
    empresa_id = _empresa_id_for_user(current_user)
    values = _validate_payload(data)
    empleado = Empleado(empresa_id=empresa_id, **values)
    db.session.add(empleado)
    _commit_employee(empleado)
    return _serialize_employee(empleado)


def update_employee(current_user, empleado_id, data, replace=False):
    empleado = _find_employee(current_user, empleado_id)
    values = _validate_payload(data, partial=not replace)
    if replace:
        for field in WRITABLE_FIELDS - REQUIRED_FIELDS - {"estado"}:
            if field not in values:
                values[field] = None
        values.setdefault("estado", "ACTIVO")
    for field, value in values.items():
        setattr(empleado, field, value)
    _commit_employee(empleado)
    return _serialize_employee(empleado)


def delete_employee(current_user, empleado_id):
    empleado = _find_employee(current_user, empleado_id)
    empleado.estado = "INACTIVO"
    _commit_employee(empleado)
    return _serialize_employee(empleado)
