from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Asistencia, Contrato, Empleado, Empresa


ESTADOS = {"REGISTRADA", "VALIDADA", "ANULADA"}
REQUIRED_FIELDS = {"contrato_id", "entrada"}
OPTIONAL_FIELDS = {"salida", "minutos_descanso", "estado", "observacion"}
WRITABLE_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS


class AsistenciaValidationError(ValueError):
    pass


class AsistenciaNotFoundError(LookupError):
    pass


class AsistenciaForbiddenError(PermissionError):
    pass


class AsistenciaConflictError(ValueError):
    pass


def _empresa_id_for_user(current_user):
    empresa_id = current_user.empresa_id
    if empresa_id is None:
        raise AsistenciaForbiddenError("El usuario no está asociado a una empresa.")

    empresa = db.session.get(Empresa, empresa_id)
    if empresa is None or not empresa.activa:
        raise AsistenciaForbiddenError("La empresa del usuario no está disponible.")
    return empresa_id


def _parse_datetime(value, field, required=False):
    if value is None:
        if required:
            raise AsistenciaValidationError(f"{field} es obligatoria.")
        return None
    if not isinstance(value, str):
        raise AsistenciaValidationError(
            f"{field} debe usar el formato ISO 8601, por ejemplo 2026-03-02T08:00:00-05:00."
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise AsistenciaValidationError(
            f"{field} debe usar el formato ISO 8601, por ejemplo 2026-03-02T08:00:00-05:00."
        ) from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _validate_payload(data, partial=False):
    if not isinstance(data, dict):
        raise AsistenciaValidationError("El cuerpo debe ser un objeto JSON.")
    if not data:
        raise AsistenciaValidationError("Debe enviar al menos un campo.")

    unknown_fields = set(data) - WRITABLE_FIELDS
    if unknown_fields:
        fields = ", ".join(sorted(unknown_fields))
        raise AsistenciaValidationError(f"Campos no permitidos: {fields}.")

    if not partial:
        missing_fields = REQUIRED_FIELDS - set(data)
        if missing_fields:
            fields = ", ".join(sorted(missing_fields))
            raise AsistenciaValidationError(f"Faltan campos obligatorios: {fields}.")

    values = {}
    for field, value in data.items():
        if field == "contrato_id":
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise AsistenciaValidationError("contrato_id debe ser un entero positivo.")
            values[field] = value
        elif field in {"entrada", "salida"}:
            values[field] = _parse_datetime(value, field, required=field == "entrada")
        elif field == "minutos_descanso":
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise AsistenciaValidationError(
                    "minutos_descanso debe ser un entero mayor o igual que cero."
                )
            values[field] = value
        elif field == "estado":
            if not isinstance(value, str) or value not in ESTADOS:
                options = ", ".join(sorted(ESTADOS))
                raise AsistenciaValidationError(f"estado debe ser uno de: {options}.")
            values[field] = value
        elif field == "observacion":
            if value is not None and not isinstance(value, str):
                raise AsistenciaValidationError("observacion debe ser texto o null.")
            if isinstance(value, str):
                value = value.strip() or None
            values[field] = value

    if not partial:
        values.setdefault("salida", None)
        values.setdefault("minutos_descanso", 0)
        values.setdefault("estado", "REGISTRADA")
        values.setdefault("observacion", None)
    return values


def _serialize_asistencia(asistencia):
    return {
        "id": asistencia.id,
        "contrato_id": asistencia.contrato_id,
        "entrada": asistencia.entrada.isoformat(),
        "salida": asistencia.salida.isoformat() if asistencia.salida else None,
        "minutos_descanso": asistencia.minutos_descanso,
        "estado": asistencia.estado,
        "observacion": asistencia.observacion,
    }


def _contrato_for_company(empresa_id, contrato_id, allow_terminated=False):
    contrato = (
        Contrato.query.join(Empleado, Empleado.id == Contrato.empleado_id)
        .filter(Contrato.id == contrato_id, Empleado.empresa_id == empresa_id)
        .first()
    )
    if contrato is None:
        raise AsistenciaNotFoundError("Contrato no encontrado.")
    if not allow_terminated and contrato.estado != "ACTIVO":
        raise AsistenciaConflictError(
            "No se puede registrar asistencia en un contrato terminado."
        )
    return contrato


def _validate_times(entrada, salida):
    if entrada is None:
        raise AsistenciaValidationError("entrada es obligatoria.")
    if salida is not None and salida <= entrada:
        raise AsistenciaValidationError("salida debe ser posterior a entrada.")


def _apply_references(empresa_id, values, current=None):
    if "contrato_id" in values:
        same_contract = current is not None and current.contrato_id == values["contrato_id"]
        _contrato_for_company(
            empresa_id,
            values["contrato_id"],
            allow_terminated=same_contract,
        )
    entrada = values.get("entrada", current.entrada if current is not None else None)
    salida = values.get("salida", current.salida if current is not None else None)
    _validate_times(entrada, salida)


def _scoped_query(empresa_id):
    return (
        Asistencia.query.join(Contrato, Contrato.id == Asistencia.contrato_id)
        .join(Empleado, Empleado.id == Contrato.empleado_id)
        .filter(Empleado.empresa_id == empresa_id)
    )


def _find_asistencia(empresa_id, asistencia_id):
    asistencia = _scoped_query(empresa_id).filter(Asistencia.id == asistencia_id).first()
    if asistencia is None:
        raise AsistenciaNotFoundError("Asistencia no encontrada.")
    return asistencia


def _commit_asistencia(asistencia):
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise AsistenciaValidationError(
            "La asistencia no cumple las reglas de horario, descanso o estado."
        ) from error


def _parse_query_contrato_id(contrato_id):
    if contrato_id is None:
        return None
    if not isinstance(contrato_id, str) or not contrato_id.isdigit():
        raise AsistenciaValidationError("contrato_id debe ser un entero positivo.")
    parsed = int(contrato_id)
    if parsed < 1:
        raise AsistenciaValidationError("contrato_id debe ser un entero positivo.")
    return parsed


def list_attendance(current_user, page=1, per_page=20, contrato_id=None, estado=None):
    empresa_id = _empresa_id_for_user(current_user)
    if page < 1:
        raise AsistenciaValidationError("page debe ser mayor que cero.")
    if per_page < 1 or per_page > 100:
        raise AsistenciaValidationError("per_page debe estar entre 1 y 100.")
    if estado is not None and estado not in ESTADOS:
        raise AsistenciaValidationError("estado debe ser REGISTRADA, VALIDADA o ANULADA.")

    parsed_contrato_id = _parse_query_contrato_id(contrato_id)
    if parsed_contrato_id is not None:
        _contrato_for_company(empresa_id, parsed_contrato_id, allow_terminated=True)

    query = _scoped_query(empresa_id)
    if parsed_contrato_id is not None:
        query = query.filter(Asistencia.contrato_id == parsed_contrato_id)
    if estado is not None:
        query = query.filter(Asistencia.estado == estado)
    pagination = query.order_by(Asistencia.id).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return {
        "items": [_serialize_asistencia(asistencia) for asistencia in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        },
    }


def get_attendance(current_user, asistencia_id):
    empresa_id = _empresa_id_for_user(current_user)
    return _serialize_asistencia(_find_asistencia(empresa_id, asistencia_id))


def create_attendance(current_user, data):
    empresa_id = _empresa_id_for_user(current_user)
    values = _validate_payload(data)
    _apply_references(empresa_id, values)
    asistencia = Asistencia(**values)
    db.session.add(asistencia)
    _commit_asistencia(asistencia)
    return _serialize_asistencia(asistencia)


def update_attendance(current_user, asistencia_id, data, replace=False):
    empresa_id = _empresa_id_for_user(current_user)
    asistencia = _find_asistencia(empresa_id, asistencia_id)
    values = _validate_payload(data, partial=not replace)
    if replace:
        values.setdefault("salida", None)
        values.setdefault("minutos_descanso", 0)
        values.setdefault("estado", "REGISTRADA")
        values.setdefault("observacion", None)
    _apply_references(empresa_id, values, current=asistencia)
    for field, value in values.items():
        setattr(asistencia, field, value)
    _commit_asistencia(asistencia)
    return _serialize_asistencia(asistencia)


def delete_attendance(current_user, asistencia_id):
    empresa_id = _empresa_id_for_user(current_user)
    asistencia = _find_asistencia(empresa_id, asistencia_id)
    asistencia.estado = "ANULADA"
    _commit_asistencia(asistencia)
    return _serialize_asistencia(asistencia)
