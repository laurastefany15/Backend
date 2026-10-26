from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import (
    ConceptoNomina,
    Contrato,
    DeduccionEmpleado,
    DetalleNomina,
    Empleado,
    Empresa,
    HistorialSalario,
    HoraExtra,
    Incapacidad,
    Licencia,
    Nomina,
    PagoNomina,
    ParametroNomina,
    PeriodoNomina,
    TarifaRecargo,
    TipoRecargo,
    Vacacion,
)


MONEY = Decimal("0.01")
RATE = Decimal("0.0001")
QTY = Decimal("0.001")
HUNDRED = Decimal("100")
THIRTY = Decimal("30")
ESTADOS = {"BORRADOR", "APROBADA", "PAGADA", "ANULADA"}
MEDIOS_PAGO = {"TRANSFERENCIA", "EFECTIVO", "CHEQUE", "OTRO"}
ESTADOS_VACACION_PAGADA = ("APROBADA", "DISFRUTADA")
ESTADOS_LICENCIA_EFECTIVA = ("APROBADA", "DISFRUTADA")
INCAPACIDAD_100 = {"ACCIDENTE_LABORAL", "ENFERMEDAD_LABORAL", "MATERNIDAD", "PATERNIDAD"}
INCAPACIDAD_GENERAL_PCT = Decimal("66.67")
INCAPACIDAD_PROLONGADA_PCT = Decimal("50")
ORDEN_DEDUCCIONES = {"EMBARGO": 0, "LIBRANZA": 1, "PRESTAMO": 2, "OTRA_DEDUCCION": 3}
GENERAR_FIELDS = {"anio", "mes", "quincena", "fecha", "fecha_pago", "empleado_id", "contrato_id"}
PAGO_FIELDS = {"fecha_pago", "medio", "referencia", "observaciones"}


class NominaValidationError(ValueError):
    pass


class NominaNotFoundError(LookupError):
    pass


class NominaForbiddenError(PermissionError):
    pass


class NominaConflictError(ValueError):
    pass


@dataclass
class Linea:
    concepto: str
    valor: Decimal
    cantidad: Decimal = None
    valor_unitario: Decimal = None
    porcentaje: Decimal = None
    origen_tipo: str = None
    origen_id: int = None
    descripcion: str = None


@dataclass
class Liquidacion:
    salario_referencia: Decimal
    lineas: list = field(default_factory=list)
    notas: list = field(default_factory=list)
    horas_extras: list = field(default_factory=list)


def _money(value):
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def _dec(value):
    return Decimal(str(value))


def _empresa_id_for_user(current_user):
    empresa_id = current_user.empresa_id
    if empresa_id is None:
        raise NominaForbiddenError("El usuario no está asociado a una empresa.")
    empresa = db.session.get(Empresa, empresa_id)
    if empresa is None or not empresa.activa:
        raise NominaForbiddenError("La empresa del usuario no está disponible.")
    return empresa_id


def quincena_bounds(anio, mes, quincena):
    if quincena == 1:
        return date(anio, mes, 1), date(anio, mes, 15)
    return date(anio, mes, 16), date(anio, mes, monthrange(anio, mes)[1])


def day_weight(day):
    """Peso del día en el mes comercial de 30 días."""
    last = monthrange(day.year, day.month)[1]
    if day.day == 31:
        return 0
    if day.day == last and last < 30:
        return 30 - day.day + 1
    return 1


def _days(start, end):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _param(empresa_id, codigo, fecha, required=True):
    value = ParametroNomina.get_vigente(empresa_id, codigo, fecha)
    if value is None:
        if required:
            raise NominaConflictError(
                f"No hay un valor vigente del parámetro {codigo} para {fecha.isoformat()}."
            )
        return None
    return _dec(value)


def _salary_lookup(contrato):
    historial = (
        HistorialSalario.query.filter_by(contrato_id=contrato.id)
        .order_by(HistorialSalario.vigente_desde)
        .all()
    )

    def salary_on(day):
        value = contrato.salario_mensual
        for registro in historial:
            if registro.vigente_desde > day:
                break
            value = registro.salario_mensual
        return _dec(value)

    return salary_on


def _covering(items, day):
    return next((item for item in items if item.fecha_inicio <= day <= item.fecha_fin), None)


def _incapacidad_pct(incapacidad, day_number):
    if incapacidad.porcentaje_reconocimiento is not None:
        return _dec(incapacidad.porcentaje_reconocimiento)
    if incapacidad.tipo in INCAPACIDAD_100:
        return HUNDRED
    if day_number <= 90:
        return INCAPACIDAD_GENERAL_PCT
    return INCAPACIDAD_PROLONGADA_PCT


def _fsp_rate(ibc_mensual, smmlv):
    veces = ibc_mensual / smmlv
    if veces < 4:
        return None
    if veces < 16:
        return Decimal("1")
    if veces >= 20:
        return Decimal("2")
    return Decimal("1") + (Decimal(int(veces) - 15) * Decimal("0.2"))


