from flask import Blueprint

from controllers.incapacidad_controller import (
    create,
    delete,
    documents_delete,
    documents_download,
    documents_index,
    documents_show,
    documents_upload,
    index,
    show,
    update,
)
from services.auth_service import jwt_required


incapacidad_bp = Blueprint("incapacidades", __name__, url_prefix="/incapacidades")
incapacidad_bp.add_url_rule("", view_func=jwt_required(index), methods=["GET"])
incapacidad_bp.add_url_rule("", view_func=jwt_required(create), methods=["POST"])
incapacidad_bp.add_url_rule(
    "/<int:incapacidad_id>",
    view_func=jwt_required(show),
    methods=["GET"],
)
incapacidad_bp.add_url_rule(
    "/<int:incapacidad_id>",
    view_func=jwt_required(update),
    methods=["PUT", "PATCH"],
)
incapacidad_bp.add_url_rule(
    "/<int:incapacidad_id>",
    view_func=jwt_required(delete),
    methods=["DELETE"],
)
incapacidad_bp.add_url_rule(
    "/<int:incapacidad_id>/documentos",
    view_func=jwt_required(documents_index),
    methods=["GET"],
)
incapacidad_bp.add_url_rule(
    "/<int:incapacidad_id>/documentos",
    view_func=jwt_required(documents_upload),
    methods=["POST"],
)
incapacidad_bp.add_url_rule(
    "/<int:incapacidad_id>/documentos/<int:documento_id>",
    view_func=jwt_required(documents_show),
    methods=["GET"],
)
incapacidad_bp.add_url_rule(
    "/<int:incapacidad_id>/documentos/<int:documento_id>/archivo",
    view_func=jwt_required(documents_download),
    methods=["GET"],
)
incapacidad_bp.add_url_rule(
    "/<int:incapacidad_id>/documentos/<int:documento_id>",
    view_func=jwt_required(documents_delete),
    methods=["DELETE"],
)
