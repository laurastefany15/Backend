import os
import sqlite3

from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    database_path = app.config["DATABASE"]
    database_directory = os.path.dirname(database_path)
    if database_directory:
        os.makedirs(database_directory, exist_ok=True)

    with sqlite3.connect(database_path) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )