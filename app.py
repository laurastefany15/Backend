import os
from importlib import import_module
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, send_from_directory

load_dotenv(Path(__file__).resolve().parent / ".env")

from extensions import db, migrate
from routes.asistencia_routes import asistencia_bp
from routes.auth_routes import auth_bp
from routes.contrato_routes import contrato_bp
from routes.empleado_routes import empleado_bp
from routes.empresa_routes import empresa_bp
from routes.incapacidad_routes import incapacidad_bp
from routes.movimiento_vacaciones_routes import movimiento_vacaciones_bp
from routes.usuario_empresa_routes import usuario_empresa_bp
from routes.vacacion_routes import vacacion_bp
from flask_swagger_ui import get_swaggerui_blueprint


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI="sqlite:///"
        + os.path.join(app.instance_path, "nomina.sqlite3").replace("\\", "/"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY"),
        JWT_ACCESS_TOKEN_EXPIRES=3600,
        UPLOAD_FOLDER=os.path.join(app.instance_path, "uploads"),
        MAX_DOCUMENT_BYTES=10 * 1024 * 1024,
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,
    )
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

    @app.errorhandler(413)
    def request_too_large(_error):
        return jsonify({"error": "La petición supera el tamaño máximo de 50 MB."}), 413

    @app.get("/")
    def index():
        return jsonify({"message": "API de nómina Colombia"})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)