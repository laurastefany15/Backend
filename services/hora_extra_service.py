from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Asistencia, Contrato, Empleado, Empresa, HoraExtra, TipoRecargo


ESTADOS_EDITABLES = {"PENDIENTE", "APROBADA", "RECHAZADA"}
ESTADOS = ESTADOS_EDITABLES | {"LIQUIDADA"}
REQUIRED_FIELDS = {"contrato_id", "tipo_codigo", "fecha", "cantidad_horas"}
OPTIONAL_FIELDS = {"asistencia_id", "estado", "observaciones"}
WRITABLE_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS
HOURS = Decimal("0.001")


class HoraExtraValidationError(ValueError):
    pass


class HoraExtraNotFoundError(LookupError):
    pass


class HoraExtraForbiddenError(PermissionError):
    pass


class HoraExtraConflictError(ValueError):
    pass


def _empresa_id_for_user(current_user):
    empresa_id = current_user.empresa_id
    if empresa_id is None:
        raise HoraExtraForbiddenError("El usuario no está asociado a una empresa.")

    empresa = db.session.get(Empresa, empresa_id)
    if empresa is None or not empresa.activa:
        raise HoraExtraForbiddenError("La empresa del usuario no está disponible.")
    return empresa_id


def _parse_date(value):
    if not isinstance(value, str):
        raise HoraExtraValidationError("fecha debe usar el formato YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise HoraExtraValidationError("fecha debe usar el formato YYYY-MM-DD.") from error


def _parse_hours(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise HoraExtraValidationError("cantidad_horas debe ser un número.")
    try:
        hours = Decimal(str(value).strip()).quantize(HOURS, rounding=ROUND_HALF_UP)
    except InvalidOperation as error:
        raise HoraExtraValidationError("cantidad_horas debe ser un número.") from error
    if not hours.is_finite() or hours <= 0 or hours > 24:
        raise HoraExtraValidationError("cantidad_horas debe ser mayor que 0 y no superar 24.")
    return hours


def _validate_payload(data, partial=False):
    if not isinstance(data, dict):
        raise HoraExtraValidationError("El cuerpo debe ser un objeto JSON.")
    if not data:
        raise HoraExtraValidationError("Debe enviar al menos un campo.")

    unknown_fields = set(data) - WRITABLE_FIELDS
    if unknown_fields:
        fields = ", ".join(sorted(unknown_fields))
        raise HoraExtraValidationError(f"Campos no permitidos: {fields}.")

    if not partial:
        missing_fields = REQUIRED_FIELDS - set(data)
        if missing_fields:
            fields = ", ".join(sorted(missing_fields))
            raise HoraExtraValidationError(f"Faltan campos obligatorios: {fields}.")

    values = {}
    for field, value in data.items():
        if field in {"contrato_id", "asistencia_id"}:
            if field == "asistencia_id" and value is None:
                values[field] = None
            elif isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise HoraExtraValidationError(f"{field} debe ser un entero positivo.")
            else:
                values[field] = value
        elif field == "tipo_codigo":
            if not isinstance(value, str) or not value.strip():
                raise HoraExtraValidationError("tipo_codigo debe ser texto.")
            values[field] = value.strip().upper()
        elif field == "fecha":
            values[field] = _parse_date(value)
        elif field == "cantidad_horas":
            values[field] = _parse_hours(value)
        elif field == "estado":
            if not isinstance(value, str) or value not in ESTADOS_EDITABLES:
                options = ", ".join(sorted(ESTADOS_EDITABLES))
                raise HoraExtraValidationError(f"estado debe ser uno de: {options}.")
            values[field] = value
        elif field == "observaciones":
            if value is not None and not isinstance(value, str):
                raise HoraExtraValidationError("observaciones debe ser texto o null.")
            values[field] = (value.strip() or None) if isinstance(value, str) else None

    if not partial:
        values.setdefault("asistencia_id", None)
        values.setdefault("estado", "PENDIENTE")
        values.setdefault("observaciones", None)
    return values


def _optional_decimal(value, scale):
    if value is None:
        return None
    return float(Decimal(str(value)).quantize(scale))


def _serialize(hora_extra):
    return {
        "id": hora_extra.id,
        "contrato_id": hora_extra.contrato_id,
        "asistencia_id": hora_extra.asistencia_id,
        "tipo_codigo": hora_extra.tipo_codigo,
        "fecha": hora_extra.fecha.isoformat(),
        "cantidad_horas": float(Decimal(str(hora_extra.cantidad_horas)).quantize(HOURS)),
        "valor_hora_base": _optional_decimal(hora_extra.valor_hora_base, Decimal("0.0001")),
        "porcentaje_aplicado": _optional_decimal(hora_extra.porcentaje_aplicado, Decimal("0.0001")),
        "modo_pago_aplicado": hora_extra.modo_pago_aplicado,
        "valor_calculado": _optional_decimal(hora_extra.valor_calculado, Decimal("0.01")),
        "estado": hora_extra.estado,
        "aprobado_por": hora_extra.aprobado_por,
        "observaciones": hora_extra.observaciones,
    }


def _merged(values, current, field):
    if field in values:
        return values[field]
    return getattr(current, field) if current is not None else None


def _contrato_for_company(empresa_id, contrato_id, allow_terminated=False):
    contrato = (
        Contrato.query.join(Empleado, Empleado.id == Contrato.empleado_id)
        .filter(Contrato.id == contrato_id, Empleado.empresa_id == empresa_id)
        .first()
    )
    if contrato is None:
        raise HoraExtraNotFoundError("Contrato no encontrado.")
    if not allow_terminated and contrato.estado != "ACTIVO":
        raise HoraExtraConflictError(
            "No se pueden registrar horas extras en un contrato terminado."
        )
    return contrato


def _apply_rules(empresa_id, values, current=None):
    if current is not None and current.estado == "LIQUIDADA":
        raise HoraExtraConflictError(
            "La hora extra ya fue liquidada en una nómina aprobada; no se puede modificar."
        )

    contrato_id = _merged(values, current, "contrato_id")
    same_contract = current is not None and current.contrato_id == contrato_id
    contrato = _contrato_for_company(empresa_id, contrato_id, allow_terminated=same_contract)

    tipo_codigo = _merged(values, current, "tipo_codigo")
    tipo = db.session.get(TipoRecargo, tipo_codigo)
    if tipo is None or not tipo.activo:
        options = ", ".join(
            row.codigo for row in TipoRecargo.query.filter_by(activo=True).order_by(TipoRecargo.codigo)
        )
        raise HoraExtraValidationError(f"tipo_codigo debe ser uno de: {options}.")

    fecha = _merged(values, current, "fecha")
    if fecha < contrato.fecha_inicio or (contrato.fecha_fin and fecha > contrato.fecha_fin):
        raise HoraExtraValidationError("fecha debe estar dentro de la vigencia del contrato.")

    asistencia_id = _merged(values, current, "asistencia_id")
    if asistencia_id is not None:
        asistencia = db.session.get(Asistencia, asistencia_id)
        if asistencia is None or asistencia.contrato_id != contrato.id:
            raise HoraExtraNotFoundError("La asistencia no pertenece al contrato indicado.")


def _sync_approval(hora_extra, current_user):
    if hora_extra.estado == "APROBADA":
        if hora_extra.aprobado_por is None:
            hora_extra.aprobado_por = current_user.id
    else:
        hora_extra.aprobado_por = None


def _scoped_query(empresa_id):
    return (
        HoraExtra.query.join(Contrato, Contrato.id == HoraExtra.contrato_id)
        .join(Empleado, Empleado.id == Contrato.empleado_id)
        .filter(Empleado.empresa_id == empresa_id)
    )


def _find(empresa_id, hora_extra_id):
    hora_extra = _scoped_query(empresa_id).filter(HoraExtra.id == hora_extra_id).first()
    if hora_extra is None:
        raise HoraExtraNotFoundError("Hora extra no encontrada.")
    return hora_extra


def _commit():
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise HoraExtraValidationError(
            "La hora extra no cumple las reglas de tipo, cantidad o estado."
        ) from error


def _parse_query_int(value, field):
    if value is None:
        return None
    if not value.isdigit() or int(value) < 1:
        raise HoraExtraValidationError(f"{field} debe ser un entero positivo.")
    return int(value)


def list_overtime(current_user, page=1, per_page=20, contrato_id=None, estado=None,
                  desde=None, hasta=None):
    empresa_id = _empresa_id_for_user(current_user)
    if page < 1:
        raise HoraExtraValidationError("page debe ser mayor que cero.")
    if per_page < 1 or per_page > 100:
        raise HoraExtraValidationError("per_page debe estar entre 1 y 100.")
    if estado is not None and estado not in ESTADOS:
        options = ", ".join(sorted(ESTADOS))
        raise HoraExtraValidationError(f"estado debe ser uno de: {options}.")

    query = _scoped_query(empresa_id)
    parsed_contrato_id = _parse_query_int(contrato_id, "contrato_id")
    if parsed_contrato_id is not None:
        _contrato_for_company(empresa_id, parsed_contrato_id, allow_terminated=True)
        query = query.filter(HoraExtra.contrato_id == parsed_contrato_id)
    if estado is not None:
        query = query.filter(HoraExtra.estado == estado)
    if desde is not None:
        query = query.filter(HoraExtra.fecha >= _parse_date(desde))
    if hasta is not None:
        query = query.filter(HoraExtra.fecha <= _parse_date(hasta))
    pagination = query.order_by(HoraExtra.fecha, HoraExtra.id).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return {
        "items": [_serialize(item) for item in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        },
    }


def get_overtime(current_user, hora_extra_id):
    empresa_id = _empresa_id_for_user(current_user)
    return _serialize(_find(empresa_id, hora_extra_id))


def create_overtime(current_user, data):
    empresa_id = _empresa_id_for_user(current_user)
    values = _validate_payload(data)
    _apply_rules(empresa_id, values)
    hora_extra = HoraExtra(**values)
    _sync_approval(hora_extra, current_user)
    db.session.add(hora_extra)
    _commit()
    return _serialize(hora_extra)


def update_overtime(current_user, hora_extra_id, data, replace=False):
    empresa_id = _empresa_id_for_user(current_user)
    hora_extra = _find(empresa_id, hora_extra_id)
    values = _validate_payload(data, partial=not replace)
    if replace:
        values.setdefault("asistencia_id", None)
        values.setdefault("estado", "PENDIENTE")
        values.setdefault("observaciones", None)
    _apply_rules(empresa_id, values, current=hora_extra)
    for field, value in values.items():
        setattr(hora_extra, field, value)
    _sync_approval(hora_extra, current_user)
    _commit()
    return _serialize(hora_extra)


def delete_overtime(current_user, hora_extra_id):
    empresa_id = _empresa_id_for_user(current_user)
    hora_extra = _find(empresa_id, hora_extra_id)
    if hora_extra.estado == "LIQUIDADA":
        raise HoraExtraConflictError(
            "La hora extra ya fue liquidada en una nómina aprobada; no se puede rechazar."
        )
    hora_extra.estado = "RECHAZADA"
    hora_extra.aprobado_por = None
    _commit()
    return _serialize(hora_extra)
