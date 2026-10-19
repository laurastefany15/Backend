from flask import Blueprint

from controllers.asistencia_controller import create, delete, index, show, update
from services.auth_service import jwt_required


asistencia_bp = Blueprint("asistencias", __name__, url_prefix="/asistencias")
asistencia_bp.add_url_rule("", view_func=jwt_required(index), methods=["GET"])
asistencia_bp.add_url_rule("", view_func=jwt_required(create), methods=["POST"])
asistencia_bp.add_url_rule(
    "/<int:asistencia_id>",
    view_func=jwt_required(show),
    methods=["GET"],
)
asistencia_bp.add_url_rule(
    "/<int:asistencia_id>",
    view_func=jwt_required(update),
    methods=["PUT", "PATCH"],
)
asistencia_bp.add_url_rule(
    "/<int:asistencia_id>",
    view_func=jwt_required(delete),
    methods=["DELETE"],
)
