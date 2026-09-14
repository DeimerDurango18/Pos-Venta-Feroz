from sqlalchemy import Boolean, Column, Integer, String, Text

from .base import BaseModel


class ModeloNegocio(BaseModel):
    __tablename__ = "modelo_negocio"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(String(255))
    modulos = Column(Text, default="[]")
    activo = Column(Boolean, default=True)