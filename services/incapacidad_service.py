from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Contrato, Empleado, Empresa, Incapacidad, Vacacion


TIPOS = {
    "ENFERMEDAD_GENERAL",
    "ACCIDENTE_LABORAL",
    "ENFERMEDAD_LABORAL",
    "MATERNIDAD",
    "PATERNIDAD",
    "OTRA",
}
ESTADOS = {"REGISTRADA", "VALIDADA", "EN_COBRO", "PAGADA", "RECHAZADA"}
REQUIRED_FIELDS = {"contrato_id", "tipo", "fecha_inicio", "fecha_fin"}
OPTIONAL_FIELDS = {
    "entidad_responsable",
    "numero_certificado",
    "porcentaje_reconocimiento",
    "valor_estimado",
    "valor_reconocido",
    "estado",
    "observaciones",
}
WRITABLE_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS
INTEGER_FORM_FIELDS = {"contrato_id"}
MONEY = Decimal("0.01")
RATE = Decimal("0.0001")
MAX_MONEY = Decimal("9999999999999.99")


class IncapacidadValidationError(ValueError):
    pass


class IncapacidadNotFoundError(LookupError):
    pass


class IncapacidadForbiddenError(PermissionError):
    pass


class IncapacidadConflictError(ValueError):
    pass


def _empresa_id_for_user(current_user):
    empresa_id = current_user.empresa_id
    if empresa_id is None:
        raise IncapacidadForbiddenError("El usuario no está asociado a una empresa.")

    empresa = db.session.get(Empresa, empresa_id)
    if empresa is None or not empresa.activa:
        raise IncapacidadForbiddenError("La empresa del usuario no está disponible.")
    return empresa_id


