from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from .base import BaseModel


class AcuerdoPago(BaseModel):
    __tablename__ = "acuerdos_pago"

    id = Column(Integer, primary_key=True)
    numero = Column(String(50))
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    monto_total = Column(Numeric(12, 2), default=0)
    abonado = Column(Numeric(12, 2), default=0)
    saldo = Column(Numeric(12, 2), default=0)
    estado = Column(String(30), default="activo")  # activo, pagado, vencido, cancelado
    periodicidad = Column(String(30), default="mensual")  # semanal, quincenal, mensual
    fecha_inicio = Column(Date)
    notas = Column(Text)

    cuotas = relationship(
        "CuotaAcuerdo", back_populates="acuerdo", cascade="all, delete-orphan"
    )


class CuotaAcuerdo(BaseModel):
    __tablename__ = "cuotas_acuerdo"

    id = Column(Integer, primary_key=True)
    acuerdo_id = Column(Integer, ForeignKey("acuerdos_pago.id"), nullable=False)
    numero = Column(Integer, default=1)
    monto = Column(Numeric(12, 2), default=0)
    estado = Column(String(30), default="pendiente")  # pendiente, pagada
    fecha_programada = Column(Date)
    fecha_pago = Column(Date)

    acuerdo = relationship("AcuerdoPago", back_populates="cuotas")