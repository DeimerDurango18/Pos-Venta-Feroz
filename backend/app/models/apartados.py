from datetime import date

from sqlalchemy import (
    Column,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from .base import BaseModel


class Apartado(BaseModel):
    __tablename__ = "apartados"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    numero = Column(String(50))
    subtotal = Column(Numeric(12, 2), default=0)
    total = Column(Numeric(12, 2), default=0)
    abonado = Column(Numeric(12, 2), default=0)
    pendiente = Column(Numeric(12, 2), default=0)
    estado = Column(String(30), default="abierto")  # abierto, pagado, liquidado, cancelado
    fecha_compromiso = Column(Date)
    nota = Column(String(255))
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=True)

    detalle = relationship(
        "ApartadoDetalle", back_populates="apartado", cascade="all, delete-orphan"
    )
    abonos = relationship(
        "ApartadoAbono", back_populates="apartado", cascade="all, delete-orphan"
    )


class ApartadoDetalle(BaseModel):
    __tablename__ = "apartado_detalle"

    id = Column(Integer, primary_key=True)
    apartado_id = Column(Integer, ForeignKey("apartados.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Numeric(12, 3), nullable=False)
    precio = Column(Numeric(12, 2), default=0)
    descuento = Column(Numeric(12, 2), default=0)
    subtotal = Column(Numeric(12, 2), default=0)

    apartado = relationship("Apartado", back_populates="detalle")
    producto = relationship("Producto")


class ApartadoAbono(BaseModel):
    __tablename__ = "apartado_abono"

    id = Column(Integer, primary_key=True)
    apartado_id = Column(Integer, ForeignKey("apartados.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    monto = Column(Numeric(12, 2), nullable=False)
    medio = Column(String(50), default="efectivo")
    referencia = Column(String(100))

    apartado = relationship("Apartado", back_populates="abonos")