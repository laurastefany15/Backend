from flask import Blueprint

from controllers.contrato_controller import create, delete, index, show, update
from services.auth_service import jwt_required


contrato_bp = Blueprint("contratos", __name__, url_prefix="/contratos")
contrato_bp.add_url_rule("", view_func=jwt_required(index), methods=["GET"])
contrato_bp.add_url_rule("", view_func=jwt_required(create), methods=["POST"])
contrato_bp.add_url_rule(
    "/<int:contrato_id>",
    view_func=jwt_required(show),
    methods=["GET"],
)
contrato_bp.add_url_rule(
    "/<int:contrato_id>",
    view_func=jwt_required(update),
    methods=["PUT", "PATCH"],
)
contrato_bp.add_url_rule(
    "/<int:contrato_id>",
    view_func=jwt_required(delete),
    methods=["DELETE"],
)
