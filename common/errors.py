"""
errors.py - Errores genéricos de la aplicación, compartidos por todos los módulos.
Entradas: un mensaje de texto (opcional; si no se da, se usa el mensaje por defecto).
Esperado: cada error lleva su código HTTP; un manejador central en app.py los convertirá en JSON.
Cambios: 2026-11-10 | Stiven B | creación de la jerarquía de errores comunes
"""


class AppError(Exception):
    """Error base. Las subclases solo definen status_code y un mensaje por defecto."""

    status_code = 500
    default_message = "Error interno del servidor."

    def __init__(self, message=None):
        self.message = message or self.default_message
        super().__init__(self.message)


class ValidationError(AppError):
    status_code = 400
    default_message = "Los datos enviados no son válidos."


class UnauthorizedError(AppError):
    status_code = 401
    default_message = "No autenticado."


class ForbiddenError(AppError):
    status_code = 403
    default_message = "No tiene permiso para esta acción."


class NotFoundError(AppError):
    status_code = 404
    default_message = "Recurso no encontrado."


class ConflictError(AppError):
    status_code = 409
    default_message = "El recurso entra en conflicto con uno existente."