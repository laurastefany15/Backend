from sqlalchemy import (
    Integer,
    String,
)

from extensions import db


class Rol(db.Model):
    __tablename__ = "roles"

    id = db.Column(Integer, primary_key=True)
    codigo = db.Column(String(40), nullable=False, unique=True)
    descripcion = db.Column(String(200))
