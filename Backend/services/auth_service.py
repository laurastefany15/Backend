import hashlib
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from functools import wraps
from typing import Callable
from urllib.parse import urlencode

import jwt
from flask import current_app, jsonify, request
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import Rol, Usuario, UsuarioRol
from services.acceso_service import tiene_rol


class AuthValidationError(ValueError):
    pass


class EmailAlreadyRegisteredError(ValueError):
    pass


class EmailNotVerifiedError(ValueError):
    pass


class EmailDeliveryError(RuntimeError):
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


def assign_role(user, codigo):
    rol = Rol.query.filter_by(codigo=codigo).first()
    if rol is None:
        raise RuntimeError(
            f"El rol {codigo} no está disponible. Ejecuta las migraciones."
        )
    exists = UsuarioRol.query.filter_by(usuario_id=user.id, rol_id=rol.id).first()
    if exists is None:
        db.session.add(UsuarioRol(usuario_id=user.id, rol_id=rol.id))


def _new_verification_token(user):
    token = secrets.token_urlsafe(32)
    user.token_verificacion_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    ttl_minutes = int(current_app.config["EMAIL_VERIFICATION_TOKEN_TTL_MINUTES"])
    user.token_verificacion_expira_en = datetime.now(timezone.utc) + timedelta(
        minutes=ttl_minutes
    )
    return token


def _send_verification_email(user, token):
    config = current_app.config
    host = config.get("SMTP_HOST")
    sender = config.get("SMTP_FROM") or config.get("SMTP_USERNAME")
    username = config.get("SMTP_USERNAME")
    password = config.get("SMTP_PASSWORD")
    use_tls = config.get("SMTP_USE_TLS", True)
    if (
        not host
        or not sender
        or bool(username) != bool(password)
        or (username and not use_tls)
    ):
        raise EmailDeliveryError("La configuración SMTP está incompleta.")

    query = urlencode({"token": token})
    link = f"{config['EMAIL_VERIFICATION_BASE_URL']}/auth/verify-email?{query}"
    message = EmailMessage()
    message["Subject"] = "Verifica tu correo"
    message["From"] = sender
    message["To"] = user.correo
    message.set_content(
        "Para verificar tu correo, abre este enlace:\n\n"
        f"{link}\n\n"
        "El enlace vence en "
        f"{config['EMAIL_VERIFICATION_TOKEN_TTL_MINUTES']} minutos."
    )

    try:
        with smtplib.SMTP(host, int(config["SMTP_PORT"]), timeout=15) as server:
            if use_tls:
                server.starttls(context=ssl.create_default_context())
            if username:
                server.login(username, password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError) as error:
        raise EmailDeliveryError("No se pudo entregar el correo.") from error


def register_user(correo, password):
    correo = _normalize_email(correo)
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        raise AuthValidationError(
            "La contraseña debe tener entre 8 y 128 caracteres."
        )
    if _find_user_by_email(correo) is not None:
        raise EmailAlreadyRegisteredError("El correo ya está registrado.")

    user = Usuario(
        correo=correo,
        hash_password=generate_password_hash(password),
        correo_verificado=False,
    )
    db.session.add(user)
    try:
        db.session.flush()
        assign_role(user, "ADMIN")
        token = _new_verification_token(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if _find_user_by_email(correo) is not None:
            raise EmailAlreadyRegisteredError("El correo ya está registrado.")
        raise
    except Exception:
        db.session.rollback()
        raise
    _send_verification_email(user, token)
    return user


def resend_verification_email(correo):
    correo = _normalize_email(correo)
    user = _find_user_by_email(correo)
    if user is None or user.correo_verificado:
        return

    token = _new_verification_token(user)
    db.session.commit()
    _send_verification_email(user, token)


def verify_email_token(token):
    if not isinstance(token, str) or not token or len(token) > 128:
        return False
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    user = Usuario.query.filter_by(token_verificacion_hash=token_hash).first()
    if user is None or user.token_verificacion_expira_en is None:
        return False

    expires_at = user.token_verificacion_expira_en
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        return False

    user.correo_verificado = True
    user.token_verificacion_hash = None
    user.token_verificacion_expira_en = None
    db.session.commit()
    return True


def ensure_superuser_account(correo, password):
    correo = _normalize_email(correo)
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        raise AuthValidationError(
            "La contraseña debe tener entre 8 y 128 caracteres."
        )
    user = _find_user_by_email(correo)
    if user is None:
        user = Usuario(
            correo=correo,
            hash_password=generate_password_hash(password),
            activo=True,
        )
        db.session.add(user)
        db.session.flush()
    assign_role(user, "SUPERUSER")
    db.session.commit()
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
    if not user.correo_verificado:
        raise EmailNotVerifiedError("El correo no está verificado.")

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


def role_required(*codigos):
    def decorator(view_func: Callable):
        @wraps(view_func)
        def wrapped(*args, current_user, **kwargs):
            if not tiene_rol(current_user, *codigos):
                lista = " o ".join(codigos)
                return jsonify({"error": f"Se requiere el rol {lista}."}), 403
            return view_func(*args, current_user=current_user, **kwargs)

        return wrapped

    return decorator


def admin_required(view_func: Callable):
    return role_required("ADMIN")(view_func)
