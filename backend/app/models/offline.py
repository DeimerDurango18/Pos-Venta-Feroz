from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, Numeric, String

from ..database import Base


class PendienteSincronizacion(Base):
    __tablename__ = "pendientes_sincronizacion"

    id = Column(Integer, primary_key=True)
    cliente_uuid = Column(String(64), index=True)
    tipo = Column(String(30), default="venta")  # venta
    payload = Column(JSON)
    estado = Column(String(20), default="pendiente")  # pendiente, sincronizada, error
    error = Column(String(255))
    resultado_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    sincronizada_at = Column(DateTime)


class PantallaCliente(Base):
    __tablename__ = "pantalla_cliente"

    id = Column(Integer, primary_key=True)  # fila fija id = 1
    items = Column(JSON, default=list)
    subtotal = Column(Numeric(12, 2), default=0)
    descuento = Column(Numeric(12, 2), default=0)
    impuesto = Column(Numeric(12, 2), default=0)
    propina = Column(Numeric(12, 2), default=0)
    total = Column(Numeric(12, 2), default=0)
    mensaje = Column(String(120))
    updated_at = Column(DateTime)