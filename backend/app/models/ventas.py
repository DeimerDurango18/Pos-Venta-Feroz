from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from .base import BaseModel


class Venta(BaseModel):
    __tablename__ = "ventas"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    caja_id = Column(Integer, ForeignKey("cajas.id"), nullable=True)
    punto_venta_id = Column(Integer, ForeignKey("puntos_venta.id"), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    numero = Column(String(50))
    tipo = Column(String(30), default="contado")  # contado, credito
    estado = Column(String(30), default="completada")  # completada, suspendida, anulada
    subtotal = Column(Numeric(12, 2), default=0)
    descuento = Column(Numeric(12, 2), default=0)
    impuesto = Column(Numeric(12, 2), default=0)
    total = Column(Numeric(12, 2), default=0)
    costo_total = Column(Numeric(12, 2), default=0)
    propina = Column(Numeric(12, 2), default=0)
    saldo = Column(Numeric(12, 2), default=0)  # por cobrar para ventas a crédito
    nota = Column(String(255))

    detalle = relationship(
        "VentaDetalle", back_populates="venta", cascade="all, delete-orphan"
    )
    pagos = relationship(
        "VentaPago", back_populates="venta", cascade="all, delete-orphan"
    )


class VentaDetalle(BaseModel):
    __tablename__ = "venta_detalle"

    id = Column(Integer, primary_key=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    presentacion_id = Column(Integer, ForeignKey("presentaciones.id"), nullable=True)
    cantidad = Column(Numeric(12, 3), nullable=False)
    precio = Column(Numeric(12, 2), nullable=False)
    costo = Column(Numeric(12, 2), default=0)
    descuento = Column(Numeric(12, 2), default=0)
    impuesto = Column(Numeric(12, 2), default=0)
    subtotal = Column(Numeric(12, 2), default=0)
    lote = Column(String(100))
    vencimiento = Column(String(30))

    venta = relationship("Venta", back_populates="detalle")
    producto = relationship("Producto")


class VentaPago(BaseModel):
    __tablename__ = "venta_pago"

    id = Column(Integer, primary_key=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=False)
    medio = Column(String(50), nullable=False)  # efectivo, tarjeta, transferencia, QR, nequi, etc.
    monto = Column(Numeric(12, 2), nullable=False)
    referencia = Column(String(100))
    cambio = Column(Numeric(12, 2), default=0)

    venta = relationship("Venta", back_populates="pagos")


class AperturaCaja(BaseModel):
    __tablename__ = "aperturas_caja"

    id = Column(Integer, primary_key=True)
    caja_id = Column(Integer, ForeignKey("cajas.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    saldo_inicial = Column(Numeric(12, 2), default=0)
    saldo_cierre = Column(Numeric(12, 2))
    hora_apertura = Column(String(30))
    hora_cierre = Column(String(30))
    estado = Column(String(30), default="abierta")  # abierta, cerrada

    caja = relationship("Caja")


class MovimientoCaja(BaseModel):
    __tablename__ = "movimientos_caja"

    id = Column(Integer, primary_key=True)
    apertura_caja_id = Column(Integer, ForeignKey("aperturas_caja.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    tipo = Column(String(50), nullable=False)  # ingreso, egreso, gasto, retiro
    concepto = Column(String(255))
    monto = Column(Numeric(12, 2), nullable=False)
    medio = Column(String(50), default="efectivo")

    apertura = relationship("AperturaCaja")


class ArqueoCaja(BaseModel):
    __tablename__ = "arqueos_caja"

    id = Column(Integer, primary_key=True)
    apertura_caja_id = Column(Integer, ForeignKey("aperturas_caja.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    contado_efectivo = Column(Numeric(12, 2), default=0)
    contado_esperado = Column(Numeric(12, 2), default=0)
    diferencia = Column(Numeric(12, 2), default=0)
    observacion = Column(String(255))

    apertura = relationship("AperturaCaja")


class Gasto(BaseModel):
    __tablename__ = "gastos"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    categoria = Column(String(100))
    concepto = Column(String(255))
    monto = Column(Numeric(12, 2), nullable=False)
    medio = Column(String(50), default="efectivo")
