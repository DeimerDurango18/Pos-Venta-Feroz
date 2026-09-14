from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from .base import BaseModel


class AbonoCliente(BaseModel):
    __tablename__ = "abonos_cliente"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    monto = Column(Numeric(12, 2), nullable=False)
    medio = Column(String(50), default="efectivo")
    referencia = Column(String(100))
    observacion = Column(String(255))

    cliente = relationship("Cliente")