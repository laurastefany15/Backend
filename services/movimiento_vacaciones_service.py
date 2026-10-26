from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Contrato, Empleado, Empresa, MovimientoVacaciones, Vacacion


TIPOS = {"CAUSACION", "DISFRUTE", "COMPENSACION", "AJUSTE"}
TIPOS_NEGATIVOS = {"DISFRUTE", "COMPENSACION"}
REQUIRED_FIELDS = {"contrato_id", "fecha", "tipo", "dias"}
OPTIONAL_FIELDS = {"vacaciones_id", "observacion"}
WRITABLE_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS
DAYS = Decimal("0.001")
MAX_DAYS = Decimal("9999999.999")


class MovimientoVacacionesValidationError(ValueError):
    pass


class MovimientoVacacionesNotFoundError(LookupError):
    pass


class MovimientoVacacionesForbiddenError(PermissionError):
    pass


class MovimientoVacacionesConflictError(ValueError):
    pass


def _empresa_id_for_user(current_user):
    empresa_id = current_user.empresa_id
    if empresa_id is None:
        raise MovimientoVacacionesForbiddenError(
            "El usuario no está asociado a una empresa."
        )

    empresa = db.session.get(Empresa, empresa_id)
    if empresa is None or not empresa.activa:
        raise MovimientoVacacionesForbiddenError(
            "La empresa del usuario no está disponible."
        )
    return empresa_id


def _parse_date(value, field):
    if value is None:
        raise MovimientoVacacionesValidationError(f"{field} es obligatoria.")
    if not isinstance(value, str):
        raise MovimientoVacacionesValidationError(f"{field} debe usar el formato YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise MovimientoVacacionesValidationError(
            f"{field} debe usar el formato YYYY-MM-DD."
        ) from error


