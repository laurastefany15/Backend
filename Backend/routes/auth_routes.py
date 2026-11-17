from flask import Blueprint, jsonify

from controllers.auth_controller import (
    login,
    register,
    resend_verification,
    verify_email,
)
from services.acceso_service import perfil_publico
from services.auth_service import jwt_required


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

auth_bp.add_url_rule("/register", view_func=register, methods=["POST"])
auth_bp.add_url_rule("/login", view_func=login, methods=["POST"])
auth_bp.add_url_rule("/verify-email", view_func=verify_email, methods=["GET"])
auth_bp.add_url_rule(
    "/resend-verification", view_func=resend_verification, methods=["POST"]
)


@auth_bp.get("/me")
@jwt_required
def me(current_user):
    return jsonify({"user": perfil_publico(current_user)})
