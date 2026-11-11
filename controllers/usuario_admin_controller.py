from flask import jsonify, request

from services.usuario_admin_service import (
    UsuarioAdminConflictError,
    UsuarioAdminForbiddenError,
    UsuarioAdminNotFoundError,
    UsuarioAdminValidationError,
    create_user,
    get_user,
    list_users,
    update_user_companies,
    update_user_status,
)


def _error_response(error):
    if isinstance(error, UsuarioAdminValidationError):
        status_code = 400
    elif isinstance(error, UsuarioAdminForbiddenError):
        status_code = 403
    elif isinstance(error, UsuarioAdminNotFoundError):
        status_code = 404
    elif isinstance(error, UsuarioAdminConflictError):
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
        result = list_users(current_user, page=page, per_page=per_page)
    except UsuarioAdminValidationError as error:
        return _error_response(error)
    return jsonify(result)


def create(current_user):
    try:
        usuario = create_user(current_user, request.get_json(silent=True))
    except (
        UsuarioAdminConflictError,
        UsuarioAdminForbiddenError,
        UsuarioAdminValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(
        {"message": "Usuario creado correctamente.", "usuario": usuario}
    ), 201


def show(current_user, usuario_id):
    try:
        usuario = get_user(current_user, usuario_id)
    except UsuarioAdminNotFoundError as error:
        return _error_response(error)
    return jsonify({"usuario": usuario})


def update_status(current_user, usuario_id):
    try:
        usuario = update_user_status(
            current_user,
            usuario_id,
            request.get_json(silent=True),
        )
    except (
        UsuarioAdminNotFoundError,
        UsuarioAdminValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(
        {"message": "Usuario actualizado correctamente.", "usuario": usuario}
    )


def update_companies(current_user, usuario_id):
    try:
        usuario = update_user_companies(
            current_user,
            usuario_id,
            request.get_json(silent=True),
        )
    except (
        UsuarioAdminConflictError,
        UsuarioAdminForbiddenError,
        UsuarioAdminNotFoundError,
        UsuarioAdminValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(
        {
            "message": "Empresas del usuario actualizadas correctamente.",
            "usuario": usuario,
        }
    )
