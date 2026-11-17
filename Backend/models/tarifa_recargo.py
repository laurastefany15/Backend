from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    case,
    or_,
    select,
    text,
)

from extensions import db


class TarifaRecargo(db.Model):
    __tablename__ = "tarifas_recargo"
    __table_args__ = (
        CheckConstraint("porcentaje >= 0", name="ck_tarifa_porcentaje"),
        CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta >= vigente_desde",
            name="ck_tarifa_vigencia",
        ),
        Index(
            "uq_tarifa_nacional",
            "tipo_codigo",
            "vigente_desde",
            unique=True,
            sqlite_where=text("empresa_id IS NULL"),
        ),
        Index(
            "uq_tarifa_empresa",
            "empresa_id",
            "tipo_codigo",
            "vigente_desde",
            unique=True,
            sqlite_where=text("empresa_id IS NOT NULL"),
        ),
        Index("idx_tarifas_busqueda", "tipo_codigo", "vigente_desde"),
    )

    id = db.Column(Integer, primary_key=True)
    empresa_id = db.Column(ForeignKey("empresas.id"))
    tipo_codigo = db.Column(ForeignKey("tipos_recargo.codigo"), nullable=False)
    porcentaje = db.Column(Numeric(8, 4), nullable=False)
    vigente_desde = db.Column(Date, nullable=False)
    vigente_hasta = db.Column(Date)
    fuente_normativa = db.Column(Text)

    @classmethod
    def get_vigente(cls, empresa_id, tipo_codigo, fecha):
        statement = (
            select(cls.porcentaje)
            .where(
                cls.tipo_codigo == tipo_codigo,
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
