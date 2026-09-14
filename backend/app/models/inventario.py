from datetime import date

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .base import BaseModel


class Stock(BaseModel):
    __tablename__ = "stock"
    __table_args__ = (UniqueConstraint("producto_id", "sucursal_id"),)

    id = Column(Integer, primary_key=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    existencias = Column(Numeric(12, 3), default=0)
    reservado = Column(Numeric(12, 3), default=0)
    comprometido = Column(Numeric(12, 3), default=0)
    disponible = Column(Numeric(12, 3), default=0)

    producto = relationship("Producto")
    sucursal = relationship("Sucursal")


class MovimientoInventario(BaseModel):
    __tablename__ = "movimientos_inventario"

    id = Column(Integer, primary_key=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    tipo = Column(String(50), nullable=False)  # entrada, salida, ajuste, traslado, devolucion
    cantidad = Column(Numeric(12, 3), nullable=False)  # positiva o negativa
    referencia = Column(String(100))
    motivo = Column(String(255))
    lote = Column(String(100))
    vencimiento = Column(Date)
    saldo = Column(Numeric(12, 3), default=0)  # stock resultante
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    producto = relationship("Producto")


class Lote(BaseModel):
    __tablename__ = "lotes"
    __table_args__ = (UniqueConstraint("producto_id", "codigo"),)

    id = Column(Integer, primary_key=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    codigo = Column(String(100), nullable=False)
    vencimiento = Column(Date)
    cantidad = Column(Numeric(12, 3), default=0)
    activo = Column(Boolean, default=True)

    producto = relationship("Producto")


class StockBodega(BaseModel):
    """Existencias físicas por bodega/ubicación (multibodega)."""
    __tablename__ = "stock_bodega"

    id = Column(Integer, primary_key=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    bodega_id = Column(Integer, ForeignKey("bodegas.id"), nullable=False)
    ubicacion_id = Column(Integer, ForeignKey("ubicaciones.id"), nullable=True)
    existencias = Column(Numeric(12, 3), default=0)
    reservado = Column(Numeric(12, 3), default=0)
    disponible = Column(Numeric(12, 3), default=0)

    producto = relationship("Producto")
    bodega = relationship("Bodega")
    ubicacion = relationship("Ubicacion")


class InventarioTransito(BaseModel):
    """Mercancía enviada entre bodegas de distintas sucursales aún no recibida."""
    __tablename__ = "inventario_transito"

    id = Column(Integer, primary_key=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    origen_sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    origen_bodega_id = Column(Integer, ForeignKey("bodegas.id"), nullable=False)
    destino_sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    destino_bodega_id = Column(Integer, ForeignKey("bodegas.id"), nullable=False)
    cantidad = Column(Numeric(12, 3), nullable=False)
    estado = Column(String(30), default="en_transito")  # en_transito, recibido, cancelado
    referencia = Column(String(100))

    producto = relationship("Producto")
