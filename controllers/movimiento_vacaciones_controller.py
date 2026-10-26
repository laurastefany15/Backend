from flask import jsonify, request

from services.movimiento_vacaciones_service import (
    MovimientoVacacionesConflictError,
    MovimientoVacacionesForbiddenError,
    MovimientoVacacionesNotFoundError,
    MovimientoVacacionesValidationError,
    create_movement,
    delete_movement,
    get_movement,
    list_movements,
    update_movement,
)


def _error_response(error):
    if isinstance(error, MovimientoVacacionesValidationError):
        status_code = 400
    elif isinstance(error, MovimientoVacacionesForbiddenError):
        status_code = 403
    elif isinstance(error, MovimientoVacacionesNotFoundError):
        status_code = 404
    elif isinstance(error, MovimientoVacacionesConflictError):
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
        result = list_movements(
            current_user,
            page=page,
            per_page=per_page,
            contrato_id=request.args.get("contrato_id"),
            vacaciones_id=request.args.get("vacaciones_id"),
            tipo=request.args.get("tipo"),
        )
    except (
        MovimientoVacacionesForbiddenError,
        MovimientoVacacionesNotFoundError,
        MovimientoVacacionesValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(result)


def show(current_user, movimiento_id):
    try:
        movimiento = get_movement(current_user, movimiento_id)
    except (MovimientoVacacionesForbiddenError, MovimientoVacacionesNotFoundError) as error:
        return _error_response(error)
    return jsonify({"movimiento": movimiento})


def create(current_user):
    try:
        movimiento = create_movement(current_user, request.get_json(silent=True))
    except (
        MovimientoVacacionesConflictError,
        MovimientoVacacionesForbiddenError,
        MovimientoVacacionesNotFoundError,
        MovimientoVacacionesValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(
        {
            "message": "Movimiento de vacaciones creado correctamente.",
            "movimiento": movimiento,
        }
    ), 201


def update(current_user, movimiento_id):
    try:
        movimiento = update_movement(
            current_user,
            movimiento_id,
            request.get_json(silent=True),
            replace=request.method == "PUT",
        )
    except (
        MovimientoVacacionesConflictError,
        MovimientoVacacionesForbiddenError,
        MovimientoVacacionesNotFoundError,
        MovimientoVacacionesValidationError,
    ) as error:
        return _error_response(error)
    return jsonify(
        {
            "message": "Movimiento de vacaciones actualizado correctamente.",
            "movimiento": movimiento,
        }
    )


def delete(current_user, movimiento_id):
    try:
        movimiento = delete_movement(current_user, movimiento_id)
    except (
        MovimientoVacacionesConflictError,
        MovimientoVacacionesForbiddenError,
        MovimientoVacacionesNotFoundError,
    ) as error:
        return _error_response(error)
    return jsonify(
        {
            "message": "Movimiento de vacaciones eliminado correctamente.",
            "movimiento": movimiento,
        }
    )
