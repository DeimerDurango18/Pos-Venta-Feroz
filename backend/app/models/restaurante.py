from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from .base import BaseModel


class Salon(BaseModel):
    __tablename__ = "salones"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=True)
    nombre = Column(String(150), nullable=False)
    activo = Column(Boolean, default=True)

    mesas = relationship(
        "Mesa", back_populates="salon", cascade="all, delete-orphan"
    )


class Mesa(BaseModel):
    __tablename__ = "mesas"

    id = Column(Integer, primary_key=True)
    salon_id = Column(Integer, ForeignKey("salones.id"), nullable=False)
    numero = Column(String(30))
    nombre = Column(String(30), nullable=False)
    capacidad = Column(Integer, default=4)
    estado = Column(String(30), default="disponible")  # disponible, ocupada, reservada, inactiva
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    invitados = Column(Integer, default=0)

    salon = relationship("Salon", back_populates="mesas")
    comandas = relationship(
        "Comanda", back_populates="mesa", cascade="all, delete-orphan"
    )


class Comanda(BaseModel):
    __tablename__ = "comandas"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    numero = Column(String(50))
    mesa_id = Column(Integer, ForeignKey("mesas.id"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    mesero_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    estado = Column(String(30), default="abierta")  # abierta, cerrada, anulada
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=True)

    mesa = relationship("Mesa", back_populates="comandas")
    detalle = relationship(
        "ComandaDetalle", back_populates="comanda", cascade="all, delete-orphan"
    )


class ComandaDetalle(BaseModel):
    __tablename__ = "comanda_detalle"

    id = Column(Integer, primary_key=True)
    comanda_id = Column(Integer, ForeignKey("comandas.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Numeric(12, 3), nullable=False)
    precio = Column(Numeric(12, 2), default=0)
    preparacion = Column(String(50))
    entregado = Column(Boolean, default=False)
    cortesia = Column(Boolean, default=False)

    comanda = relationship("Comanda", back_populates="detalle")
    producto = relationship("Producto")


class ReservaMesa(BaseModel):
    __tablename__ = "reservas_mesa"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    mesa_id = Column(Integer, ForeignKey("mesas.id"), nullable=False)
    cliente = Column(String(150), nullable=False)
    telefono = Column(String(50))
    inicio = Column(DateTime, default=datetime.now)
    estado = Column(String(30), default="confirmada")  # confirmada, cancelada, completada
    nota = Column(String(255))

    mesa = relationship("Mesa")