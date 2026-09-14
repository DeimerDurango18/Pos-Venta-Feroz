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

from .base import BaseModel


class Cupon(BaseModel):
    __tablename__ = "cupones"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    codigo = Column(String(50), nullable=False)
    tipo = Column(String(20), default="valor")  # porcentaje, valor
    valor = Column(Numeric(12, 2), default=0)
    vigencia_desde = Column(Date)
    vigencia_hasta = Column(Date)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)  # None = cualquier cliente
    usos_max = Column(Integer, default=1)
    usos_actuales = Column(Integer, default=0)
    activo = Column(Boolean, default=True)
    descripcion = Column(String(255))

    __table_args__ = (UniqueConstraint("empresa_id", "codigo", name="uq_cupon_codigo"),)


class Bono(BaseModel):
    __tablename__ = "bonos"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    codigo = Column(String(50), nullable=False)
    valor_total = Column(Numeric(12, 2), default=0)
    saldo = Column(Numeric(12, 2), default=0)
    motivo = Column(String(255))
    vencimiento = Column(Date)
    estado = Column(String(30), default="activo")  # activo, agotado, cancelado


class TarjetaRegalo(BaseModel):
    __tablename__ = "tarjetas_regalo"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    codigo = Column(String(50), nullable=False)
    saldo = Column(Numeric(12, 2), default=0)
    estado = Column(String(30), default="activa")  # activa, agotada, cancelada


class PuntosMovimiento(BaseModel):
    __tablename__ = "puntos_movimiento"

    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    delta = Column(Integer, default=0)
    saldo_anterior = Column(Integer, default=0)
    saldo_nuevo = Column(Integer, default=0)
    motivo = Column(String(255))
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)