from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Contrato, Empleado, Empresa, Incapacidad, MovimientoVacaciones, Vacacion


ESTADOS = {"SOLICITADA", "APROBADA", "DISFRUTADA", "CANCELADA"}
ESTADOS_APROBADOS = {"APROBADA", "DISFRUTADA"}
REQUIRED_FIELDS = {"contrato_id", "fecha_inicio", "fecha_fin", "dias_habiles"}
OPTIONAL_FIELDS = {"fecha_reintegro", "estado", "observaciones"}
WRITABLE_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS
DAYS = Decimal("0.001")
MAX_DAYS = Decimal("99999.999")


class VacacionValidationError(ValueError):
    pass


class VacacionNotFoundError(LookupError):
    pass


class VacacionForbiddenError(PermissionError):
    pass


class VacacionConflictError(ValueError):
    pass


def _empresa_id_for_user(current_user):
    empresa_id = current_user.empresa_id
    if empresa_id is None:
        raise VacacionForbiddenError("El usuario no está asociado a una empresa.")

    empresa = db.session.get(Empresa, empresa_id)
    if empresa is None or not empresa.activa:
        raise VacacionForbiddenError("La empresa del usuario no está disponible.")
    return empresa_id


def _parse_date(value, field, required=False):
    if value is None:
        if required:
            raise VacacionValidationError(f"{field} es obligatoria.")
        return None
    if not isinstance(value, str):
        raise VacacionValidationError(f"{field} debe usar el formato YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise VacacionValidationError(f"{field} debe usar el formato YYYY-MM-DD.") from error


def _parse_days(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise VacacionValidationError(f"{field} debe ser un número.")
    if isinstance(value, str):
        value = value.strip()
        if not value:
            raise VacacionValidationError(f"{field} debe ser un número.")
    try:
        amount = Decimal(str(value)).quantize(DAYS, rounding=ROUND_HALF_UP)
    except InvalidOperation as error:
        raise VacacionValidationError(f"{field} debe ser un número.") from error
    if not amount.is_finite() or amount <= 0 or amount > MAX_DAYS:
        raise VacacionValidationError(
            f"{field} debe ser mayor que cero y no superar {MAX_DAYS}."
        )
    return amount


def _optional_text(value, field):
    if value is None:
        return None
    if not isinstance(value, str):
        raise VacacionValidationError(f"{field} debe ser texto o null.")
    return value.strip() or None


def _validate_payload(data, partial=False):
    if not isinstance(data, dict):
        raise VacacionValidationError("El cuerpo debe ser un objeto JSON.")
    if not data:
        raise VacacionValidationError("Debe enviar al menos un campo.")

    unknown_fields = set(data) - WRITABLE_FIELDS
    if unknown_fields:
        fields = ", ".join(sorted(unknown_fields))
        raise VacacionValidationError(f"Campos no permitidos: {fields}.")

    if not partial:
        missing_fields = REQUIRED_FIELDS - set(data)
        if missing_fields:
            fields = ", ".join(sorted(missing_fields))
            raise VacacionValidationError(f"Faltan campos obligatorios: {fields}.")

    values = {}
    for field, value in data.items():
        if field == "contrato_id":
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise VacacionValidationError("contrato_id debe ser un entero positivo.")
            values[field] = value
        elif field in {"fecha_inicio", "fecha_fin"}:
            values[field] = _parse_date(value, field, required=True)
        elif field == "fecha_reintegro":
            values[field] = _parse_date(value, field)
        elif field == "dias_habiles":
            values[field] = _parse_days(value, field)
        elif field == "estado":
            if not isinstance(value, str) or value not in ESTADOS:
                options = ", ".join(sorted(ESTADOS))
                raise VacacionValidationError(f"estado debe ser uno de: {options}.")
            values[field] = value
        elif field == "observaciones":
            values[field] = _optional_text(value, field)

    if not partial:
        values.setdefault("fecha_reintegro", None)
        values.setdefault("estado", "SOLICITADA")
        values.setdefault("observaciones", None)
    return values


def _json_days(value):
    return float(Decimal(str(value if value is not None else 0)).quantize(DAYS))


def _serialize_vacacion(vacacion):
    return {
        "id": vacacion.id,
        "contrato_id": vacacion.contrato_id,
        "fecha_inicio": vacacion.fecha_inicio.isoformat(),
        "fecha_fin": vacacion.fecha_fin.isoformat(),
        "fecha_reintegro": (
            vacacion.fecha_reintegro.isoformat() if vacacion.fecha_reintegro else None
        ),
        "dias_habiles": _json_days(vacacion.dias_habiles),
        "estado": vacacion.estado,
        "aprobada_por": vacacion.aprobada_por,
        "observaciones": vacacion.observaciones,
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
        raise VacacionNotFoundError("Contrato no encontrado.")
    if not allow_terminated and contrato.estado != "ACTIVO":
        raise VacacionConflictError(
            "No se puede registrar la vacación en un contrato terminado."
        )
    return contrato


def _validate_period(fecha_inicio, fecha_fin, fecha_reintegro, dias_habiles):
    if fecha_inicio is None:
        raise VacacionValidationError("fecha_inicio es obligatoria.")
    if fecha_fin is None:
        raise VacacionValidationError("fecha_fin es obligatoria.")
    if fecha_fin < fecha_inicio:
        raise VacacionValidationError("fecha_fin no puede ser anterior a fecha_inicio.")
    if fecha_reintegro is not None and fecha_reintegro <= fecha_fin:
        raise VacacionValidationError("fecha_reintegro debe ser posterior a fecha_fin.")
    if dias_habiles is None:
        raise VacacionValidationError("dias_habiles es obligatorio.")
    span = (fecha_fin - fecha_inicio).days + 1
    if dias_habiles > span:
        raise VacacionValidationError(
            "dias_habiles no puede superar los días calendario del rango."
        )


def _ensure_no_overlap(contrato_id, fecha_inicio, fecha_fin, estado, vacacion_id=None):
    if estado == "CANCELADA":
        return

    vacations = Vacacion.query.filter(
        Vacacion.contrato_id == contrato_id,
        Vacacion.estado != "CANCELADA",
        Vacacion.fecha_inicio <= fecha_fin,
        Vacacion.fecha_fin >= fecha_inicio,
    )
    if vacacion_id is not None:
        vacations = vacations.filter(Vacacion.id != vacacion_id)
    if vacations.first() is not None:
        raise VacacionConflictError(
            "Las fechas se cruzan con otra vacación del mismo contrato."
        )

    incapacidad = Incapacidad.query.filter(
        Incapacidad.contrato_id == contrato_id,
        Incapacidad.estado != "RECHAZADA",
        Incapacidad.fecha_inicio <= fecha_fin,
        Incapacidad.fecha_fin >= fecha_inicio,
    ).first()
    if incapacidad is not None:
        raise VacacionConflictError(
            "Las fechas se cruzan con una incapacidad del mismo contrato."
        )


def _saldo_contrato(contrato_id, exclude_movimiento_id=None):
    query = db.session.query(func.coalesce(func.sum(MovimientoVacaciones.dias), 0)).filter(
        MovimientoVacaciones.contrato_id == contrato_id
    )
    if exclude_movimiento_id is not None:
        query = query.filter(MovimientoVacaciones.id != exclude_movimiento_id)
    total = query.scalar()
    return Decimal(str(total or 0)).quantize(DAYS)


def _existing_disfrute(vacacion_id):
    if vacacion_id is None:
        return None
    return MovimientoVacaciones.query.filter_by(
        vacaciones_id=vacacion_id,
        tipo="DISFRUTE",
    ).first()


def _ensure_balance(contrato_id, estado, dias_habiles, vacacion_id=None):
    if estado != "DISFRUTADA":
        return
    existing = _existing_disfrute(vacacion_id)
    saldo = _saldo_contrato(contrato_id, existing.id if existing is not None else None)
    if saldo - dias_habiles < 0:
        raise VacacionConflictError(
            "El saldo de vacaciones no alcanza para los días hábiles solicitados."
        )


def _apply_rules(empresa_id, values, current=None):
    if "contrato_id" in values:
        same_contract = current is not None and current.contrato_id == values["contrato_id"]
        _contrato_for_company(
            empresa_id,
            values["contrato_id"],
            allow_terminated=same_contract,
        )

    contrato_id = _merged(values, current, "contrato_id")
    fecha_inicio = _merged(values, current, "fecha_inicio")
    fecha_fin = _merged(values, current, "fecha_fin")
    fecha_reintegro = _merged(values, current, "fecha_reintegro")
    dias_habiles = _merged(values, current, "dias_habiles")
    estado = _merged(values, current, "estado") or "SOLICITADA"
    _validate_period(fecha_inicio, fecha_fin, fecha_reintegro, dias_habiles)
    _ensure_no_overlap(
        contrato_id,
        fecha_inicio,
        fecha_fin,
        estado,
        vacacion_id=current.id if current is not None else None,
    )
    _ensure_balance(
        contrato_id,
        estado,
        dias_habiles,
        vacacion_id=current.id if current is not None else None,
    )


def _sync_disfrute(vacacion):
    movimiento = _existing_disfrute(vacacion.id)
    if vacacion.estado != "DISFRUTADA":
        if movimiento is not None:
            db.session.delete(movimiento)
        return

    dias = -Decimal(str(vacacion.dias_habiles)).quantize(DAYS)
    if movimiento is None:
        db.session.add(
            MovimientoVacaciones(
                contrato_id=vacacion.contrato_id,
                vacaciones_id=vacacion.id,
                fecha=vacacion.fecha_inicio,
                tipo="DISFRUTE",
                dias=dias,
                observacion="Disfrute registrado con la vacación.",
            )
        )
        return

    movimiento.contrato_id = vacacion.contrato_id
    movimiento.fecha = vacacion.fecha_inicio
    movimiento.dias = dias


def _sync_aprobacion(vacacion, current_user, previous_estado):
    if vacacion.estado in ESTADOS_APROBADOS:
        if previous_estado not in ESTADOS_APROBADOS or vacacion.aprobada_por is None:
            vacacion.aprobada_por = current_user.id
        return
    vacacion.aprobada_por = None


def _scoped_query(empresa_id):
    return (
        Vacacion.query.join(Contrato, Contrato.id == Vacacion.contrato_id)
        .join(Empleado, Empleado.id == Contrato.empleado_id)
        .filter(Empleado.empresa_id == empresa_id)
    )


def _find_vacacion(empresa_id, vacacion_id):
    vacacion = _scoped_query(empresa_id).filter(Vacacion.id == vacacion_id).first()
    if vacacion is None:
        raise VacacionNotFoundError("Vacación no encontrada.")
    return vacacion


def _commit_vacacion():
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise VacacionValidationError(
            "La vacación no cumple las reglas de fechas, días o estado."
        ) from error


def _parse_query_int(value, field):
    if value is None:
        return None
    if not isinstance(value, str) or not value.isdigit():
        raise VacacionValidationError(f"{field} debe ser un entero positivo.")
    parsed = int(value)
    if parsed < 1:
        raise VacacionValidationError(f"{field} debe ser un entero positivo.")
    return parsed


def _pagination(page, per_page):
    if page < 1:
        raise VacacionValidationError("page debe ser mayor que cero.")
    if per_page < 1 or per_page > 100:
        raise VacacionValidationError("per_page debe estar entre 1 y 100.")


def list_vacations(current_user, page=1, per_page=20, contrato_id=None, estado=None):
    empresa_id = _empresa_id_for_user(current_user)
    _pagination(page, per_page)
    if estado is not None and estado not in ESTADOS:
        options = ", ".join(sorted(ESTADOS))
        raise VacacionValidationError(f"estado debe ser uno de: {options}.")

    parsed_contrato_id = _parse_query_int(contrato_id, "contrato_id")
    if parsed_contrato_id is not None:
        _contrato_for_company(empresa_id, parsed_contrato_id, allow_terminated=True)

    query = _scoped_query(empresa_id)
    if parsed_contrato_id is not None:
        query = query.filter(Vacacion.contrato_id == parsed_contrato_id)
    if estado is not None:
        query = query.filter(Vacacion.estado == estado)
    pagination = query.order_by(Vacacion.fecha_inicio, Vacacion.id).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return {
        "items": [_serialize_vacacion(vacacion) for vacacion in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        },
    }


def get_vacation(current_user, vacacion_id):
    empresa_id = _empresa_id_for_user(current_user)
    return _serialize_vacacion(_find_vacacion(empresa_id, vacacion_id))


def create_vacation(current_user, data):
    empresa_id = _empresa_id_for_user(current_user)
    values = _validate_payload(data)
    _apply_rules(empresa_id, values)
    vacacion = Vacacion(**values)
    _sync_aprobacion(vacacion, current_user, previous_estado=None)
    db.session.add(vacacion)
    try:
        db.session.flush()
        _sync_disfrute(vacacion)
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise VacacionValidationError(
            "La vacación no cumple las reglas de fechas, días o estado."
        ) from error
    return _serialize_vacacion(vacacion)


def update_vacation(current_user, vacacion_id, data, replace=False):
    empresa_id = _empresa_id_for_user(current_user)
    vacacion = _find_vacacion(empresa_id, vacacion_id)
    values = _validate_payload(data, partial=not replace)
    if replace:
        values.setdefault("fecha_reintegro", None)
        values.setdefault("estado", "SOLICITADA")
        values.setdefault("observaciones", None)
    _apply_rules(empresa_id, values, current=vacacion)
    previous_estado = vacacion.estado
    for field, value in values.items():
        setattr(vacacion, field, value)
    if "estado" in values:
        _sync_aprobacion(vacacion, current_user, previous_estado)
    _sync_disfrute(vacacion)
    _commit_vacacion()
    return _serialize_vacacion(vacacion)


def delete_vacation(current_user, vacacion_id):
    empresa_id = _empresa_id_for_user(current_user)
    vacacion = _find_vacacion(empresa_id, vacacion_id)
    vacacion.estado = "CANCELADA"
    vacacion.aprobada_por = None
    _sync_disfrute(vacacion)
    _commit_vacacion()
    return _serialize_vacacion(vacacion)


def list_balances(current_user, page=1, per_page=20, contrato_id=None):
    empresa_id = _empresa_id_for_user(current_user)
    _pagination(page, per_page)
    parsed_contrato_id = _parse_query_int(contrato_id, "contrato_id")
    if parsed_contrato_id is not None:
        _contrato_for_company(empresa_id, parsed_contrato_id, allow_terminated=True)

    saldo = func.coalesce(func.sum(MovimientoVacaciones.dias), 0).label("dias_saldo")
    query = (
        db.session.query(
            Contrato.id.label("contrato_id"),
            Contrato.empleado_id.label("empleado_id"),
            saldo,
        )
        .join(Empleado, Empleado.id == Contrato.empleado_id)
        .outerjoin(MovimientoVacaciones, MovimientoVacaciones.contrato_id == Contrato.id)
        .filter(Empleado.empresa_id == empresa_id)
        .group_by(Contrato.id, Contrato.empleado_id)
    )
    if parsed_contrato_id is not None:
        query = query.filter(Contrato.id == parsed_contrato_id)

    total = db.session.query(func.count()).select_from(query.subquery()).scalar() or 0
    rows = (
        query.order_by(Contrato.id)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    pages = (total + per_page - 1) // per_page if total else 0
    return {
        "items": [
            {
                "contrato_id": row.contrato_id,
                "empleado_id": row.empleado_id,
                "dias_saldo": _json_days(row.dias_saldo),
            }
            for row in rows
        ],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
        },
    }
