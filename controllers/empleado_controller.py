from flask import jsonify, request

from services.empleado_service import (
    EmpleadoConflictError,
    EmpleadoForbiddenError,
    EmpleadoNotFoundError,
    EmpleadoValidationError,
    create_employee,
    delete_employee,
    get_employee,
    list_employees,
    update_employee,
)


def _error_response(error):
    if isinstance(error, EmpleadoValidationError):
        status_code = 400
    elif isinstance(error, EmpleadoForbiddenError):
        status_code = 403
    elif isinstance(error, EmpleadoNotFoundError):
        status_code = 404
    elif isinstance(error, EmpleadoConflictError):
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
        result = list_employees(
            current_user,
            page=page,
            per_page=per_page,
            estado=request.args.get("estado"),
        )
    except (EmpleadoValidationError, EmpleadoForbiddenError) as error:
        return _error_response(error)
    return jsonify(result)


def show(current_user, empleado_id):
    try:
        empleado = get_employee(current_user, empleado_id)
    except (EmpleadoForbiddenError, EmpleadoNotFoundError) as error:
        return _error_response(error)
    return jsonify({"empleado": empleado})


def create(current_user):
    try:
        empleado = create_employee(current_user, request.get_json(silent=True))
    except (
        EmpleadoConflictError,
        EmpleadoForbiddenError,
        EmpleadoValidationError,
    ) as error:
        return _error_response(error)
    return jsonify({"message": "Empleado creado correctamente.", "empleado": empleado}), 201


def update(current_user, empleado_id):
    data = request.get_json(silent=True)
    try:
        empleado = update_employee(
            current_user,
            empleado_id,
            data,
            replace=request.method == "PUT",
        )
    except (
        EmpleadoConflictError,
        EmpleadoForbiddenError,
        EmpleadoNotFoundError,
        EmpleadoValidationError,
    ) as error:
        return _error_response(error)
    return jsonify({"message": "Empleado actualizado correctamente.", "empleado": empleado})


def delete(current_user, empleado_id):
    try:
        empleado = delete_employee(current_user, empleado_id)
    except (EmpleadoForbiddenError, EmpleadoNotFoundError) as error:
        return _error_response(error)
    return jsonify(
        {
            "message": "Empleado desactivado correctamente.",
            "empleado": empleado,
        }
    )
