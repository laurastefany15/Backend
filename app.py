import os
from importlib import import_module

from flask import Flask, jsonify, send_from_directory

from extensions import db, migrate
from routes.auth_routes import auth_bp
from flask_swagger_ui import get_swaggerui_blueprint


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI="sqlite:///"
        + os.path.join(app.instance_path, "nomina.sqlite3").replace("\\", "/"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY"),
        JWT_ACCESS_TOKEN_EXPIRES=3600,
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)
    migrate.init_app(app, db)
    import_module("models")
    app.register_blueprint(auth_bp)
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

    @app.get("/")
    def index():
        return jsonify({"message": "API de nómina Colombia"})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)