from flask import jsonify, request

from services.contrato_service import (
    ContratoConflictError,
    ContratoForbiddenError,
    ContratoNotFoundError,
    ContratoValidationError,
    create_contract,
    delete_contract,
    get_contract,
    list_contracts,
    update_contract,
)


def _error_response(error):
    if isinstance(error, ContratoValidationError):
        status_code = 400
    elif isinstance(error, ContratoForbiddenError):
        status_code = 403
    elif isinstance(error, ContratoNotFoundError):
        status_code = 404
    elif isinstance(error, ContratoConflictError):
        status_code = 409
    else:
        raise error
    return jsonify({"error": str(error)}), status_code


def index(current_user):
    try:
        page = int(request.args.get("page", "1"))
        per_page = int(request.args.get("per_page", "20"))
    except ValueError:
        return jsonify({"error": "page y per_page deben ser números enteros."}), 400

    try:
        result = list_contracts(
            current_user,
            page=page,
            per_page=per_page,
            empleado_id=request.args.get("empleado_id"),
            estado=request.args.get("estado"),
        )
    except (
        ContratoForbiddenError,
        ContratoNotFoundError,
        ContratoValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(result)


def show(current_user, contrato_id):
    try:
        contrato = get_contract(current_user, contrato_id)
    except (ContratoForbiddenError, ContratoNotFoundError) as error:
        return _error_response(error)
    return jsonify({"contrato": contrato})


def create(current_user):
    try:
        contrato = create_contract(current_user, request.get_json(silent=True))
    except (
        ContratoConflictError,
        ContratoForbiddenError,
        ContratoNotFoundError,
        ContratoValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(
        {"message": "Contrato creado correctamente.", "contrato": contrato}
    ), 201


def update(current_user, contrato_id):
    try:
        contrato = update_contract(
            current_user,
            contrato_id,
            request.get_json(silent=True),
            replace=request.method == "PUT",
        )
    except (
        ContratoConflictError,
        ContratoForbiddenError,
        ContratoNotFoundError,
        ContratoValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(
        {"message": "Contrato actualizado correctamente.", "contrato": contrato}
    )


def delete(current_user, contrato_id):
    try:
        contrato = delete_contract(current_user, contrato_id)
    except (ContratoForbiddenError, ContratoNotFoundError) as error:
        return _error_response(error)
    return jsonify(
        {"message": "Contrato terminado correctamente.", "contrato": contrato}
    )