def _liquidar(contrato, periodo, empresa_id, nomina_id=None):
    start = max(periodo.fecha_inicio, contrato.fecha_inicio)
    end = min(periodo.fecha_fin, contrato.fecha_fin or periodo.fecha_fin)
    if start > end:
        raise NominaConflictError("El contrato no estuvo vigente en el periodo.")

    smmlv = _param(empresa_id, "SMMLV", periodo.fecha_fin)
    salary_on = _salary_lookup(contrato)
    resultado = Liquidacion(salario_referencia=_money(salary_on(end)))

    incapacidades = Incapacidad.query.filter(
        Incapacidad.contrato_id == contrato.id,
        Incapacidad.estado != "RECHAZADA",
        Incapacidad.fecha_inicio <= end,
        Incapacidad.fecha_fin >= start,
    ).all()
    vacaciones = Vacacion.query.filter(
        Vacacion.contrato_id == contrato.id,
        Vacacion.estado.in_(ESTADOS_VACACION_PAGADA),
        Vacacion.fecha_inicio <= end,
        Vacacion.fecha_fin >= start,
    ).all()
    licencias = Licencia.query.filter(
        Licencia.contrato_id == contrato.id,
        Licencia.estado.in_(ESTADOS_LICENCIA_EFECTIVA),
        Licencia.fecha_inicio <= end,
        Licencia.fecha_fin >= start,
    ).all()

    trabajados = Decimal("0")
    valor_trabajado = Decimal("0")
    no_remunerados = Decimal("0")
    por_vacacion = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    por_licencia = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    por_incapacidad = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    piso_diario = smmlv / THIRTY

    for day in _days(start, end):
        weight = Decimal(day_weight(day))
        if not weight:
            continue
        diario = salary_on(day) / THIRTY
        incapacidad = _covering(incapacidades, day)
        if incapacidad is not None:
            number = (day - incapacidad.fecha_inicio).days + 1
            pct = _incapacidad_pct(incapacidad, number)
            valor = diario * pct / HUNDRED
            if incapacidad.tipo not in INCAPACIDAD_100 and number <= 180:
                valor = max(valor, piso_diario)
            acumulado = por_incapacidad[(incapacidad.id, pct)]
            acumulado[0] += weight
            acumulado[1] += valor * weight
            continue
        vacacion = _covering(vacaciones, day)
        if vacacion is not None:
            por_vacacion[vacacion.id][0] += weight
            por_vacacion[vacacion.id][1] += diario * weight
            continue
        licencia = _covering(licencias, day)
        if licencia is not None:
            if licencia.remunerada:
                por_licencia[licencia.id][0] += weight
                por_licencia[licencia.id][1] += diario * weight
            else:
                no_remunerados += weight
            continue
        trabajados += weight
        valor_trabajado += diario * weight

    if trabajados:
        resultado.lineas.append(
            Linea(
                concepto="SALARIO",
                cantidad=trabajados,
                valor_unitario=valor_trabajado / trabajados,
                valor=_money(valor_trabajado),
                descripcion=f"Salario por {trabajados} días trabajados",
            )
        )
    for licencia_id, (dias, valor) in por_licencia.items():
        resultado.lineas.append(
            Linea(
                concepto="SALARIO",
                cantidad=dias,
                valor_unitario=valor / dias,
                valor=_money(valor),
                origen_tipo="LICENCIA",
                origen_id=licencia_id,
                descripcion=f"Licencia remunerada por {dias} días",
            )
        )
    if no_remunerados:
        resultado.notas.append(f"Licencia no remunerada: {no_remunerados} días sin pago.")
    for vacacion_id, (dias, valor) in por_vacacion.items():
        resultado.lineas.append(
            Linea(
                concepto="VACACIONES",
                cantidad=dias,
                valor_unitario=valor / dias,
                valor=_money(valor),
                origen_tipo="VACACION",
                origen_id=vacacion_id,
                descripcion=f"Vacaciones por {dias} días",
            )
        )
    tipos_incapacidad = {incapacidad.id: incapacidad.tipo for incapacidad in incapacidades}
    for (incapacidad_id, pct), (dias, valor) in por_incapacidad.items():
        resultado.lineas.append(
            Linea(
                concepto="INCAPACIDAD",
                cantidad=dias,
                valor_unitario=valor / dias,
                porcentaje=pct,
                valor=_money(valor),
                origen_tipo="INCAPACIDAD",
                origen_id=incapacidad_id,
                descripcion=(
                    f"Incapacidad {tipos_incapacidad[incapacidad_id]} por {dias} días al {pct}%"
                ),
            )
        )

    _liquidar_horas_extras(contrato, empresa_id, start, end, salary_on, resultado)

    if trabajados and contrato.tiene_auxilio_transporte:
        limite = _param(empresa_id, "LIMITE_AUX_TRANSPORTE_SMMLV", periodo.fecha_fin) * smmlv
        if resultado.salario_referencia <= limite:
            auxilio = _param(empresa_id, "AUX_TRANSPORTE", periodo.fecha_fin)
            resultado.lineas.append(
                Linea(
                    concepto="AUX_TRANSPORTE",
                    cantidad=trabajados,
                    valor_unitario=auxilio / THIRTY,
                    valor=_money(auxilio / THIRTY * trabajados),
                    descripcion=f"Auxilio de transporte por {trabajados} días trabajados",
                )
            )
        else:
            resultado.notas.append(
                "Sin auxilio de transporte: el salario supera el tope de "
                f"{_money(limite)}."
            )

    dias_pagados = (
        trabajados
        + sum((dias for dias, _ in por_licencia.values()), Decimal("0"))
        + sum((dias for dias, _ in por_vacacion.values()), Decimal("0"))
        + sum((dias for dias, _ in por_incapacidad.values()), Decimal("0"))
    )
    _liquidar_seguridad_social(contrato, empresa_id, periodo, smmlv, dias_pagados, resultado)
    _liquidar_deducciones(contrato, start, end, nomina_id, resultado)
    return resultado


