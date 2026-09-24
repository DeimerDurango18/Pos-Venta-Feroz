from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from .base import BaseModel


class CotizacionCliente(BaseModel):
    __tablename__ = "cotizaciones_cliente"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    numero = Column(String(50))
    cliente_nombre = Column(String(200))
    cliente_documento = Column(String(50))
    cliente_telefono = Column(String(50))
    vence = Column(Date, nullable=True)
    estado = Column(String(30), default="vigente")  # vigente, vencida, convertida, anulada
    observaciones = Column(Text)
    subtotal = Column(Numeric(12, 2), default=0)
    descuento_global = Column(Numeric(12, 2), default=0)
    impuesto = Column(Numeric(12, 2), default=0)
    total = Column(Numeric(12, 2), default=0)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=True)

    detalle = relationship(
        "CotizacionClienteDetalle",
        back_populates="cotizacion",
        cascade="all, delete-orphan",
    )


class CotizacionClienteDetalle(BaseModel):
    __tablename__ = "cotizaciones_cliente_detalle"

    id = Column(Integer, primary_key=True)
    cotizacion_id = Column(Integer, ForeignKey("cotizaciones_cliente.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    nombre = Column(String(250))
    precio_unitario = Column(Numeric(12, 2), nullable=False)
    cantidad = Column(Numeric(12, 3), nullable=False)
    descuento = Column(Numeric(12, 2), default=0)
    impuesto_pct = Column(Numeric(5, 2), default=0)
    subtotal = Column(Numeric(12, 2), default=0)

    cotizacion = relationship("CotizacionCliente", back_populates="detalle")
    producto = relationship("Producto")