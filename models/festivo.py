from sqlalchemy import (
    Date,
    String,
    Text,
)

from extensions import db


class Festivo(db.Model):
    __tablename__ = "festivos"

    fecha = db.Column(Date, primary_key=True)
    nombre = db.Column(String(150), nullable=False)
    observaciones = db.Column(Text)
