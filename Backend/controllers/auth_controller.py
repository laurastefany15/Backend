from flask import current_app, jsonify, request

from services.acceso_service import perfil_publico
from services.auth_service import (
    AuthValidationError,
    EmailDeliveryError,
    EmailAlreadyRegisteredError,
    EmailNotVerifiedError,
    authenticate_user,
    register_user,
    resend_verification_email,
    verify_email_token,
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
    except EmailDeliveryError:
        current_app.logger.exception("No se pudo enviar el correo de verificación.")
        return jsonify(
            {
                "error": (
                    "La cuenta quedó creada, pero no se pudo enviar el correo. "
                    "Solicita otro enlace en /auth/resend-verification."
                )
            }
        ), 503

    return (
        jsonify(
            {
                "message": (
                    "Cuenta creada. Revisa tu correo para completar "
                    "la verificación."
                ),
                "user": perfil_publico(user),
            }
        ),
        201,
    )


def verify_email():
    token = request.args.get("token", "")
    if not token:
        return jsonify({"error": "El token de verificación es obligatorio."}), 400
    if not verify_email_token(token):
        return jsonify(
            {"error": "El enlace de verificación es inválido o ha expirado."}
        ), 400
    return jsonify({"message": "Correo verificado correctamente."}), 200


def resend_verification():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "El cuerpo debe ser un objeto JSON."}), 400

    try:
        resend_verification_email(data.get("correo"))
    except AuthValidationError as error:
        return jsonify({"error": str(error)}), 400
    except EmailDeliveryError:
        current_app.logger.exception("No se pudo reenviar la verificación.")

    return jsonify(
        {
            "message": (
                "Si la cuenta existe y aún no está verificada, "
                "recibirás un nuevo enlace."
            )
        }
    ), 200


def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "El cuerpo debe ser un objeto JSON."}), 400

    correo = data.get("correo")
    password = data.get("password")
    if not isinstance(correo, str) or not isinstance(password, str):
        return jsonify({"error": "Correo y contraseña son obligatorios."}), 400

    try:
        user, token = authenticate_user(correo, password)
    except EmailNotVerifiedError:
        return jsonify(
            {"error": "Debes verificar tu correo antes de iniciar sesión."}
        ), 403
    if user is None or token is None:
        return jsonify({"error": "Credenciales inválidas."}), 401

    return jsonify(
        {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": current_app.config["JWT_ACCESS_TOKEN_EXPIRES"],
            "user": perfil_publico(user),
        }
    )
