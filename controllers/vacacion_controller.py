from flask import jsonify, request

from services.vacacion_service import (
    VacacionConflictError,
    VacacionForbiddenError,
    VacacionNotFoundError,
    VacacionValidationError,
    create_vacation,
    delete_vacation,
    get_vacation,
    list_balances,
    list_vacations,
    update_vacation,
)


def _error_response(error):
    if isinstance(error, VacacionValidationError):
        status_code = 400
    elif isinstance(error, VacacionForbiddenError):
        status_code = 403
    elif isinstance(error, VacacionNotFoundError):
        status_code = 404
    elif isinstance(error, VacacionConflictError):
        status_code = 409
    else:
        raise error
    return jsonify({"error": str(error)}), status_code


def _page_args():
    try:
        return int(request.args.get("page", "1")), int(request.args.get("per_page", "20"))
    except ValueError:
        return None


def index(current_user):
    pages = _page_args()
    if pages is None:
        return jsonify({"error": "page y per_page deben ser números enteros."}), 400
    page, per_page = pages
    try:
        result = list_vacations(
            current_user,
            page=page,
            per_page=per_page,
            contrato_id=request.args.get("contrato_id"),
            estado=request.args.get("estado"),
        )
    except (
        VacacionForbiddenError,
        VacacionNotFoundError,
        VacacionValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(result)


def balances(current_user):
    pages = _page_args()
    if pages is None:
        return jsonify({"error": "page y per_page deben ser números enteros."}), 400
    page, per_page = pages
    try:
        result = list_balances(
            current_user,
            page=page,
            per_page=per_page,
            contrato_id=request.args.get("contrato_id"),
        )
    except (
        VacacionForbiddenError,
        VacacionNotFoundError,
        VacacionValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(result)


def show(current_user, vacacion_id):
    try:
        vacacion = get_vacation(current_user, vacacion_id)
    except (VacacionForbiddenError, VacacionNotFoundError) as error:
        return _error_response(error)
    return jsonify({"vacacion": vacacion})


def create(current_user):
    try:
        vacacion = create_vacation(current_user, request.get_json(silent=True))
    except (
        VacacionConflictError,
        VacacionForbiddenError,
        VacacionNotFoundError,
        VacacionValidationError,
    ) as error:
        return _error_response(error)
    return jsonify({"message": "Vacación creada correctamente.", "vacacion": vacacion}), 201


def update(current_user, vacacion_id):
    try:
        vacacion = update_vacation(
            current_user,
            vacacion_id,
            request.get_json(silent=True),
            replace=request.method == "PUT",
        )
    except (
        VacacionConflictError,
        VacacionForbiddenError,
        VacacionNotFoundError,
        VacacionValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(
        {"message": "Vacación actualizada correctamente.", "vacacion": vacacion}
    )


def delete(current_user, vacacion_id):
    try:
        vacacion = delete_vacation(current_user, vacacion_id)
    except (VacacionForbiddenError, VacacionNotFoundError) as error:
        return _error_response(error)
    return jsonify({"message": "Vacación cancelada correctamente.", "vacacion": vacacion})