def _parse_days(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise MovimientoVacacionesValidationError("dias debe ser un número.")
    if isinstance(value, str):
        value = value.strip()
        if not value:
            raise MovimientoVacacionesValidationError("dias debe ser un número.")
    try:
        amount = Decimal(str(value)).quantize(DAYS, rounding=ROUND_HALF_UP)
    except InvalidOperation as error:
        raise MovimientoVacacionesValidationError("dias debe ser un número.") from error
    if not amount.is_finite() or amount < -MAX_DAYS or amount > MAX_DAYS:
        raise MovimientoVacacionesValidationError(
            f"dias debe estar entre {-MAX_DAYS} y {MAX_DAYS}."
        )
    if amount == 0:
        raise MovimientoVacacionesValidationError("dias no puede ser cero.")
    return amount


def _validate_sign(tipo, dias):
    if tipo == "CAUSACION" and dias <= 0:
        raise MovimientoVacacionesValidationError(
            "En una causación los días deben ser positivos."
        )
    if tipo in TIPOS_NEGATIVOS and dias >= 0:
        if tipo == "DISFRUTE":
            raise MovimientoVacacionesValidationError(
                "En un disfrute los días deben ser negativos."
            )
        raise MovimientoVacacionesValidationError(
            "En una compensación los días deben ser negativos."
        )


def _optional_text(value, field):
    if value is None:
        return None
    if not isinstance(value, str):
        raise MovimientoVacacionesValidationError(f"{field} debe ser texto o null.")
    return value.strip() or None


def _validate_payload(data, partial=False):
    if not isinstance(data, dict):
        raise MovimientoVacacionesValidationError("El cuerpo debe ser un objeto JSON.")
    if not data:
        raise MovimientoVacacionesValidationError("Debe enviar al menos un campo.")

    unknown_fields = set(data) - WRITABLE_FIELDS
    if unknown_fields:
        fields = ", ".join(sorted(unknown_fields))
        raise MovimientoVacacionesValidationError(f"Campos no permitidos: {fields}.")

    if not partial:
        missing_fields = REQUIRED_FIELDS - set(data)
        if missing_fields:
            fields = ", ".join(sorted(missing_fields))
            raise MovimientoVacacionesValidationError(
                f"Faltan campos obligatorios: {fields}."
            )

    values = {}
    for field, value in data.items():
        if field == "contrato_id":
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise MovimientoVacacionesValidationError(
                    "contrato_id debe ser un entero positivo."
                )
            values[field] = value
        elif field == "vacaciones_id":
            if value is None:
                values[field] = None
            elif isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise MovimientoVacacionesValidationError(
                    "vacaciones_id debe ser un entero positivo o null."
                )
            else:
                values[field] = value
        elif field == "fecha":
            values[field] = _parse_date(value, field)
        elif field == "tipo":
            if not isinstance(value, str) or value not in TIPOS:
                options = ", ".join(sorted(TIPOS))
                raise MovimientoVacacionesValidationError(f"tipo debe ser uno de: {options}.")
            values[field] = value
        elif field == "dias":
            values[field] = _parse_days(value)
        elif field == "observacion":
            values[field] = _optional_text(value, field)

    if not partial:
        values.setdefault("vacaciones_id", None)
        values.setdefault("observacion", None)
    return values


def _json_days(value):
    return float(Decimal(str(value)).quantize(DAYS))


def _serialize_movimiento(movimiento):
    return {
        "id": movimiento.id,
        "contrato_id": movimiento.contrato_id,
        "vacaciones_id": movimiento.vacaciones_id,
        "fecha": movimiento.fecha.isoformat(),
        "tipo": movimiento.tipo,
        "dias": _json_days(movimiento.dias),
        "observacion": movimiento.observacion,
    }


def _merged(values, current, field):
    if field in values:
        return values[field]
    if current is not None:
        return getattr(current, field)
    return None


def _contrato_for_company(empresa_id, contrato_id, allow_terminated=False):
    contrato = (
        Contrato.query.join(Empleado, Empleado.id == Contrato.empleado_id)
        .filter(Contrato.id == contrato_id, Empleado.empresa_id == empresa_id)
        .first()
    )
    if contrato is None:
        raise MovimientoVacacionesNotFoundError("Contrato no encontrado.")
    if not allow_terminated and contrato.estado != "ACTIVO":
        raise MovimientoVacacionesConflictError(
            "No se puede registrar el movimiento en un contrato terminado."
        )
    return contrato


def _vacacion_for_company(empresa_id, vacacion_id):
    vacacion = (
        Vacacion.query.join(Contrato, Contrato.id == Vacacion.contrato_id)
        .join(Empleado, Empleado.id == Contrato.empleado_id)
        .filter(Vacacion.id == vacacion_id, Empleado.empresa_id == empresa_id)
        .first()
    )
    if vacacion is None:
        raise MovimientoVacacionesNotFoundError("Vacación no encontrada.")
    return vacacion


def _locked_disfrute(movimiento):
    if movimiento is None or movimiento.tipo != "DISFRUTE" or movimiento.vacaciones_id is None:
        return False
    vacacion = db.session.get(Vacacion, movimiento.vacaciones_id)
    return vacacion is not None and vacacion.estado == "DISFRUTADA"


def _contract_balance(contrato_id, exclude_id=None):
    query = db.session.query(func.coalesce(func.sum(MovimientoVacaciones.dias), 0)).filter(
        MovimientoVacaciones.contrato_id == contrato_id
    )
    if exclude_id is not None:
        query = query.filter(MovimientoVacaciones.id != exclude_id)
    return Decimal(str(query.scalar() or 0)).quantize(DAYS)


def _ensure_non_negative_balance(contrato_id, dias, current=None):
    exclude_id = current.id if current is not None else None
    if _contract_balance(contrato_id, exclude_id) + dias < 0:
        raise MovimientoVacacionesConflictError(
            "El movimiento dejaría el saldo de vacaciones en negativo."
        )
    if current is not None and current.contrato_id != contrato_id:
        if _contract_balance(current.contrato_id, exclude_id) < 0:
            raise MovimientoVacacionesConflictError(
                "El movimiento dejaría el saldo de vacaciones en negativo."
            )


def _ensure_unique_disfrute(vacaciones_id, tipo, current_id=None):
    if tipo != "DISFRUTE" or vacaciones_id is None:
        return
    existing = MovimientoVacaciones.query.filter_by(
        vacaciones_id=vacaciones_id,
        tipo="DISFRUTE",
    ).first()
    if existing is not None and existing.id != current_id:
        raise MovimientoVacacionesConflictError(
            "Ya existe un disfrute asociado a esa vacación."
        )


def _apply_rules(empresa_id, values, current=None):
    if current is not None and _locked_disfrute(current):
        raise MovimientoVacacionesConflictError(
            "Ese disfrute está ligado a una vacación en estado DISFRUTADA. "
            "Cambie la vacación para modificarlo."
        )

    if "contrato_id" in values:
        same_contract = current is not None and current.contrato_id == values["contrato_id"]
        _contrato_for_company(
            empresa_id,
            values["contrato_id"],
            allow_terminated=same_contract,
        )

    contrato_id = _merged(values, current, "contrato_id")
    vacaciones_id = _merged(values, current, "vacaciones_id")
    tipo = _merged(values, current, "tipo")
    dias = _merged(values, current, "dias")
    if tipo is None:
        raise MovimientoVacacionesValidationError("tipo es obligatorio.")
    if dias is None:
        raise MovimientoVacacionesValidationError("dias es obligatorio.")
    _validate_sign(tipo, dias)

    if vacaciones_id is not None:
        vacacion = _vacacion_for_company(empresa_id, vacaciones_id)
        if vacacion.contrato_id != contrato_id:
            raise MovimientoVacacionesValidationError(
                "La vacación no pertenece al contrato indicado."
            )
    _ensure_unique_disfrute(
        vacaciones_id,
        tipo,
        current_id=current.id if current is not None else None,
    )
    _ensure_non_negative_balance(contrato_id, dias, current=current)


def _scoped_query(empresa_id):
    return (
        MovimientoVacaciones.query.join(Contrato, Contrato.id == MovimientoVacaciones.contrato_id)
        .join(Empleado, Empleado.id == Contrato.empleado_id)
        .filter(Empleado.empresa_id == empresa_id)
    )


def _find_movimiento(empresa_id, movimiento_id):
    movimiento = (
        _scoped_query(empresa_id)
        .filter(MovimientoVacaciones.id == movimiento_id)
        .first()
    )
    if movimiento is None:
        raise MovimientoVacacionesNotFoundError("Movimiento de vacaciones no encontrado.")
    return movimiento


def _commit_movimiento():
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        message = str(getattr(error, "orig", error)).lower()
        if "unique" in message or "uq_descuento_vacacion" in message:
            raise MovimientoVacacionesConflictError(
                "Ya existe un disfrute asociado a esa vacación."
            ) from error
        raise MovimientoVacacionesValidationError(
            "El movimiento no cumple las reglas de tipo, días o contrato."
        ) from error


def _parse_query_int(value, field):
    if value is None:
        return None
    if not isinstance(value, str) or not value.isdigit():
        raise MovimientoVacacionesValidationError(f"{field} debe ser un entero positivo.")
    parsed = int(value)
    if parsed < 1:
        raise MovimientoVacacionesValidationError(f"{field} debe ser un entero positivo.")
    return parsed


def list_movements(
    current_user,
    page=1,
    per_page=20,
    contrato_id=None,
    vacaciones_id=None,
    tipo=None,
):
    empresa_id = _empresa_id_for_user(current_user)
    if page < 1:
        raise MovimientoVacacionesValidationError("page debe ser mayor que cero.")
    if per_page < 1 or per_page > 100:
        raise MovimientoVacacionesValidationError("per_page debe estar entre 1 y 100.")
    if tipo is not None and tipo not in TIPOS:
        options = ", ".join(sorted(TIPOS))
        raise MovimientoVacacionesValidationError(f"tipo debe ser uno de: {options}.")

    parsed_contrato_id = _parse_query_int(contrato_id, "contrato_id")
    parsed_vacaciones_id = _parse_query_int(vacaciones_id, "vacaciones_id")
    if parsed_contrato_id is not None:
        _contrato_for_company(empresa_id, parsed_contrato_id, allow_terminated=True)
    if parsed_vacaciones_id is not None:
        _vacacion_for_company(empresa_id, parsed_vacaciones_id)

    query = _scoped_query(empresa_id)
    if parsed_contrato_id is not None:
        query = query.filter(MovimientoVacaciones.contrato_id == parsed_contrato_id)
    if parsed_vacaciones_id is not None:
        query = query.filter(MovimientoVacaciones.vacaciones_id == parsed_vacaciones_id)
    if tipo is not None:
        query = query.filter(MovimientoVacaciones.tipo == tipo)
    pagination = query.order_by(MovimientoVacaciones.fecha, MovimientoVacaciones.id).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return {
        "items": [_serialize_movimiento(movimiento) for movimiento in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        },
    }


def get_movement(current_user, movimiento_id):
    empresa_id = _empresa_id_for_user(current_user)
    return _serialize_movimiento(_find_movimiento(empresa_id, movimiento_id))


def create_movement(current_user, data):
    empresa_id = _empresa_id_for_user(current_user)
    values = _validate_payload(data)
    _apply_rules(empresa_id, values)
    movimiento = MovimientoVacaciones(**values)
    db.session.add(movimiento)
    _commit_movimiento()
    return _serialize_movimiento(movimiento)


def update_movement(current_user, movimiento_id, data, replace=False):
    empresa_id = _empresa_id_for_user(current_user)
    movimiento = _find_movimiento(empresa_id, movimiento_id)
    values = _validate_payload(data, partial=not replace)
    if replace:
        values.setdefault("vacaciones_id", None)
        values.setdefault("observacion", None)
    _apply_rules(empresa_id, values, current=movimiento)
    for field, value in values.items():
        setattr(movimiento, field, value)
    _commit_movimiento()
    return _serialize_movimiento(movimiento)


def delete_movement(current_user, movimiento_id):
    empresa_id = _empresa_id_for_user(current_user)
    movimiento = _find_movimiento(empresa_id, movimiento_id)
    if _locked_disfrute(movimiento):
        raise MovimientoVacacionesConflictError(
            "Ese disfrute está ligado a una vacación en estado DISFRUTADA. "
            "Cambie la vacación para modificarlo."
        )
    if _contract_balance(movimiento.contrato_id, movimiento.id) < 0:
        raise MovimientoVacacionesConflictError(
            "El movimiento dejaría el saldo de vacaciones en negativo."
        )
    payload = _serialize_movimiento(movimiento)
    db.session.delete(movimiento)
    _commit_movimiento()
    return payload
