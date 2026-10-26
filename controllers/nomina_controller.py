from flask import jsonify, request, send_file

from services.recibo_nomina_service import build_receipt
from services.nomina_service import (
    NominaConflictError,
    NominaForbiddenError,
    NominaNotFoundError,
    NominaValidationError,
    annul_payroll,
    approve_payroll,
    approve_period,
    close_period,
    generate_payroll,
    get_payroll,
    get_period,
    list_payrolls,
    list_periods,
    pay_payroll,
)


ERRORS = (
    NominaConflictError,
    NominaForbiddenError,
    NominaNotFoundError,
    NominaValidationError,
)


def _error_response(error):
    if isinstance(error, NominaValidationError):
        status_code = 400
    elif isinstance(error, NominaForbiddenError):
        status_code = 403
    elif isinstance(error, NominaNotFoundError):
        status_code = 404
    elif isinstance(error, NominaConflictError):
        status_code = 409
    else:
        raise error
    return jsonify({"error": str(error)}), status_code


def _page_args():
    try:
        return int(request.args.get("page", "1")), int(request.args.get("per_page", "20"))
    except ValueError:
        return None


def generate(current_user):
    try:
        result = generate_payroll(current_user, request.get_json(silent=True))
    except ERRORS as error:
        return _error_response(error)
    generated = len(result["nominas"])
    result["message"] = f"Se liquidaron {generated} nóminas."
    return jsonify(result), 201 if generated else 200


def index(current_user):
    pages = _page_args()
    if pages is None:
        return jsonify({"error": "page y per_page deben ser números enteros."}), 400
    try:
        result = list_payrolls(
            current_user,
            page=pages[0],
            per_page=pages[1],
            periodo_id=request.args.get("periodo_id"),
            contrato_id=request.args.get("contrato_id"),
            empleado_id=request.args.get("empleado_id"),
            estado=request.args.get("estado"),
        )
    except ERRORS as error:
        return _error_response(error)
    return jsonify(result)


def show(current_user, nomina_id):
    try:
        nomina = get_payroll(current_user, nomina_id)
    except ERRORS as error:
        return _error_response(error)
    return jsonify({"nomina": nomina})


def receipt(current_user, nomina_id):
    try:
        buffer, download_name = build_receipt(current_user, nomina_id)
    except ERRORS as error:
        return _error_response(error)
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=request.args.get("inline") != "1",
        download_name=download_name,
    )


def approve(current_user, nomina_id):
    try:
        nomina = approve_payroll(current_user, nomina_id)
    except ERRORS as error:
        return _error_response(error)
    return jsonify({"message": "Nómina aprobada correctamente.", "nomina": nomina})


def annul(current_user, nomina_id):
    try:
        nomina = annul_payroll(current_user, nomina_id)
    except ERRORS as error:
        return _error_response(error)
    return jsonify({"message": "Nómina anulada correctamente.", "nomina": nomina})


def pay(current_user, nomina_id):
    try:
        nomina = pay_payroll(current_user, nomina_id, request.get_json(silent=True))
    except ERRORS as error:
        return _error_response(error)
    return jsonify({"message": "Pago registrado correctamente.", "nomina": nomina})


def periods_index(current_user):
    pages = _page_args()
    if pages is None:
        return jsonify({"error": "page y per_page deben ser números enteros."}), 400
    try:
        result = list_periods(
            current_user,
            page=pages[0],
            per_page=pages[1],
            estado=request.args.get("estado"),
        )
    except ERRORS as error:
        return _error_response(error)
    return jsonify(result)


def periods_show(current_user, periodo_id):
    try:
        periodo = get_period(current_user, periodo_id)
    except ERRORS as error:
        return _error_response(error)
    return jsonify({"periodo": periodo})


def periods_approve(current_user, periodo_id):
    try:
        result = approve_period(current_user, periodo_id)
    except ERRORS as error:
        return _error_response(error)
    result["message"] = f"Se aprobaron {len(result['aprobadas'])} nóminas."
    return jsonify(result)


def periods_close(current_user, periodo_id):
    try:
        periodo = close_period(current_user, periodo_id)
    except ERRORS as error:
        return _error_response(error)
    return jsonify({"message": "Periodo cerrado correctamente.", "periodo": periodo})
