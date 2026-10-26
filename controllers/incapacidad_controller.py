from flask import jsonify, request, send_file

from services.documento_incapacidad_service import (
    delete_document,
    document_file,
    get_document,
    list_documents,
    upload_documents,
)
from services.incapacidad_service import (
    IncapacidadConflictError,
    IncapacidadForbiddenError,
    IncapacidadNotFoundError,
    IncapacidadValidationError,
    create_disability,
    delete_disability,
    form_to_payload,
    get_disability,
    list_disabilities,
    update_disability,
)


def _uploaded_files(field):
    return [upload for upload in request.files.getlist(field) if upload and upload.filename]


def _error_response(error):
    if isinstance(error, IncapacidadValidationError):
        status_code = 400
    elif isinstance(error, IncapacidadForbiddenError):
        status_code = 403
    elif isinstance(error, IncapacidadNotFoundError):
        status_code = 404
    elif isinstance(error, IncapacidadConflictError):
        status_code = 409
    else:
        raise error
    return jsonify({"error": str(error)}), status_code


def index(current_user):
    try:
        page = int(request.args.get("page", "1"))
        per_page = int(request.args.get("per_page", "20"))
    except ValueError:
        return jsonify({"error": "page y per_page deben ser números enteros."}), 400

    try:
        result = list_disabilities(
            current_user,
            page=page,
            per_page=per_page,
            contrato_id=request.args.get("contrato_id"),
            estado=request.args.get("estado"),
            tipo=request.args.get("tipo"),
        )
    except (
        IncapacidadForbiddenError,
        IncapacidadNotFoundError,
        IncapacidadValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(result)


def show(current_user, incapacidad_id):
    try:
        incapacidad = get_disability(current_user, incapacidad_id)
    except (IncapacidadForbiddenError, IncapacidadNotFoundError) as error:
        return _error_response(error)
    return jsonify({"incapacidad": incapacidad})


def create(current_user):
    if request.mimetype == "multipart/form-data":
        form = request.form.to_dict()
        tipo_documento = form.pop("tipo_documento", None)
        data = form_to_payload(form)
        uploads = _uploaded_files("documentos")
    else:
        data = request.get_json(silent=True)
        tipo_documento = None
        uploads = []
    try:
        incapacidad = create_disability(current_user, data, uploads, tipo_documento)
    except (
        IncapacidadConflictError,
        IncapacidadForbiddenError,
        IncapacidadNotFoundError,
        IncapacidadValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(
        {"message": "Incapacidad creada correctamente.", "incapacidad": incapacidad}
    ), 201


def update(current_user, incapacidad_id):
    try:
        incapacidad = update_disability(
            current_user,
            incapacidad_id,
            request.get_json(silent=True),
            replace=request.method == "PUT",
        )
    except (
        IncapacidadConflictError,
        IncapacidadForbiddenError,
        IncapacidadNotFoundError,
        IncapacidadValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(
        {"message": "Incapacidad actualizada correctamente.", "incapacidad": incapacidad}
    )


def delete(current_user, incapacidad_id):
    try:
        incapacidad = delete_disability(current_user, incapacidad_id)
    except (IncapacidadForbiddenError, IncapacidadNotFoundError) as error:
        return _error_response(error)
    return jsonify(
        {"message": "Incapacidad rechazada correctamente.", "incapacidad": incapacidad}
    )


def documents_index(current_user, incapacidad_id):
    try:
        documentos = list_documents(current_user, incapacidad_id)
    except (IncapacidadForbiddenError, IncapacidadNotFoundError) as error:
        return _error_response(error)
    return jsonify({"items": documentos})


def documents_upload(current_user, incapacidad_id):
    if request.mimetype != "multipart/form-data":
        return jsonify({"error": "Envíe los archivos como multipart/form-data."}), 400
    try:
        documentos = upload_documents(
            current_user,
            incapacidad_id,
            _uploaded_files("documentos"),
            request.form.get("tipo"),
        )
    except (
        IncapacidadForbiddenError,
        IncapacidadNotFoundError,
        IncapacidadValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(
        {"message": "Documentos cargados correctamente.", "documentos": documentos}
    ), 201


def documents_show(current_user, incapacidad_id, documento_id):
    try:
        documento = get_document(current_user, incapacidad_id, documento_id)
    except (IncapacidadForbiddenError, IncapacidadNotFoundError) as error:
        return _error_response(error)
    return jsonify({"documento": documento})


def documents_download(current_user, incapacidad_id, documento_id):
    try:
        path, documento = document_file(current_user, incapacidad_id, documento_id)
    except (IncapacidadForbiddenError, IncapacidadNotFoundError) as error:
        return _error_response(error)
    return send_file(
        path,
        mimetype=documento.content_type,
        as_attachment=request.args.get("inline") != "1",
        download_name=documento.nombre_original,
    )


def documents_delete(current_user, incapacidad_id, documento_id):
    try:
        documento = delete_document(current_user, incapacidad_id, documento_id)
    except (IncapacidadForbiddenError, IncapacidadNotFoundError) as error:
        return _error_response(error)
    return jsonify({"message": "Documento eliminado correctamente.", "documento": documento})
