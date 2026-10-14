from flask import Blueprint

from controllers import item_controller


item_routes = Blueprint("items", __name__, url_prefix="/api/items")


@item_routes.get("")
def list_items():
    return item_controller.list_items()


@item_routes.post("")
def create_item():
    return item_controller.create_item()


@item_routes.get("/<int:item_id>")
def get_item(item_id):
    return item_controller.get_item(item_id)


@item_routes.patch("/<int:item_id>")
def update_item(item_id):
    return item_controller.update_item(item_id)


@item_routes.delete("/<int:item_id>")
def delete_item(item_id):
    return item_controller.delete_item(item_id)