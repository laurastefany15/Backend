from flask import current_app, jsonify, request

from services.auth_service import (
    AuthValidationError,
    EmailAlreadyRegisteredError,
    authenticate_user,
    register_user,
)


def register():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "El cuerpo debe ser un objeto JSON."}), 400

    try:
        user = register_user(data.get("correo"), data.get("password"))
    except AuthValidationError as error:
        return jsonify({"error": str(error)}), 400
    except EmailAlreadyRegisteredError as error:
        return jsonify({"error": str(error)}), 409

    return (
        jsonify(
            {
                "message": "Usuario registrado correctamente.",
                "user": {"id": user.id, "correo": user.correo},
            }
        ),
        201,
    )


def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "El cuerpo debe ser un objeto JSON."}), 400

    correo = data.get("correo")
    password = data.get("password")
    if not isinstance(correo, str) or not isinstance(password, str):
        return jsonify({"error": "Correo y contraseña son obligatorios."}), 400

    user, token = authenticate_user(correo, password)
    if user is None or token is None:
        return jsonify({"error": "Credenciales inválidas."}), 401

    return jsonify(
        {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": current_app.config["JWT_ACCESS_TOKEN_EXPIRES"],
            "user": {"id": user.id, "correo": user.correo},
        }
    )
