from flask import jsonify, request

from services.hora_extra_service import (
    HoraExtraConflictError,
    HoraExtraForbiddenError,
    HoraExtraNotFoundError,
    HoraExtraValidationError,
    create_overtime,
    delete_overtime,
    get_overtime,
    list_overtime,
    update_overtime,
)


ERRORS = (
    HoraExtraConflictError,
    HoraExtraForbiddenError,
    HoraExtraNotFoundError,
    HoraExtraValidationError,
)


def _error_response(error):
    if isinstance(error, HoraExtraValidationError):
        status_code = 400
    elif isinstance(error, HoraExtraForbiddenError):
        status_code = 403
    elif isinstance(error, HoraExtraNotFoundError):
        status_code = 404
    elif isinstance(error, HoraExtraConflictError):
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
        result = list_overtime(
            current_user,
            page=page,
            per_page=per_page,
            contrato_id=request.args.get("contrato_id"),
            estado=request.args.get("estado"),
            desde=request.args.get("desde"),
            hasta=request.args.get("hasta"),
        )
    except ERRORS as error:
        return _error_response(error)
    return jsonify(result)


def show(current_user, hora_extra_id):
    try:
        hora_extra = get_overtime(current_user, hora_extra_id)
    except ERRORS as error:
        return _error_response(error)
    return jsonify({"hora_extra": hora_extra})


def create(current_user):
    try:
        hora_extra = create_overtime(current_user, request.get_json(silent=True))
    except ERRORS as error:
        return _error_response(error)
    return jsonify(
        {"message": "Hora extra registrada correctamente.", "hora_extra": hora_extra}
    ), 201


def update(current_user, hora_extra_id):
    try:
        hora_extra = update_overtime(
            current_user,
            hora_extra_id,
            request.get_json(silent=True),
            replace=request.method == "PUT",
        )
    except ERRORS as error:
        return _error_response(error)
    return jsonify(
        {"message": "Hora extra actualizada correctamente.", "hora_extra": hora_extra}
    )


def delete(current_user, hora_extra_id):
    try:
        hora_extra = delete_overtime(current_user, hora_extra_id)
    except ERRORS as error:
        return _error_response(error)
    return jsonify(
        {"message": "Hora extra rechazada correctamente.", "hora_extra": hora_extra}
    )
