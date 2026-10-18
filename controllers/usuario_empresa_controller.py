from flask import jsonify, request

from services.usuario_empresa_service import (
    UsuarioEmpresaConflictError,
    UsuarioEmpresaNotFoundError,
    UsuarioEmpresaValidationError,
    create_user_company,
    delete_user_company,
    get_user_company,
    update_user_company,
)


def _error_response(error):
    if isinstance(error, UsuarioEmpresaValidationError):
        status_code = 400
    elif isinstance(error, UsuarioEmpresaNotFoundError):
        status_code = 404
    elif isinstance(error, UsuarioEmpresaConflictError):
        status_code = 409
    else:
        raise error
    return jsonify({"error": str(error)}), status_code


def show(usuario_id):
    try:
        association = get_user_company(usuario_id)
    except UsuarioEmpresaNotFoundError as error:
        return _error_response(error)
    return jsonify(association)


def _read_empresa_id():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "El cuerpo debe ser un objeto JSON."}), 400)
    if set(data) != {"empresa_id"}:
        return None, (
            jsonify({"error": "El cuerpo debe contener únicamente empresa_id."}),
            400,
        )
    return data["empresa_id"], None


def create(usuario_id):
    empresa_id, error_response = _read_empresa_id()
    if error_response:
        return error_response
    try:
        association = create_user_company(usuario_id, empresa_id)
    except (
        UsuarioEmpresaConflictError,
        UsuarioEmpresaNotFoundError,
        UsuarioEmpresaValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(
        {
            "message": "Empresa asociada al usuario correctamente.",
            **association,
        }
    ), 201


def update(usuario_id):
    empresa_id, error_response = _read_empresa_id()
    if error_response:
        return error_response
    try:
        association = update_user_company(usuario_id, empresa_id)
    except (
        UsuarioEmpresaConflictError,
        UsuarioEmpresaNotFoundError,
        UsuarioEmpresaValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(
        {
            "message": "Empresa del usuario actualizada correctamente.",
            **association,
        }
    )


def delete(usuario_id):
    try:
        association = delete_user_company(usuario_id)
    except UsuarioEmpresaNotFoundError as error:
        return _error_response(error)
    return jsonify(
        {
            "message": "Asociación usuario-empresa eliminada correctamente.",
            **association,
        }
    )
