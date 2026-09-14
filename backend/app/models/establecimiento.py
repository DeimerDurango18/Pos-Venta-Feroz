from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .base import BaseModel


class Establecimiento(BaseModel):
    __tablename__ = "establecimientos"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=True)
    nit = Column(String(50), unique=True, nullable=False, index=True)
    nombre = Column(String(200), nullable=False, default="")
    razon_social = Column(String(200))
    tipo_negocio = Column(String(30), default="general")
    regimen = Column(String(50))
    actividad_economica = Column(String(100))
    direccion = Column(String(255))
    ciudad = Column(String(100))
    departamento = Column(String(100))
    telefono = Column(String(50))
    email = Column(String(200))
    modelo_negocio_id = Column(Integer, ForeignKey("modelo_negocio.id"), nullable=True, index=True)
    activo = Column(Boolean, default=True)

    empresa = relationship("Empresa")
    modelo_negocio = relationship("ModeloNegocio")