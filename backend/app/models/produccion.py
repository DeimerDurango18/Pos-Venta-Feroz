from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from .base import BaseModel


class ProduccionOrden(BaseModel):
    __tablename__ = "produccion_ordenes"

    id = Column(Integer, primary_key=True)
    numero = Column(String(50))
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    cantidad = Column(Numeric(12, 3), default=1)
    costo_total = Column(Numeric(12, 2), default=0)
    estado = Column(String(30), default="procesada")  # procesada, cancelada

    detalle = relationship(
        "ProduccionDetalle", back_populates="produccion", cascade="all, delete-orphan"
    )


class ProduccionDetalle(BaseModel):
    __tablename__ = "produccion_detalle"

    id = Column(Integer, primary_key=True)
    produccion_id = Column(Integer, ForeignKey("produccion_ordenes.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)  # materia prima
    cantidad = Column(Numeric(12, 3), nullable=False)
    costo_unitario = Column(Numeric(12, 2), default=0)

    produccion = relationship("ProduccionOrden", back_populates="detalle")