def _liquidar_horas_extras(contrato, empresa_id, start, end, salary_on, resultado):
    horas_extras = (
        HoraExtra.query.filter(
            HoraExtra.contrato_id == contrato.id,
            HoraExtra.estado == "APROBADA",
            HoraExtra.fecha >= start,
            HoraExtra.fecha <= end,
        )
        .order_by(HoraExtra.fecha, HoraExtra.id)
        .all()
    )
    for hora_extra in horas_extras:
        tipo = db.session.get(TipoRecargo, hora_extra.tipo_codigo)
        porcentaje = TarifaRecargo.get_vigente(empresa_id, hora_extra.tipo_codigo, hora_extra.fecha)
        if porcentaje is None:
            raise NominaConflictError(
                f"No hay una tarifa vigente de {hora_extra.tipo_codigo} para "
                f"{hora_extra.fecha.isoformat()}."
            )
        porcentaje = _dec(porcentaje)
        divisor = _param(empresa_id, "DIVISOR_HORA_MENSUAL", hora_extra.fecha, required=False)
        if divisor is None:
            divisor = _dec(contrato.horas_semanales) * 5
        valor_hora = salary_on(hora_extra.fecha) / divisor
        factor = porcentaje / HUNDRED
        if tipo.modo_pago == "COMPLETO":
            factor += 1
        horas = _dec(hora_extra.cantidad_horas)
        valor = _money(horas * valor_hora * factor)
        resultado.lineas.append(
            Linea(
                concepto=hora_extra.tipo_codigo,
                cantidad=horas,
                valor_unitario=valor_hora * factor,
                porcentaje=porcentaje,
                valor=valor,
                origen_tipo="HORA_EXTRA",
                origen_id=hora_extra.id,
                descripcion=f"{tipo.nombre} del {hora_extra.fecha.isoformat()}",
            )
        )
        resultado.horas_extras.append(
            (hora_extra, valor_hora.quantize(RATE), porcentaje, tipo.modo_pago, valor)
        )


def _liquidar_seguridad_social(contrato, empresa_id, periodo, smmlv, dias_pagados, resultado):
    if contrato.tipo_contrato == "APRENDIZAJE" or not dias_pagados:
        return

    conceptos = {
        concepto.codigo: concepto
        for concepto in ConceptoNomina.query.filter(
            ConceptoNomina.codigo.in_({linea.concepto for linea in resultado.lineas})
        )
    }
    ibc = sum(
        (
            linea.valor
            for linea in resultado.lineas
            if conceptos[linea.concepto].integra_base_seguridad_social
        ),
        Decimal("0"),
    )
    ibc = max(ibc, smmlv / THIRTY * dias_pagados)
    ibc = _money(min(ibc, smmlv * 25 / THIRTY * dias_pagados))

    fecha = periodo.fecha_fin
    for concepto, codigo in (
        ("SALUD", "APORTE_SALUD_TRABAJADOR"),
        ("PENSION", "APORTE_PENSION_TRABAJADOR"),
    ):
        pct = _param(empresa_id, codigo, fecha)
        resultado.lineas.append(
            Linea(
                concepto=concepto,
                valor_unitario=ibc,
                porcentaje=pct,
                valor=_money(ibc * pct / HUNDRED),
                descripcion=f"{pct}% sobre IBC {ibc}",
            )
        )

    fsp = _fsp_rate(ibc * THIRTY / dias_pagados, smmlv)
    if fsp is not None:
        resultado.lineas.append(
            Linea(
                concepto="FSP",
                valor_unitario=ibc,
                porcentaje=fsp,
                valor=_money(ibc * fsp / HUNDRED),
                descripcion=f"{fsp}% sobre IBC {ibc}",
            )
        )


def _deduccion_unica_aplicada(deduccion_id, nomina_id):
    query = (
        DetalleNomina.query.join(Nomina, Nomina.id == DetalleNomina.nomina_id)
        .filter(
            DetalleNomina.origen_tipo == "DEDUCCION_EMPLEADO",
            DetalleNomina.origen_id == deduccion_id,
            Nomina.estado != "ANULADA",
        )
    )
    if nomina_id is not None:
        query = query.filter(Nomina.id != nomina_id)
    return query.first() is not None


def _liquidar_deducciones(contrato, start, end, nomina_id, resultado):
    conceptos = {concepto.id: concepto for concepto in ConceptoNomina.query.all()}
    devengado = Decimal("0")
    deducido = Decimal("0")
    for linea in resultado.lineas:
        concepto = next(c for c in conceptos.values() if c.codigo == linea.concepto)
        if concepto.tipo == "DEVENGADO":
            devengado += linea.valor
        else:
            deducido += linea.valor
    disponible = devengado - deducido

    deducciones = DeduccionEmpleado.query.filter(
        DeduccionEmpleado.contrato_id == contrato.id,
        DeduccionEmpleado.activa.is_(True),
        DeduccionEmpleado.vigente_desde <= end,
        or_(DeduccionEmpleado.vigente_hasta.is_(None), DeduccionEmpleado.vigente_hasta >= start),
    ).all()
    deducciones.sort(
        key=lambda d: (ORDEN_DEDUCCIONES.get(conceptos[d.concepto_id].codigo, 9), d.id)
    )
    for deduccion in deducciones:
        concepto = conceptos[deduccion.concepto_id]
        if concepto.tipo != "DEDUCCION":
            continue
        if deduccion.periodicidad == "UNICA" and _deduccion_unica_aplicada(deduccion.id, nomina_id):
            continue
        cuota = _dec(deduccion.valor_cuota)
        if deduccion.saldo_pendiente is not None:
            cuota = min(cuota, _dec(deduccion.saldo_pendiente))
        if cuota <= 0:
            continue
        if cuota > disponible:
            resultado.notas.append(
                f"La deducción {deduccion.id} ({concepto.codigo}) se redujo de "
                f"{_money(cuota)} a {_money(max(disponible, Decimal('0')))} "
                "para no dejar el neto en negativo."
            )
            cuota = disponible
        if cuota <= 0:
            continue
        disponible -= cuota
        resultado.lineas.append(
            Linea(
                concepto=concepto.codigo,
                valor=_money(cuota),
                origen_tipo="DEDUCCION_EMPLEADO",
                origen_id=deduccion.id,
                descripcion=deduccion.descripcion or concepto.nombre,
            )
        )


