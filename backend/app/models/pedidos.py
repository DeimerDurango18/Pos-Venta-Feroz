from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from .base import BaseModel


class Pedido(BaseModel):
    __tablename__ = "pedidos"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    repartidor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    numero = Column(String(50))
    tipo = Column(String(30), default="mostrador")  # mostrador, domicilio
    estado = Column(String(30), default="pendiente")  # pendiente, en_preparacion, listo, entregado, cancelado
    total = Column(Numeric(12, 2), default=0)
    direccion_entrega = Column(String(255))
    costo_domicilio = Column(Numeric(12, 2), default=0)
    estado_domicilio = Column(String(30))  # pendiente, en_ruta, entregado, cancelado
    plato_principal = Column(Integer, ForeignKey("productos.id"), nullable=True)
    nota = Column(String(255))

    detalle = relationship(
        "PedidoDetalle", back_populates="pedido", cascade="all, delete-orphan"
    )


class PedidoDetalle(BaseModel):
    __tablename__ = "pedido_detalle"

    id = Column(Integer, primary_key=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Numeric(12, 3), nullable=False)
    precio = Column(Numeric(12, 2), default=0)
    subtotal = Column(Numeric(12, 2), default=0)

    pedido = relationship("Pedido", back_populates="detalle")
    producto = relationship("Producto")