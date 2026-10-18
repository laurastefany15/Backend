import os
from importlib import import_module

from flask import Flask, jsonify

from extensions import db, migrate


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI="sqlite:///"
        + os.path.join(app.instance_path, "nomina.sqlite3").replace("\\", "/"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)
    migrate.init_app(app, db)
    import_module("models")

    @app.get("/")
    def index():
        return jsonify({"message": "API de nómina Colombia"})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)