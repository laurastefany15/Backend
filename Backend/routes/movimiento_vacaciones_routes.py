from flask import Blueprint

from controllers.movimiento_vacaciones_controller import create, delete, index, show, update
from services.auth_service import jwt_required


movimiento_vacaciones_bp = Blueprint(
    "movimientos_vacaciones",
    __name__,
    url_prefix="/movimientos-vacaciones",
)
movimiento_vacaciones_bp.add_url_rule("", view_func=jwt_required(index), methods=["GET"])
movimiento_vacaciones_bp.add_url_rule("", view_func=jwt_required(create), methods=["POST"])
movimiento_vacaciones_bp.add_url_rule(
    "/<int:movimiento_id>",
    view_func=jwt_required(show),
    methods=["GET"],
)
movimiento_vacaciones_bp.add_url_rule(
    "/<int:movimiento_id>",
    view_func=jwt_required(update),
    methods=["PUT", "PATCH"],
)
movimiento_vacaciones_bp.add_url_rule(
    "/<int:movimiento_id>",
    view_func=jwt_required(delete),
    methods=["DELETE"],
)
