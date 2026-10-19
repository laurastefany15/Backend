from flask import Blueprint

from controllers.usuario_empresa_controller import create, delete, show, update
from services.auth_service import admin_required, jwt_required


usuario_empresa_bp = Blueprint(
    "usuario_empresa",
    __name__,
    url_prefix="/admin/usuarios",
)


def protected_admin(view):
    return jwt_required(admin_required(view))

usuario_empresa_bp.add_url_rule(
    "/<int:usuario_id>/empresa",
    view_func=protected_admin(show),
    methods=["GET"],
)
usuario_empresa_bp.add_url_rule(
    "/<int:usuario_id>/empresa",
    view_func=protected_admin(create),
    methods=["POST"],
)
usuario_empresa_bp.add_url_rule(
    "/<int:usuario_id>/empresa",
    view_func=protected_admin(update),
    methods=["PUT"],
)
usuario_empresa_bp.add_url_rule(
    "/<int:usuario_id>/empresa",
    view_func=protected_admin(delete),
    methods=["DELETE"],
)
