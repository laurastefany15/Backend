from flask import Blueprint

from controllers.usuario_admin_controller import (
    create,
    index,
    show,
    update_companies,
    update_status,
)
from services.auth_service import admin_required, jwt_required


usuario_admin_bp = Blueprint(
    "usuario_admin",
    __name__,
    url_prefix="/admin/usuarios",
)


def protected_admin(view):
    return jwt_required(admin_required(view))


usuario_admin_bp.add_url_rule("", view_func=protected_admin(index), methods=["GET"])
usuario_admin_bp.add_url_rule("", view_func=protected_admin(create), methods=["POST"])
usuario_admin_bp.add_url_rule(
    "/<int:usuario_id>",
    view_func=protected_admin(show),
    methods=["GET"],
)
usuario_admin_bp.add_url_rule(
    "/<int:usuario_id>",
    view_func=protected_admin(update_status),
    methods=["PATCH"],
)
usuario_admin_bp.add_url_rule(
    "/<int:usuario_id>/empresas",
    view_func=protected_admin(update_companies),
    methods=["PUT"],
)
