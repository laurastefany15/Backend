from flask import jsonify, request

from services import item_service
from services.item_service import ServiceError


def _error_response(error):
    return jsonify(error=str(error)), error.status_code


def list_items():
    return jsonify([item.to_dict() for item in item_service.list_items()])


def create_item():
    try:
        item = item_service.create_item(request.get_json(silent=True))
    except ServiceError as error:
        return _error_response(error)
    return jsonify(item.to_dict()), 201


def get_item(item_id):
    try:
        item = item_service.get_item(item_id)
    except ServiceError as error:
        return _error_response(error)
    return jsonify(item.to_dict())


def update_item(item_id):
    try:
        item = item_service.update_item(item_id, request.get_json(silent=True))
    except ServiceError as error:
        return _error_response(error)
    return jsonify(item.to_dict())


def delete_item(item_id):
    try:
        item_service.delete_item(item_id)
    except ServiceError as error:
        return _error_response(error)
    return "", 204