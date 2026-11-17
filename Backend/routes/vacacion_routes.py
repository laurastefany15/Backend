from flask import Blueprint

from controllers.vacacion_controller import balances, create, delete, index, show, update
from services.auth_service import jwt_required


vacacion_bp = Blueprint("vacaciones", __name__, url_prefix="/vacaciones")
vacacion_bp.add_url_rule("", view_func=jwt_required(index), methods=["GET"])
vacacion_bp.add_url_rule("", view_func=jwt_required(create), methods=["POST"])
vacacion_bp.add_url_rule("/saldos", view_func=jwt_required(balances), methods=["GET"])
vacacion_bp.add_url_rule(
    "/<int:vacacion_id>",
    view_func=jwt_required(show),
    methods=["GET"],
)
vacacion_bp.add_url_rule(
    "/<int:vacacion_id>",
    view_func=jwt_required(update),
    methods=["PUT", "PATCH"],
)
vacacion_bp.add_url_rule(
    "/<int:vacacion_id>",
    view_func=jwt_required(delete),
    methods=["DELETE"],
)
