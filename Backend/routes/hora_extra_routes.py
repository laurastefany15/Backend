from flask import Blueprint

from controllers.hora_extra_controller import create, delete, index, show, update
from services.auth_service import jwt_required


hora_extra_bp = Blueprint("horas_extras", __name__, url_prefix="/horas-extras")
hora_extra_bp.add_url_rule("", view_func=jwt_required(index), methods=["GET"])
hora_extra_bp.add_url_rule("", view_func=jwt_required(create), methods=["POST"])
hora_extra_bp.add_url_rule(
    "/<int:hora_extra_id>",
    view_func=jwt_required(show),
    methods=["GET"],
)
hora_extra_bp.add_url_rule(
    "/<int:hora_extra_id>",
    view_func=jwt_required(update),
    methods=["PUT", "PATCH"],
)
hora_extra_bp.add_url_rule(
    "/<int:hora_extra_id>",
    view_func=jwt_required(delete),
    methods=["DELETE"],
)
