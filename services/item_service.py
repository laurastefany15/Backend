from models import Item


class ServiceError(Exception):
    status_code = 400


class ItemNotFoundError(ServiceError):
    status_code = 404


def list_items():
    return Item.list_all()


def create_item(data):
    if not isinstance(data, dict):
        raise ServiceError("El cuerpo debe ser un objeto JSON.")

    name = data.get("name")
    description = data.get("description", "")
    if not isinstance(name, str) or not name.strip():
        raise ServiceError("El campo 'name' es obligatorio.")
    if not isinstance(description, str):
        raise ServiceError("El campo 'description' debe ser texto.")

    return Item.create(name.strip(), description)


def get_item(item_id):
    item = Item.get_by_id(item_id)
    if item is None:
        raise ItemNotFoundError("Elemento no encontrado.")
    return item


def update_item(item_id, data):
    if not isinstance(data, dict) or not data:
        raise ServiceError("El cuerpo debe ser un objeto JSON no vacío.")

    fields = {}
    if "name" in data:
        if not isinstance(data["name"], str) or not data["name"].strip():
            raise ServiceError("El campo 'name' no puede estar vacío.")
        fields["name"] = data["name"].strip()
    if "description" in data:
        if not isinstance(data["description"], str):
            raise ServiceError("El campo 'description' debe ser texto.")
        fields["description"] = data["description"]
    if not fields:
        raise ServiceError("No hay campos válidos para actualizar.")

    item = Item.update(item_id, fields)
    if item is None:
        raise ItemNotFoundError("Elemento no encontrado.")
    return item


def delete_item(item_id):
    if not Item.delete(item_id):
        raise ItemNotFoundError("Elemento no encontrado.")