def _quant(value, scale):
    return None if value is None else Decimal(value).quantize(scale, rounding=ROUND_HALF_UP)


def _guardar(nomina, contrato, periodo, liquidacion):
    conceptos = {concepto.codigo: concepto for concepto in ConceptoNomina.query.all()}
    for linea in liquidacion.lineas:
        concepto = conceptos.get(linea.concepto)
        if concepto is None or not concepto.activo:
            raise NominaConflictError(f"El concepto {linea.concepto} no está activo.")

    if nomina is None:
        nomina = Nomina(contrato_id=contrato.id, periodo_id=periodo.id)
        db.session.add(nomina)
    else:
        if nomina.estado == "ANULADA":
            nomina.estado = "BORRADOR"
            nomina.aprobada_por = None
            db.session.flush()
        DetalleNomina.query.filter_by(nomina_id=nomina.id).delete(synchronize_session=False)
    nomina.salario_referencia = liquidacion.salario_referencia
    nomina.observaciones = "\n".join(liquidacion.notas) or None
    nomina.fecha_liquidacion = datetime.now(timezone.utc)
    db.session.flush()

    for linea in liquidacion.lineas:
        db.session.add(
            DetalleNomina(
                nomina_id=nomina.id,
                concepto_id=conceptos[linea.concepto].id,
                cantidad=_quant(linea.cantidad, QTY),
                valor_unitario=_quant(linea.valor_unitario, RATE),
                porcentaje_aplicado=_quant(linea.porcentaje, RATE),
                valor=linea.valor,
                origen_tipo=linea.origen_tipo,
                origen_id=linea.origen_id,
                descripcion=linea.descripcion,
            )
        )
    for hora_extra, valor_hora, porcentaje, modo, valor in liquidacion.horas_extras:
        hora_extra.valor_hora_base = valor_hora
        hora_extra.porcentaje_aplicado = porcentaje
        hora_extra.modo_pago_aplicado = modo
        hora_extra.valor_calculado = valor
    db.session.flush()
    return nomina


def _parse_int(value, field, minimum=1, maximum=None):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise NominaValidationError(f"{field} debe ser un entero mayor o igual que {minimum}.")
    if maximum is not None and value > maximum:
        raise NominaValidationError(f"{field} debe estar entre {minimum} y {maximum}.")
    return value


