from flask import Blueprint

from controllers.superuser_controller import (
    companies,
    company,
    summary,
    user_status,
    users,
)
from services.auth_service import jwt_required, role_required


superuser_bp = Blueprint("superuser", __name__, url_prefix="/superuser")


def protected(view):
    return jwt_required(role_required("SUPERUSER")(view))


superuser_bp.add_url_rule("/resumen", view_func=protected(summary), methods=["GET"])
superuser_bp.add_url_rule("/empresas", view_func=protected(companies), methods=["GET"])
superuser_bp.add_url_rule(
    "/empresas/<int:empresa_id>",
    view_func=protected(company),
    methods=["GET"],
)
superuser_bp.add_url_rule("/usuarios", view_func=protected(users), methods=["GET"])
superuser_bp.add_url_rule(
    "/usuarios/<int:usuario_id>",
    view_func=protected(user_status),
    methods=["PATCH"],
)
