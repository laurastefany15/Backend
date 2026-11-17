from flask import Blueprint

from controllers.empresa_controller import create, delete, index, show, update
from services.auth_service import admin_required, jwt_required


empresa_bp = Blueprint("empresas", __name__, url_prefix="/admin/empresas")


def protected_admin(view):
    return jwt_required(admin_required(view))


empresa_bp.add_url_rule("", view_func=protected_admin(index), methods=["GET"])
empresa_bp.add_url_rule("", view_func=protected_admin(create), methods=["POST"])
empresa_bp.add_url_rule(
    "/<int:empresa_id>",
    view_func=protected_admin(show),
    methods=["GET"],
)
empresa_bp.add_url_rule(
    "/<int:empresa_id>",
    view_func=protected_admin(update),
    methods=["PUT", "PATCH"],
)
empresa_bp.add_url_rule(
    "/<int:empresa_id>",
    view_func=protected_admin(delete),
    methods=["DELETE"],
)
