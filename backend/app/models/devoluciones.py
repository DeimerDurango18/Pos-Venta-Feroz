from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from .base import BaseModel


class DevolucionVenta(BaseModel):
    __tablename__ = "devoluciones_venta"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    tipo = Column(String(30), default="total")  # total, parcial
    motivo = Column(String(255))
    estado = Column(String(30), default="aplicada")  # aplicada, anulada
    total_devolucion = Column(Numeric(12, 2), default=0)
    reembolso_medio = Column(String(50), default="efectivo")
    numero_nota = Column(String(50))

    detalle = relationship(
        "DevolucionVentaDetalle", back_populates="devolucion", cascade="all, delete-orphan"
    )


class DevolucionVentaDetalle(BaseModel):
    __tablename__ = "devolucion_venta_detalle"

    id = Column(Integer, primary_key=True)
    devolucion_id = Column(Integer, ForeignKey("devoluciones_venta.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Numeric(12, 3), nullable=False)
    precio = Column(Numeric(12, 2), default=0)
    subtotal = Column(Numeric(12, 2), default=0)

    devolucion = relationship("DevolucionVenta", back_populates="detalle")