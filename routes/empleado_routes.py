from flask import Blueprint

from controllers.empleado_controller import create, delete, index, show, update
from services.auth_service import jwt_required


empleado_bp = Blueprint("empleados", __name__, url_prefix="/empleados")
empleado_bp.add_url_rule("", view_func=jwt_required(index), methods=["GET"])
empleado_bp.add_url_rule("", view_func=jwt_required(create), methods=["POST"])
empleado_bp.add_url_rule(
    "/<int:empleado_id>",
    view_func=jwt_required(show),
    methods=["GET"],
)
empleado_bp.add_url_rule(
    "/<int:empleado_id>",
    view_func=jwt_required(update),
    methods=["PUT", "PATCH"],
)
empleado_bp.add_url_rule(
    "/<int:empleado_id>",
    view_func=jwt_required(delete),
    methods=["DELETE"],
)