def _parse_date(value, field, required=False):
    if value is None:
        if required:
            raise IncapacidadValidationError(f"{field} es obligatoria.")
        return None
    if not isinstance(value, str):
        raise IncapacidadValidationError(f"{field} debe usar el formato YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise IncapacidadValidationError(f"{field} debe usar el formato YYYY-MM-DD.") from error


def _parse_decimal(value, field, scale, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise IncapacidadValidationError(f"{field} debe ser un número.")
    if isinstance(value, str):
        value = value.strip()
        if not value:
            raise IncapacidadValidationError(f"{field} debe ser un número.")
    try:
        amount = Decimal(str(value)).quantize(scale, rounding=ROUND_HALF_UP)
    except InvalidOperation as error:
        raise IncapacidadValidationError(f"{field} debe ser un número.") from error
    if not amount.is_finite() or amount < minimum or amount > maximum:
        raise IncapacidadValidationError(
            f"{field} debe estar entre {minimum} y {maximum}."
        )
    return amount


def _optional_text(value, field, limit=None):
    if value is None:
        return None
    if not isinstance(value, str):
        raise IncapacidadValidationError(f"{field} debe ser texto o null.")
    value = value.strip()
    if not value:
        return None
    if limit is not None and len(value) > limit:
        raise IncapacidadValidationError(f"{field} no puede superar {limit} caracteres.")
    return value


def _optional_number(value, field, scale, minimum, maximum):
    if value is None:
        return None
    return _parse_decimal(value, field, scale, minimum, maximum)


def _validate_payload(data, partial=False):
    if not isinstance(data, dict):
        raise IncapacidadValidationError("El cuerpo debe ser un objeto JSON.")
    if not data:
        raise IncapacidadValidationError("Debe enviar al menos un campo.")

    unknown_fields = set(data) - WRITABLE_FIELDS
    if unknown_fields:
        fields = ", ".join(sorted(unknown_fields))
        raise IncapacidadValidationError(f"Campos no permitidos: {fields}.")

    if not partial:
        missing_fields = REQUIRED_FIELDS - set(data)
        if missing_fields:
            fields = ", ".join(sorted(missing_fields))
            raise IncapacidadValidationError(f"Faltan campos obligatorios: {fields}.")

    values = {}
    for field, value in data.items():
        if field == "contrato_id":
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise IncapacidadValidationError("contrato_id debe ser un entero positivo.")
            values[field] = value
        elif field == "tipo":
            if not isinstance(value, str) or value not in TIPOS:
                options = ", ".join(sorted(TIPOS))
                raise IncapacidadValidationError(f"tipo debe ser uno de: {options}.")
            values[field] = value
        elif field in {"fecha_inicio", "fecha_fin"}:
            values[field] = _parse_date(value, field, required=True)
        elif field == "entidad_responsable":
            values[field] = _optional_text(value, field, 150)
        elif field == "numero_certificado":
            values[field] = _optional_text(value, field, 100)
        elif field == "porcentaje_reconocimiento":
            values[field] = _optional_number(value, field, RATE, Decimal("0"), Decimal("100"))
        elif field in {"valor_estimado", "valor_reconocido"}:
            values[field] = _optional_number(value, field, MONEY, Decimal("0"), MAX_MONEY)
        elif field == "estado":
            if not isinstance(value, str) or value not in ESTADOS:
                options = ", ".join(sorted(ESTADOS))
                raise IncapacidadValidationError(f"estado debe ser uno de: {options}.")
            values[field] = value
        elif field == "observaciones":
            values[field] = _optional_text(value, field)

    if not partial:
        values.setdefault("entidad_responsable", None)
        values.setdefault("numero_certificado", None)
        values.setdefault("porcentaje_reconocimiento", None)
        values.setdefault("valor_estimado", None)
        values.setdefault("valor_reconocido", None)
        values.setdefault("estado", "REGISTRADA")
        values.setdefault("observaciones", None)
    return values


def form_to_payload(form):
    """Convierte los campos de un formulario multipart al formato del cuerpo JSON."""
    data = {}
    for field, value in form.items():
        value = value.strip()
        if field in INTEGER_FORM_FIELDS:
            data[field] = int(value) if value.isdigit() else value
        elif field in REQUIRED_FIELDS or value:
            data[field] = value
    return data


def _json_decimal(value, scale):
    if value is None:
        return None
    return float(Decimal(str(value)).quantize(scale))


def _serialize_incapacidad(incapacidad):
    from services.documento_incapacidad_service import documents_for, serialize_documento

    documentos = documents_for(incapacidad.id) if incapacidad.id is not None else []
    return {
        "id": incapacidad.id,
        "contrato_id": incapacidad.contrato_id,
        "tipo": incapacidad.tipo,
        "fecha_inicio": incapacidad.fecha_inicio.isoformat(),
        "fecha_fin": incapacidad.fecha_fin.isoformat(),
        "entidad_responsable": incapacidad.entidad_responsable,
        "numero_certificado": incapacidad.numero_certificado,
        "porcentaje_reconocimiento": _json_decimal(
            incapacidad.porcentaje_reconocimiento, RATE
        ),
        "valor_estimado": _json_decimal(incapacidad.valor_estimado, MONEY),
        "valor_reconocido": _json_decimal(incapacidad.valor_reconocido, MONEY),
        "estado": incapacidad.estado,
        "observaciones": incapacidad.observaciones,
        "documentos": [serialize_documento(documento) for documento in documentos],
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
        raise IncapacidadNotFoundError("Contrato no encontrado.")
    if not allow_terminated and contrato.estado != "ACTIVO":
        raise IncapacidadConflictError(
            "No se puede registrar la incapacidad en un contrato terminado."
        )
    return contrato


def _validate_period(fecha_inicio, fecha_fin):
    if fecha_inicio is None:
        raise IncapacidadValidationError("fecha_inicio es obligatoria.")
    if fecha_fin is None:
        raise IncapacidadValidationError("fecha_fin es obligatoria.")
    if fecha_fin < fecha_inicio:
        raise IncapacidadValidationError("fecha_fin no puede ser anterior a fecha_inicio.")


def _ensure_no_overlap(contrato_id, fecha_inicio, fecha_fin, estado, incapacidad_id=None):
    if estado == "RECHAZADA":
        return

    incapacidades = Incapacidad.query.filter(
        Incapacidad.contrato_id == contrato_id,
        Incapacidad.estado != "RECHAZADA",
        Incapacidad.fecha_inicio <= fecha_fin,
        Incapacidad.fecha_fin >= fecha_inicio,
    )
    if incapacidad_id is not None:
        incapacidades = incapacidades.filter(Incapacidad.id != incapacidad_id)
    if incapacidades.first() is not None:
        raise IncapacidadConflictError(
            "Las fechas se cruzan con otra incapacidad del mismo contrato."
        )

    vacacion = Vacacion.query.filter(
        Vacacion.contrato_id == contrato_id,
        Vacacion.estado != "CANCELADA",
        Vacacion.fecha_inicio <= fecha_fin,
        Vacacion.fecha_fin >= fecha_inicio,
    ).first()
    if vacacion is not None:
        raise IncapacidadConflictError(
            "Las fechas se cruzan con una vacación del mismo contrato."
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
    estado = _merged(values, current, "estado") or "REGISTRADA"
    _validate_period(fecha_inicio, fecha_fin)
    _ensure_no_overlap(
        contrato_id,
        fecha_inicio,
        fecha_fin,
        estado,
        incapacidad_id=current.id if current is not None else None,
    )


def _scoped_query(empresa_id):
    return (
        Incapacidad.query.join(Contrato, Contrato.id == Incapacidad.contrato_id)
        .join(Empleado, Empleado.id == Contrato.empleado_id)
        .filter(Empleado.empresa_id == empresa_id)
    )


def _find_incapacidad(empresa_id, incapacidad_id):
    incapacidad = (
        _scoped_query(empresa_id).filter(Incapacidad.id == incapacidad_id).first()
    )
    if incapacidad is None:
        raise IncapacidadNotFoundError("Incapacidad no encontrada.")
    return incapacidad


def _commit_incapacidad():
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise IncapacidadValidationError(
            "La incapacidad no cumple las reglas de tipo, fechas o estado."
        ) from error


def _parse_query_int(value, field):
    if value is None:
        return None
    if not isinstance(value, str) or not value.isdigit():
        raise IncapacidadValidationError(f"{field} debe ser un entero positivo.")
    parsed = int(value)
    if parsed < 1:
        raise IncapacidadValidationError(f"{field} debe ser un entero positivo.")
    return parsed


def list_disabilities(current_user, page=1, per_page=20, contrato_id=None, estado=None, tipo=None):
    empresa_id = _empresa_id_for_user(current_user)
    if page < 1:
        raise IncapacidadValidationError("page debe ser mayor que cero.")
    if per_page < 1 or per_page > 100:
        raise IncapacidadValidationError("per_page debe estar entre 1 y 100.")
    if estado is not None and estado not in ESTADOS:
        options = ", ".join(sorted(ESTADOS))
        raise IncapacidadValidationError(f"estado debe ser uno de: {options}.")
    if tipo is not None and tipo not in TIPOS:
        options = ", ".join(sorted(TIPOS))
        raise IncapacidadValidationError(f"tipo debe ser uno de: {options}.")

    parsed_contrato_id = _parse_query_int(contrato_id, "contrato_id")
    if parsed_contrato_id is not None:
        _contrato_for_company(empresa_id, parsed_contrato_id, allow_terminated=True)

    query = _scoped_query(empresa_id)
    if parsed_contrato_id is not None:
        query = query.filter(Incapacidad.contrato_id == parsed_contrato_id)
    if estado is not None:
        query = query.filter(Incapacidad.estado == estado)
    if tipo is not None:
        query = query.filter(Incapacidad.tipo == tipo)
    pagination = query.order_by(Incapacidad.fecha_inicio, Incapacidad.id).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return {
        "items": [_serialize_incapacidad(item) for item in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        },
    }


def get_disability(current_user, incapacidad_id):
    empresa_id = _empresa_id_for_user(current_user)
    return _serialize_incapacidad(_find_incapacidad(empresa_id, incapacidad_id))


def create_disability(current_user, data, uploads=None, tipo_documento=None):
    from services.documento_incapacidad_service import (
        discard_files,
        parse_tipo_documento,
        stage_documents,
    )

    empresa_id = _empresa_id_for_user(current_user)
    values = _validate_payload(data)
    _apply_rules(empresa_id, values)
    tipo = parse_tipo_documento(tipo_documento) if uploads else None
    incapacidad = Incapacidad(**values)
    db.session.add(incapacidad)
    paths = []
    try:
        db.session.flush()
        if uploads:
            _, paths = stage_documents(incapacidad.id, uploads, tipo, current_user)
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        discard_files(paths)
        raise IncapacidadValidationError(
            "La incapacidad no cumple las reglas de tipo, fechas o estado."
        ) from error
    except Exception:
        db.session.rollback()
        discard_files(paths)
        raise
    return _serialize_incapacidad(incapacidad)


def update_disability(current_user, incapacidad_id, data, replace=False):
    empresa_id = _empresa_id_for_user(current_user)
    incapacidad = _find_incapacidad(empresa_id, incapacidad_id)
    values = _validate_payload(data, partial=not replace)
    if replace:
        for field in (
            "entidad_responsable",
            "numero_certificado",
            "porcentaje_reconocimiento",
            "valor_estimado",
            "valor_reconocido",
            "observaciones",
        ):
            values.setdefault(field, None)
        values.setdefault("estado", "REGISTRADA")
    _apply_rules(empresa_id, values, current=incapacidad)
    for field, value in values.items():
        setattr(incapacidad, field, value)
    _commit_incapacidad()
    return _serialize_incapacidad(incapacidad)


def delete_disability(current_user, incapacidad_id):
    empresa_id = _empresa_id_for_user(current_user)
    incapacidad = _find_incapacidad(empresa_id, incapacidad_id)
    incapacidad.estado = "RECHAZADA"
    _commit_incapacidad()
    return _serialize_incapacidad(incapacidad)
