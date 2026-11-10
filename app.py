"""
app.py - Crea y configura la aplicación Flask (extensiones, blueprints, docs, manejo de errores).
Entradas: config_name (opcional) o variable APP_ENV; test_config (opcional) para pruebas.
Esperado: devuelve la app lista; en producción falla si la configuración es insegura; todo error responde en JSON.
Cambios: 2026-11-10 | Stiven B | configuración movida a config.py
         2026-11-10 | Stiven B | manejador central de errores en JSON
"""
import logging
import os
from importlib import import_module

from flask import Flask, jsonify, send_from_directory
from flask_swagger_ui import get_swaggerui_blueprint
from werkzeug.exceptions import HTTPException

from common.errors import AppError
from config import get_config
from extensions import db, migrate
from routes.asistencia_routes import asistencia_bp
from routes.auth_routes import auth_bp
from routes.contrato_routes import contrato_bp
from routes.empleado_routes import empleado_bp
from routes.empresa_routes import empresa_bp
from routes.hora_extra_routes import hora_extra_bp
from routes.incapacidad_routes import incapacidad_bp
from routes.movimiento_vacaciones_routes import movimiento_vacaciones_bp
from routes.nomina_routes import nomina_bp
from routes.usuario_empresa_routes import usuario_empresa_bp
from routes.vacacion_routes import vacacion_bp

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def handle_app_error(error):
        return jsonify({"error": error.message}), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        # El 413 conserva su mensaje propio en español.
        if error.code == 413:
            message = "La petición supera el tamaño máximo de 50 MB."
        else:
            message = error.description
        return jsonify({"error": message}), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        logger.exception("Error no controlado")
        return jsonify({"error": "Error interno del servidor."}), 500


def create_app(config_name=None, test_config=None):
    app = Flask(__name__)

    config_class = get_config(config_name or os.environ.get("APP_ENV", "development"))
    config_class.validate()
    app.config.from_object(config_class)
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)
    migrate.init_app(app, db)
    import_module("models")
    app.register_blueprint(auth_bp)
    app.register_blueprint(empleado_bp)
    app.register_blueprint(contrato_bp)
    app.register_blueprint(asistencia_bp)
    app.register_blueprint(vacacion_bp)
    app.register_blueprint(movimiento_vacaciones_bp)
    app.register_blueprint(incapacidad_bp)
    app.register_blueprint(hora_extra_bp)
    app.register_blueprint(nomina_bp)
    app.register_blueprint(empresa_bp)
    app.register_blueprint(usuario_empresa_bp)
    app.register_blueprint(
        get_swaggerui_blueprint(
            "/apidocs",
            "/openapi.yaml",
            config={"app_name": "API de nómina Colombia"},
        )
    )

    @app.get("/openapi.yaml")
    def openapi_spec():
        return send_from_directory(
            os.path.join(app.root_path, "docs"),
            "openapi.yaml",
            mimetype="application/yaml",
        )

    register_error_handlers(app)

    @app.get("/")
    def index():
        return jsonify({"message": "API de nómina Colombia"})

    return app


# Se mantiene temporalmente porque los tests actuales hacen "from app import app".
# Se eliminará cuando los tests usen una fixture.
app = create_app()


if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])