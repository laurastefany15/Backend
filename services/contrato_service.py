from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Contrato, Empleado, Empresa


TIPOS_CONTRATO = {"INDEFINIDO", "FIJO", "OBRA_LABOR", "APRENDIZAJE", "OTRO"}
ESTADOS = {"ACTIVO", "TERMINADO"}
REQUIRED_FIELDS = {
    "empleado_id",
    "tipo_contrato",
    "cargo",
    "fecha_inicio",
    "salario_mensual",
    "horas_semanales",
}
OPTIONAL_FIELDS = {
    "fecha_fin",
    "dia_descanso",
    "tiene_auxilio_transporte",
    "estado",
}
WRITABLE_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS
MONEY = Decimal("0.01")


class ContratoValidationError(ValueError):
    pass


class ContratoNotFoundError(LookupError):
    pass


class ContratoForbiddenError(PermissionError):
    pass


class ContratoConflictError(ValueError):
    pass


def _empresa_id_for_user(current_user):
    empresa_id = current_user.empresa_id
    if empresa_id is None:
        raise ContratoForbiddenError("El usuario no está asociado a una empresa.")

    empresa = db.session.get(Empresa, empresa_id)
    if empresa is None or not empresa.activa:
        raise ContratoForbiddenError("La empresa del usuario no está disponible.")
    return empresa_id


def _require_text(value, field, limit):
    if not isinstance(value, str):
        raise ContratoValidationError(f"{field} debe ser texto.")
    value = value.strip()
    if not value:
        raise ContratoValidationError(f"{field} no puede estar vacío.")
    if len(value) > limit:
        raise ContratoValidationError(f"{field} no puede superar {limit} caracteres.")
    return value


def _parse_date(value, field):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ContratoValidationError(f"{field} debe usar el formato YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ContratoValidationError(
            f"{field} debe usar el formato YYYY-MM-DD."
        ) from error


