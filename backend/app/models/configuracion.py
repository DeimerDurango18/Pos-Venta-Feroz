from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    Numeric,
    String,
)

from .base import BaseModel


class Configuracion(BaseModel):
    __tablename__ = "configuraciones"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=True)
    clave = Column(String(100), nullable=False)
    valor = Column(String(255))
    descripcion = Column(String(255))


class Impuesto(BaseModel):
    __tablename__ = "impuestos"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False)
    tasa = Column(Numeric(5, 2), default=0)  # porcentaje, p.ej. 19.00
    activo = Column(Boolean, default=True)