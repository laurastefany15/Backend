from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    case,
    or_,
    select,
    text,
)

from extensions import db


class ParametroNomina(db.Model):
    __tablename__ = "parametros_nomina"
    __table_args__ = (
        CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta >= vigente_desde",
            name="ck_parametro_vigencia",
        ),
        Index(
            "uq_parametros_nacional",
            "codigo",
            "vigente_desde",
            unique=True,
            sqlite_where=text("empresa_id IS NULL"),
        ),
        Index(
            "uq_parametros_empresa",
            "empresa_id",
            "codigo",
            "vigente_desde",
            unique=True,
            sqlite_where=text("empresa_id IS NOT NULL"),
        ),
        Index("idx_parametros_busqueda", "codigo", "vigente_desde"),
    )

    id = db.Column(Integer, primary_key=True)
    empresa_id = db.Column(ForeignKey("empresas.id"))
    codigo = db.Column(String(60), nullable=False)
    descripcion = db.Column(String(220), nullable=False)
    valor = db.Column(Numeric(18, 5), nullable=False)
    vigente_desde = db.Column(Date, nullable=False)
    vigente_hasta = db.Column(Date)
    fuente_normativa = db.Column(Text)
    creado_en = db.Column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    @classmethod
    def get_vigente(cls, empresa_id, codigo, fecha):
        statement = (
            select(cls.valor)
            .where(
                cls.codigo == codigo,
                cls.vigente_desde <= fecha,
                or_(cls.vigente_hasta.is_(None), cls.vigente_hasta >= fecha),
                or_(cls.empresa_id == empresa_id, cls.empresa_id.is_(None)),
            )
            .order_by(
                case((cls.empresa_id.is_not(None), 1), else_=0).desc(),
                cls.vigente_desde.desc(),
            )
            .limit(1)
        )
        return db.session.execute(statement).scalar_one_or_none()
