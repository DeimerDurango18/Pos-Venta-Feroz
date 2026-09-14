from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from ..database import Base


class TarjetaTransaccion(Base):
    __tablename__ = "tarjeta_transacciones"

    id = Column(Integer, primary_key=True)
    monto = Column(Numeric(12, 2), nullable=False)
    marca = Column(String(30), default="Visa")
    ultimos4 = Column(String(4))
    estado = Column(String(20), default="solicitada")  # aprobada, rechazada, confirmada, reversada
    codigo_autorizacion = Column(String(20))
    referencia = Column(String(40))
    venta_id = Column(Integer, ForeignKey("ventas.id"))
    created_at = Column(DateTime, default=datetime.now)

    venta = relationship("Venta")