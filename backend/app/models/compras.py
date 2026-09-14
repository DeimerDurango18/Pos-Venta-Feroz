from datetime import date

from sqlalchemy import (
    Column,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .base import BaseModel


class OrdenCompra(BaseModel):
    __tablename__ = "ordenes_compra"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    numero = Column(String(50))
    estado = Column(String(30), default="solicitada")  # solicitada, aprobada, recibida, cancelada
    fecha_requerida = Column(Date)
    total_estimado = Column(Numeric(12, 2), default=0)
    notas = Column(Text)

    detalle = relationship(
        "OrdenCompraDetalle", back_populates="orden", cascade="all, delete-orphan"
    )


class OrdenCompraDetalle(BaseModel):
    __tablename__ = "orden_compra_detalle"

    id = Column(Integer, primary_key=True)
    orden_id = Column(Integer, ForeignKey("ordenes_compra.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Numeric(12, 3), nullable=False)
    costo_unitario = Column(Numeric(12, 2), default=0)

    orden = relationship("OrdenCompra", back_populates="detalle")


class Compra(BaseModel):
    __tablename__ = "compras"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    orden_compra_id = Column(Integer, ForeignKey("ordenes_compra.id"), nullable=True)
    numero = Column(String(50))
    tipo = Column(String(30), default="contado")  # contado, credito
    estado = Column(String(30), default="pendiente")  # pendiente, recibida, anulada
    subtotal = Column(Numeric(12, 2), default=0)
    impuesto = Column(Numeric(12, 2), default=0)
    otros_costos = Column(Numeric(12, 2), default=0)
    total = Column(Numeric(12, 2), default=0)
    nota = Column(String(255))
    fecha_recepcion = Column(Date)

    detalle = relationship(
        "CompraDetalle", back_populates="compra", cascade="all, delete-orphan"
    )


class CompraDetalle(BaseModel):
    __tablename__ = "compra_detalle"

    id = Column(Integer, primary_key=True)
    compra_id = Column(Integer, ForeignKey("compras.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Numeric(12, 3), nullable=False)
    costo_unitario = Column(Numeric(12, 2), default=0)
    subtotal = Column(Numeric(12, 2), default=0)

    compra = relationship("Compra", back_populates="detalle")


class CuentaPagar(BaseModel):
    __tablename__ = "cuentas_pagar"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"), nullable=False)
    compra_id = Column(Integer, ForeignKey("compras.id"), nullable=True)
    monto_total = Column(Numeric(12, 2), default=0)
    saldo = Column(Numeric(12, 2), default=0)
    estado = Column(String(30), default="pendiente")  # pendiente, pagada
    fecha_vencimiento = Column(Date)


class AbonoProveedor(BaseModel):
    __tablename__ = "abonos_proveedor"

    id = Column(Integer, primary_key=True)
    cuenta_id = Column(Integer, ForeignKey("cuentas_pagar.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    monto = Column(Numeric(12, 2), nullable=False)
    medio = Column(String(50), default="efectivo")
    referencia = Column(String(100))
    observacion = Column(String(255))