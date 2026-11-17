from flask import Blueprint

from controllers.nomina_controller import (
    annul,
    approve,
    generate,
    index,
    pay,
    periods_approve,
    periods_close,
    periods_index,
    periods_show,
    receipt,
    report,
    show,
)
from services.auth_service import jwt_required


nomina_bp = Blueprint("nominas", __name__, url_prefix="/nominas")
nomina_bp.add_url_rule("", view_func=jwt_required(index), methods=["GET"])
nomina_bp.add_url_rule("/reporte", view_func=jwt_required(report), methods=["GET"])
nomina_bp.add_url_rule("/generar", view_func=jwt_required(generate), methods=["POST"])
nomina_bp.add_url_rule("/<int:nomina_id>", view_func=jwt_required(show), methods=["GET"])
nomina_bp.add_url_rule(
    "/<int:nomina_id>/recibo",
    view_func=jwt_required(receipt),
    methods=["GET"],
)
nomina_bp.add_url_rule(
    "/<int:nomina_id>/aprobar",
    view_func=jwt_required(approve),
    methods=["POST"],
)
nomina_bp.add_url_rule(
    "/<int:nomina_id>/anular",
    view_func=jwt_required(annul),
    methods=["POST"],
)
nomina_bp.add_url_rule(
    "/<int:nomina_id>/pagar",
    view_func=jwt_required(pay),
    methods=["POST"],
)
nomina_bp.add_url_rule("/periodos", view_func=jwt_required(periods_index), methods=["GET"])
nomina_bp.add_url_rule(
    "/periodos/<int:periodo_id>",
    view_func=jwt_required(periods_show),
    methods=["GET"],
)
nomina_bp.add_url_rule(
    "/periodos/<int:periodo_id>/aprobar",
    view_func=jwt_required(periods_approve),
    methods=["POST"],
)
nomina_bp.add_url_rule(
    "/periodos/<int:periodo_id>/cerrar",
    view_func=jwt_required(periods_close),
    methods=["POST"],
)
