from flask import jsonify, request

from services.asistencia_service import (
    AsistenciaConflictError,
    AsistenciaForbiddenError,
    AsistenciaNotFoundError,
    AsistenciaValidationError,
    create_attendance,
    delete_attendance,
    get_attendance,
    list_attendance,
    update_attendance,
)


def _error_response(error):
    if isinstance(error, AsistenciaValidationError):
        status_code = 400
    elif isinstance(error, AsistenciaForbiddenError):
        status_code = 403
    elif isinstance(error, AsistenciaNotFoundError):
        status_code = 404
    elif isinstance(error, AsistenciaConflictError):
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
        result = list_attendance(
            current_user,
            page=page,
            per_page=per_page,
            contrato_id=request.args.get("contrato_id"),
            estado=request.args.get("estado"),
        )
    except (
        AsistenciaForbiddenError,
        AsistenciaNotFoundError,
        AsistenciaValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(result)


def show(current_user, asistencia_id):
    try:
        asistencia = get_attendance(current_user, asistencia_id)
    except (AsistenciaForbiddenError, AsistenciaNotFoundError) as error:
        return _error_response(error)
    return jsonify({"asistencia": asistencia})


def create(current_user):
    try:
        asistencia = create_attendance(current_user, request.get_json(silent=True))
    except (
        AsistenciaConflictError,
        AsistenciaForbiddenError,
        AsistenciaNotFoundError,
        AsistenciaValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(
        {"message": "Asistencia creada correctamente.", "asistencia": asistencia}
    ), 201


def update(current_user, asistencia_id):
    try:
        asistencia = update_attendance(
            current_user,
            asistencia_id,
            request.get_json(silent=True),
            replace=request.method == "PUT",
        )
    except (
        AsistenciaConflictError,
        AsistenciaForbiddenError,
        AsistenciaNotFoundError,
        AsistenciaValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(
        {"message": "Asistencia actualizada correctamente.", "asistencia": asistencia}
    )


def delete(current_user, asistencia_id):
    try:
        asistencia = delete_attendance(current_user, asistencia_id)
    except (AsistenciaForbiddenError, AsistenciaNotFoundError) as error:
        return _error_response(error)
    return jsonify(
        {"message": "Asistencia anulada correctamente.", "asistencia": asistencia}
    )