def _parse_date(value, field):
    if not isinstance(value, str):
        raise NominaValidationError(f"{field} debe usar el formato YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise NominaValidationError(f"{field} debe usar el formato YYYY-MM-DD.") from error


def _parse_generar(data):
    if not isinstance(data, dict):
        raise NominaValidationError("El cuerpo debe ser un objeto JSON.")
    unknown = set(data) - GENERAR_FIELDS
    if unknown:
        raise NominaValidationError(f"Campos no permitidos: {', '.join(sorted(unknown))}.")

    if "fecha" in data:
        if {"anio", "mes", "quincena"} & set(data):
            raise NominaValidationError("Envíe fecha o anio, mes y quincena, no ambos.")
        fecha = _parse_date(data["fecha"], "fecha")
        anio, mes, quincena = fecha.year, fecha.month, 1 if fecha.day <= 15 else 2
    else:
        missing = {"anio", "mes", "quincena"} - set(data)
        if missing:
            raise NominaValidationError(
                "Indique la quincena con fecha o con anio, mes y quincena."
            )
        anio = _parse_int(data["anio"], "anio", 2000, 2100)
        mes = _parse_int(data["mes"], "mes", 1, 12)
        quincena = _parse_int(data["quincena"], "quincena", 1, 2)

    fecha_inicio, fecha_fin = quincena_bounds(anio, mes, quincena)
    fecha_pago = None
    if data.get("fecha_pago") is not None:
        fecha_pago = _parse_date(data["fecha_pago"], "fecha_pago")
        if fecha_pago < fecha_inicio:
            raise NominaValidationError("fecha_pago no puede ser anterior al inicio del periodo.")
    empleado_id = data.get("empleado_id")
    contrato_id = data.get("contrato_id")
    if empleado_id is not None:
        _parse_int(empleado_id, "empleado_id")
    if contrato_id is not None:
        _parse_int(contrato_id, "contrato_id")
    return fecha_inicio, fecha_fin, fecha_pago, empleado_id, contrato_id


def _periodo(empresa_id, fecha_inicio, fecha_fin, fecha_pago):
    periodo = PeriodoNomina.query.filter_by(
        empresa_id=empresa_id,
        tipo="QUINCENAL",
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    ).first()
    if periodo is None:
        periodo = PeriodoNomina(
            empresa_id=empresa_id,
            tipo="QUINCENAL",
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            fecha_pago=fecha_pago or fecha_fin,
            estado="ABIERTO",
        )
        db.session.add(periodo)
        db.session.flush()
        return periodo
    if periodo.estado == "CERRADO":
        raise NominaConflictError("El periodo está cerrado; no se puede volver a liquidar.")
    if fecha_pago is not None:
        periodo.fecha_pago = fecha_pago
    return periodo


def _contratos_del_periodo(empresa_id, periodo, empleado_id=None, contrato_id=None):
    query = (
        Contrato.query.join(Empleado, Empleado.id == Contrato.empleado_id)
        .filter(
            Empleado.empresa_id == empresa_id,
            Contrato.fecha_inicio <= periodo.fecha_fin,
            or_(Contrato.fecha_fin.is_(None), Contrato.fecha_fin >= periodo.fecha_inicio),
            or_(Contrato.estado == "ACTIVO", Contrato.fecha_fin.is_not(None)),
        )
    )
    if empleado_id is not None:
        if Empleado.query.filter_by(id=empleado_id, empresa_id=empresa_id).first() is None:
            raise NominaNotFoundError("Empleado no encontrado.")
        query = query.filter(Contrato.empleado_id == empleado_id)
    if contrato_id is not None:
        exists = (
            Contrato.query.join(Empleado, Empleado.id == Contrato.empleado_id)
            .filter(Contrato.id == contrato_id, Empleado.empresa_id == empresa_id)
            .first()
        )
        if exists is None:
            raise NominaNotFoundError("Contrato no encontrado.")
        query = query.filter(Contrato.id == contrato_id)
    contratos = query.order_by(Contrato.id).all()
    if not contratos and (empleado_id is not None or contrato_id is not None):
        raise NominaConflictError("El empleado no tiene un contrato vigente en la quincena.")
    return contratos


def generate_payroll(current_user, data):
    empresa_id = _empresa_id_for_user(current_user)
    fecha_inicio, fecha_fin, fecha_pago, empleado_id, contrato_id = _parse_generar(data)
    try:
        periodo = _periodo(empresa_id, fecha_inicio, fecha_fin, fecha_pago)
        contratos = _contratos_del_periodo(empresa_id, periodo, empleado_id, contrato_id)

        generadas = []
        omitidas = []
        errores = []
        for contrato in contratos:
            nomina = Nomina.query.filter_by(contrato_id=contrato.id, periodo_id=periodo.id).first()
            if nomina is not None and nomina.estado in {"APROBADA", "PAGADA"}:
                omitidas.append(
                    {
                        "contrato_id": contrato.id,
                        "empleado_id": contrato.empleado_id,
                        "nomina_id": nomina.id,
                        "motivo": f"La nómina ya está {nomina.estado}.",
                    }
                )
                continue
            try:
                liquidacion = _liquidar(
                    contrato,
                    periodo,
                    empresa_id,
                    nomina.id if nomina is not None else None,
                )
            except NominaConflictError as error:
                errores.append(
                    {
                        "contrato_id": contrato.id,
                        "empleado_id": contrato.empleado_id,
                        "error": str(error),
                    }
                )
                continue
            generadas.append(_guardar(nomina, contrato, periodo, liquidacion))
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise NominaConflictError("No se pudo guardar la liquidación.") from error
    except Exception:
        db.session.rollback()
        raise

    return {
        "periodo": _serialize_periodo(periodo),
        "nominas": [_serialize_nomina(nomina, detalles=True) for nomina in generadas],
        "omitidas": omitidas,
        "errores": errores,
    }


def _serialize_periodo(periodo, resumen=False):
    data = {
        "id": periodo.id,
        "tipo": periodo.tipo,
        "fecha_inicio": periodo.fecha_inicio.isoformat(),
        "fecha_fin": periodo.fecha_fin.isoformat(),
        "fecha_pago": periodo.fecha_pago.isoformat(),
        "estado": periodo.estado,
    }
    if resumen:
        nominas = Nomina.query.filter_by(periodo_id=periodo.id).all()
        vigentes = [nomina for nomina in nominas if nomina.estado != "ANULADA"]
        por_estado = defaultdict(int)
        for nomina in nominas:
            por_estado[nomina.estado] += 1
        data["resumen"] = {
            "nominas": len(nominas),
            "por_estado": dict(por_estado),
            "total_devengado": _json_money(sum((_dec(n.total_devengado) for n in vigentes), Decimal("0"))),
            "total_deducciones": _json_money(
                sum((_dec(n.total_deducciones) for n in vigentes), Decimal("0"))
            ),
            "neto_pagar": _json_money(sum((_dec(n.neto_pagar) for n in vigentes), Decimal("0"))),
        }
    return data


def _json_money(value):
    return None if value is None else float(_dec(value).quantize(MONEY))


def _json_dec(value, scale):
    return None if value is None else float(_dec(value).quantize(scale))


def _serialize_nomina(nomina, detalles=False):
    contrato = db.session.get(Contrato, nomina.contrato_id)
    empleado = db.session.get(Empleado, contrato.empleado_id)
    periodo = db.session.get(PeriodoNomina, nomina.periodo_id)
    data = {
        "id": nomina.id,
        "contrato_id": nomina.contrato_id,
        "empleado": {
            "id": empleado.id,
            "tipo_documento": empleado.tipo_documento,
            "numero_documento": empleado.numero_documento,
            "nombres": empleado.nombres,
            "apellidos": empleado.apellidos,
        },
        "periodo": _serialize_periodo(periodo),
        "salario_referencia": _json_money(nomina.salario_referencia),
        "total_devengado": _json_money(nomina.total_devengado),
        "total_deducciones": _json_money(nomina.total_deducciones),
        "neto_pagar": _json_money(nomina.neto_pagar),
        "estado": nomina.estado,
        "fecha_liquidacion": (
            nomina.fecha_liquidacion.isoformat() if nomina.fecha_liquidacion else None
        ),
        "aprobada_por": nomina.aprobada_por,
        "observaciones": nomina.observaciones,
    }
    if detalles:
        rows = (
            db.session.query(DetalleNomina, ConceptoNomina)
            .join(ConceptoNomina, ConceptoNomina.id == DetalleNomina.concepto_id)
            .filter(DetalleNomina.nomina_id == nomina.id)
            .order_by(ConceptoNomina.tipo.desc(), DetalleNomina.id)
            .all()
        )
        data["detalles"] = [
            {
                "id": detalle.id,
                "concepto": concepto.codigo,
                "nombre": concepto.nombre,
                "tipo": concepto.tipo,
                "cantidad": _json_dec(detalle.cantidad, QTY),
                "valor_unitario": _json_dec(detalle.valor_unitario, RATE),
                "porcentaje_aplicado": _json_dec(detalle.porcentaje_aplicado, RATE),
                "valor": _json_money(detalle.valor),
                "origen_tipo": detalle.origen_tipo,
                "origen_id": detalle.origen_id,
                "descripcion": detalle.descripcion,
            }
            for detalle, concepto in rows
        ]
        pagos = PagoNomina.query.filter_by(nomina_id=nomina.id).order_by(PagoNomina.id).all()
        data["pagos"] = [
            {
                "id": pago.id,
                "fecha_pago": pago.fecha_pago.isoformat(),
                "valor": _json_money(pago.valor),
                "medio": pago.medio,
                "referencia": pago.referencia,
                "observaciones": pago.observaciones,
            }
            for pago in pagos
        ]
    return data


def _scoped_nominas(empresa_id):
    return (
        Nomina.query.join(Contrato, Contrato.id == Nomina.contrato_id)
        .join(Empleado, Empleado.id == Contrato.empleado_id)
        .filter(Empleado.empresa_id == empresa_id)
    )


def _find_nomina(empresa_id, nomina_id):
    nomina = _scoped_nominas(empresa_id).filter(Nomina.id == nomina_id).first()
    if nomina is None:
        raise NominaNotFoundError("Nómina no encontrada.")
    return nomina


def _find_periodo(empresa_id, periodo_id):
    periodo = PeriodoNomina.query.filter_by(id=periodo_id, empresa_id=empresa_id).first()
    if periodo is None:
        raise NominaNotFoundError("Periodo no encontrado.")
    return periodo


def _parse_query_int(value, field):
    if value is None:
        return None
    if not value.isdigit() or int(value) < 1:
        raise NominaValidationError(f"{field} debe ser un entero positivo.")
    return int(value)


def _validate_page(page, per_page):
    if page < 1:
        raise NominaValidationError("page debe ser mayor que cero.")
    if per_page < 1 or per_page > 100:
        raise NominaValidationError("per_page debe estar entre 1 y 100.")


def _paginated(pagination, serializer):
    return {
        "items": [serializer(item) for item in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        },
    }


def list_payrolls(current_user, page=1, per_page=20, periodo_id=None, contrato_id=None,
                  empleado_id=None, estado=None):
    empresa_id = _empresa_id_for_user(current_user)
    _validate_page(page, per_page)
    if estado is not None and estado not in ESTADOS:
        raise NominaValidationError(f"estado debe ser uno de: {', '.join(sorted(ESTADOS))}.")
    query = _scoped_nominas(empresa_id)
    for value, field, column in (
        (periodo_id, "periodo_id", Nomina.periodo_id),
        (contrato_id, "contrato_id", Nomina.contrato_id),
        (empleado_id, "empleado_id", Contrato.empleado_id),
    ):
        parsed = _parse_query_int(value, field)
        if parsed is not None:
            query = query.filter(column == parsed)
    if estado is not None:
        query = query.filter(Nomina.estado == estado)
    pagination = query.order_by(Nomina.periodo_id.desc(), Nomina.id).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return _paginated(pagination, _serialize_nomina)


def get_payroll(current_user, nomina_id):
    empresa_id = _empresa_id_for_user(current_user)
    return _serialize_nomina(_find_nomina(empresa_id, nomina_id), detalles=True)


def receipt_data(current_user, nomina_id):
    empresa_id = _empresa_id_for_user(current_user)
    nomina = _find_nomina(empresa_id, nomina_id)
    empresa = db.session.get(Empresa, empresa_id)
    contrato = db.session.get(Contrato, nomina.contrato_id)
    return {
        "empresa": {
            "nit": empresa.nit,
            "razon_social": empresa.razon_social,
            "direccion": empresa.direccion,
            "telefono": empresa.telefono,
            "correo": empresa.correo,
        },
        "contrato": {
            "cargo": contrato.cargo,
            "tipo_contrato": contrato.tipo_contrato,
        },
        "nomina": _serialize_nomina(nomina, detalles=True),
    }


def report_data(current_user, periodo_id=None, estado=None, desde=None, hasta=None):
    """Reúne las nóminas de la empresa para el reporte general (sin paginar)."""
    empresa_id = _empresa_id_for_user(current_user)
    empresa = db.session.get(Empresa, empresa_id)

    if estado is not None and estado not in ESTADOS:
        raise NominaValidationError(f"estado debe ser uno de: {', '.join(sorted(ESTADOS))}.")

    query = _scoped_nominas(empresa_id).join(
        PeriodoNomina, PeriodoNomina.id == Nomina.periodo_id
    )
    periodo_parsed = _parse_query_int(periodo_id, "periodo_id")
    if periodo_parsed is not None:
        query = query.filter(Nomina.periodo_id == periodo_parsed)
    if estado is not None:
        query = query.filter(Nomina.estado == estado)

    desde_date = _parse_date(desde, "desde") if desde is not None else None
    hasta_date = _parse_date(hasta, "hasta") if hasta is not None else None
    if desde_date is not None:
        query = query.filter(PeriodoNomina.fecha_fin >= desde_date)
    if hasta_date is not None:
        query = query.filter(PeriodoNomina.fecha_inicio <= hasta_date)

    nominas = query.order_by(Nomina.periodo_id.desc(), Nomina.id).all()
    items = [_serialize_nomina(nomina) for nomina in nominas]

    vigentes = [nomina for nomina in nominas if nomina.estado != "ANULADA"]
    por_estado = defaultdict(int)
    for nomina in nominas:
        por_estado[nomina.estado] += 1

    return {
        "empresa": {
            "nit": empresa.nit,
            "razon_social": empresa.razon_social,
            "direccion": empresa.direccion,
            "telefono": empresa.telefono,
            "correo": empresa.correo,
        },
        "filtros": {
            "periodo_id": periodo_parsed,
            "estado": estado,
            "desde": desde_date.isoformat() if desde_date else None,
            "hasta": hasta_date.isoformat() if hasta_date else None,
        },
        "nominas": items,
        "resumen": {
            "nominas": len(nominas),
            "por_estado": dict(por_estado),
            "total_devengado": _json_money(
                sum((_dec(n.total_devengado) for n in vigentes), Decimal("0"))
            ),
            "total_deducciones": _json_money(
                sum((_dec(n.total_deducciones) for n in vigentes), Decimal("0"))
            ),
            "neto_pagar": _json_money(
                sum((_dec(n.neto_pagar) for n in vigentes), Decimal("0"))
            ),
        },
    }


def _detalles_origen(nomina, origen_tipo):
    return DetalleNomina.query.filter_by(nomina_id=nomina.id, origen_tipo=origen_tipo).all()


def _check_approval(nomina):
    if nomina.estado != "BORRADOR":
        raise NominaConflictError(f"Solo se aprueba una nómina en BORRADOR; está {nomina.estado}.")
    periodo = db.session.get(PeriodoNomina, nomina.periodo_id)
    if periodo.estado == "CERRADO":
        raise NominaConflictError("El periodo está cerrado.")
    for detalle in _detalles_origen(nomina, "HORA_EXTRA"):
        hora_extra = db.session.get(HoraExtra, detalle.origen_id)
        if hora_extra is None or hora_extra.estado != "APROBADA":
            raise NominaConflictError(
                "Las horas extras cambiaron después de liquidar; vuelva a generar la nómina."
            )
    for detalle in _detalles_origen(nomina, "DEDUCCION_EMPLEADO"):
        deduccion = db.session.get(DeduccionEmpleado, detalle.origen_id)
        if deduccion is None or not deduccion.activa:
            raise NominaConflictError(
                "Las deducciones cambiaron después de liquidar; vuelva a generar la nómina."
            )
        if deduccion.saldo_pendiente is not None and _dec(deduccion.saldo_pendiente) < _dec(detalle.valor):
            raise NominaConflictError(
                "El saldo de una deducción es menor que la cuota liquidada; "
                "vuelva a generar la nómina."
            )


def _apply_approval(nomina, current_user):
    for detalle in _detalles_origen(nomina, "HORA_EXTRA"):
        db.session.get(HoraExtra, detalle.origen_id).estado = "LIQUIDADA"
    for detalle in _detalles_origen(nomina, "DEDUCCION_EMPLEADO"):
        deduccion = db.session.get(DeduccionEmpleado, detalle.origen_id)
        if deduccion.saldo_pendiente is not None:
            deduccion.saldo_pendiente = _dec(deduccion.saldo_pendiente) - _dec(detalle.valor)
            if deduccion.saldo_pendiente <= 0:
                deduccion.activa = False
        if deduccion.periodicidad == "UNICA":
            deduccion.activa = False
    nomina.estado = "APROBADA"
    nomina.aprobada_por = current_user.id


def approve_payroll(current_user, nomina_id):
    empresa_id = _empresa_id_for_user(current_user)
    nomina = _find_nomina(empresa_id, nomina_id)
    _check_approval(nomina)
    _apply_approval(nomina, current_user)
    db.session.commit()
    return _serialize_nomina(nomina, detalles=True)


def annul_payroll(current_user, nomina_id):
    empresa_id = _empresa_id_for_user(current_user)
    nomina = _find_nomina(empresa_id, nomina_id)
    if nomina.estado == "PAGADA":
        raise NominaConflictError("Una nómina pagada no se puede anular.")
    if nomina.estado == "ANULADA":
        raise NominaConflictError("La nómina ya está anulada.")
    periodo = db.session.get(PeriodoNomina, nomina.periodo_id)
    if periodo.estado == "CERRADO":
        raise NominaConflictError("El periodo está cerrado.")

    if nomina.estado == "APROBADA":
        for detalle in _detalles_origen(nomina, "HORA_EXTRA"):
            hora_extra = db.session.get(HoraExtra, detalle.origen_id)
            if hora_extra is not None and hora_extra.estado == "LIQUIDADA":
                hora_extra.estado = "APROBADA"
        for detalle in _detalles_origen(nomina, "DEDUCCION_EMPLEADO"):
            deduccion = db.session.get(DeduccionEmpleado, detalle.origen_id)
            if deduccion is None:
                continue
            if deduccion.saldo_pendiente is not None:
                deduccion.saldo_pendiente = _dec(deduccion.saldo_pendiente) + _dec(detalle.valor)
            deduccion.activa = True
    nomina.estado = "ANULADA"
    nomina.aprobada_por = None
    db.session.commit()
    return _serialize_nomina(nomina, detalles=True)


def pay_payroll(current_user, nomina_id, data):
    empresa_id = _empresa_id_for_user(current_user)
    nomina = _find_nomina(empresa_id, nomina_id)
    data = data if data is not None else {}
    if not isinstance(data, dict):
        raise NominaValidationError("El cuerpo debe ser un objeto JSON.")
    unknown = set(data) - PAGO_FIELDS
    if unknown:
        raise NominaValidationError(f"Campos no permitidos: {', '.join(sorted(unknown))}.")
    if nomina.estado != "APROBADA":
        raise NominaConflictError(f"Solo se paga una nómina APROBADA; está {nomina.estado}.")
    neto = _dec(nomina.neto_pagar)
    if neto <= 0:
        raise NominaConflictError("El neto a pagar es cero.")

    periodo = db.session.get(PeriodoNomina, nomina.periodo_id)
    fecha_pago = (
        _parse_date(data["fecha_pago"], "fecha_pago")
        if data.get("fecha_pago") is not None
        else periodo.fecha_pago
    )
    medio = data.get("medio") or "TRANSFERENCIA"
    if medio not in MEDIOS_PAGO:
        raise NominaValidationError(f"medio debe ser uno de: {', '.join(sorted(MEDIOS_PAGO))}.")
    referencia = data.get("referencia")
    if referencia is not None and (not isinstance(referencia, str) or len(referencia) > 100):
        raise NominaValidationError("referencia debe ser texto de hasta 100 caracteres.")
    observaciones = data.get("observaciones")
    if observaciones is not None and not isinstance(observaciones, str):
        raise NominaValidationError("observaciones debe ser texto.")

    db.session.add(
        PagoNomina(
            nomina_id=nomina.id,
            fecha_pago=fecha_pago,
            valor=neto,
            medio=medio,
            referencia=referencia,
            observaciones=observaciones,
        )
    )
    nomina.estado = "PAGADA"
    db.session.commit()
    return _serialize_nomina(nomina, detalles=True)


def list_periods(current_user, page=1, per_page=20, estado=None):
    empresa_id = _empresa_id_for_user(current_user)
    _validate_page(page, per_page)
    query = PeriodoNomina.query.filter_by(empresa_id=empresa_id)
    if estado is not None:
        if estado not in {"ABIERTO", "EN_REVISION", "CERRADO"}:
            raise NominaValidationError("estado debe ser ABIERTO, EN_REVISION o CERRADO.")
        query = query.filter_by(estado=estado)
    pagination = query.order_by(PeriodoNomina.fecha_inicio.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return _paginated(pagination, lambda periodo: _serialize_periodo(periodo, resumen=True))


def get_period(current_user, periodo_id):
    empresa_id = _empresa_id_for_user(current_user)
    return _serialize_periodo(_find_periodo(empresa_id, periodo_id), resumen=True)


def approve_period(current_user, periodo_id):
    empresa_id = _empresa_id_for_user(current_user)
    periodo = _find_periodo(empresa_id, periodo_id)
    if periodo.estado == "CERRADO":
        raise NominaConflictError("El periodo está cerrado.")
    aprobadas = []
    errores = []
    for nomina in Nomina.query.filter_by(periodo_id=periodo.id, estado="BORRADOR").order_by(Nomina.id):
        try:
            _check_approval(nomina)
        except NominaConflictError as error:
            errores.append({"nomina_id": nomina.id, "error": str(error)})
            continue
        _apply_approval(nomina, current_user)
        aprobadas.append(nomina.id)
    db.session.commit()
    return {
        "periodo": _serialize_periodo(periodo, resumen=True),
        "aprobadas": aprobadas,
        "errores": errores,
    }


def close_period(current_user, periodo_id):
    empresa_id = _empresa_id_for_user(current_user)
    periodo = _find_periodo(empresa_id, periodo_id)
    if periodo.estado == "CERRADO":
        raise NominaConflictError("El periodo ya está cerrado.")
    pendientes = Nomina.query.filter_by(periodo_id=periodo.id, estado="BORRADOR").count()
    if pendientes:
        raise NominaConflictError(
            f"Hay {pendientes} nóminas en BORRADOR; apruébelas o anúlelas antes de cerrar."
        )
    periodo.estado = "CERRADO"
    db.session.commit()
    return _serialize_periodo(periodo, resumen=True)
