from flask import jsonify, request

from services.empresa_service import (
    EmpresaConflictError,
    EmpresaNotFoundError,
    EmpresaValidationError,
    create_company,
    delete_company,
    get_company,
    list_companies,
    update_company,
)


def _error_response(error):
    if isinstance(error, EmpresaValidationError):
        status_code = 400
    elif isinstance(error, EmpresaNotFoundError):
        status_code = 404
    elif isinstance(error, EmpresaConflictError):
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
        result = list_companies(
            current_user,
            page=page,
            per_page=per_page,
            activa=request.args.get("activa"),
        )
    except EmpresaValidationError as error:
        return _error_response(error)
    return jsonify(result)


def show(current_user, empresa_id):
    try:
        empresa = get_company(current_user, empresa_id)
    except EmpresaNotFoundError as error:
        return _error_response(error)
    return jsonify({"empresa": empresa})


def create(current_user):
    try:
        empresa = create_company(current_user, request.get_json(silent=True))
    except (EmpresaConflictError, EmpresaValidationError) as error:
        return _error_response(error)
    return jsonify({"message": "Empresa creada correctamente.", "empresa": empresa}), 201


def update(current_user, empresa_id):
    try:
        empresa = update_company(
            current_user,
            empresa_id,
            request.get_json(silent=True),
            replace=request.method == "PUT",
        )
    except (
        EmpresaConflictError,
        EmpresaNotFoundError,
        EmpresaValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(
        {"message": "Empresa actualizada correctamente.", "empresa": empresa}
    )


def delete(current_user, empresa_id):
    try:
        empresa = delete_company(current_user, empresa_id)
    except EmpresaNotFoundError as error:
        return _error_response(error)
    return jsonify(
        {"message": "Empresa desactivada correctamente.", "empresa": empresa}
    )
