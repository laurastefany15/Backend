import os

from flask import Flask, jsonify

from database import close_db, init_db
from routes.item_routes import item_routes


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "items.sqlite3"),
    )
    if test_config:
        app.config.update(test_config)

    app.teardown_appcontext(close_db)
    init_db(app)
    app.register_blueprint(item_routes)

    @app.get("/")
    def index():
        return jsonify({
            "message": "API Flask",
            "endpoints": {
                "items": "/api/items",
                "item": "/api/items/<id>",
            },
        })

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)