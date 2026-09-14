from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
)

from .base import BaseModel


class Autorizacion(BaseModel):
    __tablename__ = "autorizaciones"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    modulo = Column(String(50), nullable=False)
    accion = Column(String(50), nullable=False)
    entidad = Column(String(100))
    entidad_id = Column(Integer)
    solicitante_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    datos = Column(Text)  # JSON con los datos de la solicitud
    estado = Column(String(30), default="pendiente")  # pendiente, aprobada, rechazada
    resolutor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    motivo = Column(String(255))