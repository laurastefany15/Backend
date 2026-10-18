from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Callable

import jwt
from flask import current_app, jsonify, request
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import Usuario


class AuthValidationError(ValueError):
    pass


class EmailAlreadyRegisteredError(ValueError):
    pass


def _normalize_email(correo):
    if not isinstance(correo, str):
        raise AuthValidationError("El correo es obligatorio.")

    correo = correo.strip().lower()
    local, separator, domain = correo.partition("@")
    if (
        not correo
        or len(correo) > 150
        or not separator
        or not local
        or "." not in domain
        or domain.startswith(".")
        or domain.endswith(".")
        or correo.count("@") != 1
        or any(character.isspace() for character in correo)
    ):
        raise AuthValidationError("El correo no tiene un formato válido.")
    return correo


def _find_user_by_email(correo):
    return Usuario.query.filter(db.func.lower(Usuario.correo) == correo).first()


def _get_jwt_secret():
    secret = current_app.config.get("JWT_SECRET_KEY")
    if not isinstance(secret, str) or len(secret.encode("utf-8")) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY debe configurarse con una clave de al menos 32 bytes."
        )
    return secret


def register_user(correo, password):
    correo = _normalize_email(correo)
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        raise AuthValidationError(
            "La contraseña debe tener entre 8 y 128 caracteres."
        )
    if _find_user_by_email(correo) is not None:
        raise EmailAlreadyRegisteredError("El correo ya está registrado.")

    user = Usuario(correo=correo, hash_password=generate_password_hash(password))
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if _find_user_by_email(correo) is not None:
            raise EmailAlreadyRegisteredError("El correo ya está registrado.")
        raise
    return user


def authenticate_user(correo, password):
    try:
        correo = _normalize_email(correo)
    except AuthValidationError:
        return None, None

    if not isinstance(password, str):
        return None, None

    user = _find_user_by_email(correo)
    if (
        user is None
        or not user.activo
        or not check_password_hash(user.hash_password, password)
    ):
        return None, None

    return user, create_access_token(user)


def create_access_token(user):
    secret = _get_jwt_secret()
    expires_in = current_app.config.get("JWT_ACCESS_TOKEN_EXPIRES", 3600)
    issued_at = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(user.id),
            "iat": issued_at,
            "exp": issued_at + timedelta(seconds=expires_in),
        },
        secret,
        algorithm="HS256",
    )
    return token


def jwt_required(view_func: Callable):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not token:
            return jsonify({"error": "Se requiere un token Bearer válido."}), 401

        secret = _get_jwt_secret()
        try:
            claims = jwt.decode(token, secret, algorithms=["HS256"])
            user_id = int(claims["sub"])
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            return jsonify({"error": "El token es inválido o ha expirado."}), 401

        user = db.session.get(Usuario, user_id)
        if user is None or not user.activo:
            return jsonify({"error": "El usuario no está disponible."}), 401

        return view_func(*args, current_user=user, **kwargs)

    return wrapped