def _parse_decimal(value, field, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ContratoValidationError(f"{field} debe ser un número.")
    if isinstance(value, str):
        value = value.strip()
        if not value:
            raise ContratoValidationError(f"{field} debe ser un número.")
    try:
        amount = Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except InvalidOperation as error:
        raise ContratoValidationError(f"{field} debe ser un número.") from error
    if not amount.is_finite() or amount < minimum or amount > maximum:
        raise ContratoValidationError(
            f"{field} debe estar entre {minimum} y {maximum}."
        )
    return amount


def _validate_payload(data, partial=False):
    if not isinstance(data, dict):
        raise ContratoValidationError("El cuerpo debe ser un objeto JSON.")
    if not data:
        raise ContratoValidationError("Debe enviar al menos un campo.")

    unknown_fields = set(data) - WRITABLE_FIELDS
    if unknown_fields:
        fields = ", ".join(sorted(unknown_fields))
        raise ContratoValidationError(f"Campos no permitidos: {fields}.")

    if not partial:
        missing_fields = REQUIRED_FIELDS - set(data)
        if missing_fields:
            fields = ", ".join(sorted(missing_fields))
            raise ContratoValidationError(f"Faltan campos obligatorios: {fields}.")

    values = {}
    for field, value in data.items():
        if field == "empleado_id":
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ContratoValidationError("empleado_id debe ser un entero positivo.")
            values[field] = value
        elif field == "tipo_contrato":
            if not isinstance(value, str) or value not in TIPOS_CONTRATO:
                options = ", ".join(sorted(TIPOS_CONTRATO))
                raise ContratoValidationError(f"tipo_contrato debe ser uno de: {options}.")
            values[field] = value
        elif field == "cargo":
            values[field] = _require_text(value, field, 140)
        elif field in {"fecha_inicio", "fecha_fin"}:
            if field == "fecha_inicio" and value is None:
                raise ContratoValidationError("fecha_inicio es obligatoria.")
            values[field] = _parse_date(value, field)
        elif field == "salario_mensual":
            values[field] = _parse_decimal(value, field, Decimal("0"), Decimal("9999999999999.99"))
        elif field == "horas_semanales":
            values[field] = _parse_decimal(value, field, MONEY, Decimal("9999.99"))
        elif field == "dia_descanso":
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 7:
                raise ContratoValidationError("dia_descanso debe ser un entero entre 1 y 7.")
            values[field] = value
        elif field == "tiene_auxilio_transporte":
            if not isinstance(value, bool):
                raise ContratoValidationError("tiene_auxilio_transporte debe ser true o false.")
            values[field] = value
        elif field == "estado":
            if not isinstance(value, str) or value not in ESTADOS:
                raise ContratoValidationError("estado debe ser ACTIVO o TERMINADO.")
            values[field] = value

    if not partial:
        values.setdefault("dia_descanso", 7)
        values.setdefault("tiene_auxilio_transporte", True)
        values.setdefault("estado", "ACTIVO")
        values.setdefault("fecha_fin", None)
    return values


def _json_decimal(value):
    return float(Decimal(value).quantize(MONEY))


def _serialize_contrato(contrato):
    return {
        "id": contrato.id,
        "empleado_id": contrato.empleado_id,
        "tipo_contrato": contrato.tipo_contrato,
        "cargo": contrato.cargo,
        "fecha_inicio": contrato.fecha_inicio.isoformat(),
        "fecha_fin": contrato.fecha_fin.isoformat() if contrato.fecha_fin else None,
        "salario_mensual": _json_decimal(contrato.salario_mensual),
        "horas_semanales": _json_decimal(contrato.horas_semanales),
        "dia_descanso": contrato.dia_descanso,
        "tiene_auxilio_transporte": contrato.tiene_auxilio_transporte,
        "estado": contrato.estado,
    }


def _employee_for_company(empresa_id, empleado_id, allow_inactive=False):
    empleado = Empleado.query.filter_by(id=empleado_id, empresa_id=empresa_id).first()
    if empleado is None:
        raise ContratoNotFoundError("Empleado no encontrado.")
    if not allow_inactive and empleado.estado != "ACTIVO":
        raise ContratoConflictError(
            "No se puede asignar un contrato a un empleado inactivo."
        )
    return empleado


def _validate_dates(fecha_inicio, fecha_fin):
    if fecha_inicio is None:
        raise ContratoValidationError("fecha_inicio es obligatoria.")
    if fecha_fin is not None and fecha_fin < fecha_inicio:
        raise ContratoValidationError("fecha_fin no puede ser anterior a fecha_inicio.")


def _apply_references(empresa_id, values, current=None):
    if "empleado_id" in values:
        same_employee = current is not None and current.empleado_id == values["empleado_id"]
        _employee_for_company(
            empresa_id,
            values["empleado_id"],
            allow_inactive=same_employee,
        )
    fecha_inicio = values.get(
        "fecha_inicio", current.fecha_inicio if current is not None else None
    )
    fecha_fin = values.get("fecha_fin", current.fecha_fin if current is not None else None)
    _validate_dates(fecha_inicio, fecha_fin)


def _find_contrato(empresa_id, contrato_id):
    contrato = (
        Contrato.query.join(Empleado, Empleado.id == Contrato.empleado_id)
        .filter(Contrato.id == contrato_id, Empleado.empresa_id == empresa_id)
        .first()
    )
    if contrato is None:
        raise ContratoNotFoundError("Contrato no encontrado.")
    return contrato


def _commit_contrato(contrato):
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ContratoValidationError(
            "El contrato no cumple las reglas de tipo, salario, horas, fechas o estado."
        ) from error


def _parse_query_empleado_id(empleado_id):
    if empleado_id is None:
        return None
    if not isinstance(empleado_id, str) or not empleado_id.isdigit():
        raise ContratoValidationError("empleado_id debe ser un entero positivo.")
    parsed = int(empleado_id)
    if parsed < 1:
        raise ContratoValidationError("empleado_id debe ser un entero positivo.")
    return parsed


def list_contracts(current_user, page=1, per_page=20, empleado_id=None, estado=None):
    empresa_id = _empresa_id_for_user(current_user)
    if page < 1:
        raise ContratoValidationError("page debe ser mayor que cero.")
    if per_page < 1 or per_page > 100:
        raise ContratoValidationError("per_page debe estar entre 1 y 100.")
    if estado is not None and estado not in ESTADOS:
        raise ContratoValidationError("estado debe ser ACTIVO o TERMINADO.")

    parsed_empleado_id = _parse_query_empleado_id(empleado_id)
    if parsed_empleado_id is not None:
        _employee_for_company(empresa_id, parsed_empleado_id, allow_inactive=True)

    query = Contrato.query.join(Empleado, Empleado.id == Contrato.empleado_id).filter(
        Empleado.empresa_id == empresa_id
    )
    if parsed_empleado_id is not None:
        query = query.filter(Contrato.empleado_id == parsed_empleado_id)
    if estado is not None:
        query = query.filter(Contrato.estado == estado)
    pagination = query.order_by(Contrato.id).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return {
        "items": [_serialize_contrato(contrato) for contrato in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        },
    }


def get_contract(current_user, contrato_id):
    empresa_id = _empresa_id_for_user(current_user)
    return _serialize_contrato(_find_contrato(empresa_id, contrato_id))


def create_contract(current_user, data):
    empresa_id = _empresa_id_for_user(current_user)
    values = _validate_payload(data)
    _apply_references(empresa_id, values)
    contrato = Contrato(**values)
    db.session.add(contrato)
    _commit_contrato(contrato)
    return _serialize_contrato(contrato)


def update_contract(current_user, contrato_id, data, replace=False):
    empresa_id = _empresa_id_for_user(current_user)
    contrato = _find_contrato(empresa_id, contrato_id)
    values = _validate_payload(data, partial=not replace)
    if replace:
        for field in ("fecha_fin",):
            values.setdefault(field, None)
        values.setdefault("dia_descanso", 7)
        values.setdefault("tiene_auxilio_transporte", True)
        values.setdefault("estado", "ACTIVO")
    _apply_references(empresa_id, values, current=contrato)
    for field, value in values.items():
        setattr(contrato, field, value)
    _commit_contrato(contrato)
    return _serialize_contrato(contrato)


def delete_contract(current_user, contrato_id):
    empresa_id = _empresa_id_for_user(current_user)
    contrato = _find_contrato(empresa_id, contrato_id)
    contrato.estado = "TERMINADO"
    _commit_contrato(contrato)
    return _serialize_contrato(contrato)
