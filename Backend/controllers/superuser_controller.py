from flask import jsonify, request

from services.superuser_service import (
    SuperuserConflictError,
    SuperuserNotFoundError,
    SuperuserValidationError,
    get_company,
    list_companies,
    list_users,
    resumen,
    update_user_status,
)


def _error_response(error):
    if isinstance(error, SuperuserValidationError):
        status_code = 400
    elif isinstance(error, SuperuserNotFoundError):
        status_code = 404
    elif isinstance(error, SuperuserConflictError):
        status_code = 409
    else:
        raise error
    return jsonify({"error": str(error)}), status_code


def summary(current_user):
    del current_user
    return jsonify(resumen())


def companies(current_user):
    del current_user
    try:
        page = int(request.args.get("page", "1"))
        per_page = int(request.args.get("per_page", "20"))
    except ValueError:
        return jsonify({"error": "page y per_page deben ser números enteros."}), 400
    try:
        result = list_companies(
            page=page,
            per_page=per_page,
            activa=request.args.get("activa"),
        )
    except SuperuserValidationError as error:
        return _error_response(error)
    return jsonify(result)


def company(current_user, empresa_id):
    del current_user
    try:
        empresa = get_company(empresa_id)
    except SuperuserNotFoundError as error:
        return _error_response(error)
    return jsonify({"empresa": empresa})


def users(current_user):
    del current_user
    try:
        page = int(request.args.get("page", "1"))
        per_page = int(request.args.get("per_page", "20"))
    except ValueError:
        return jsonify({"error": "page y per_page deben ser números enteros."}), 400
    try:
        result = list_users(page=page, per_page=per_page)
    except SuperuserValidationError as error:
        return _error_response(error)
    return jsonify(result)


def user_status(current_user, usuario_id):
    try:
        usuario = update_user_status(
            current_user,
            usuario_id,
            request.get_json(silent=True),
        )
    except (
        SuperuserConflictError,
        SuperuserNotFoundError,
        SuperuserValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(
        {"message": "Usuario actualizado correctamente.", "usuario": usuario}
    )
