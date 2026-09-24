from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
)

from .base import BaseModel


class FacturaRecurrente(BaseModel):
    """Plantilla de facturación periódica. El scheduler genera la venta cada
    período (diaria/semanal/quincenal/mensual) y alimenta cartera."""

    __tablename__ = "facturas_recurrentes"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    periodicidad = Column(String(20), default="mensual")  # diaria | semanal | quincenal | mensual
    dia = Column(Integer, default=1)  # día del mes (1-28) o día de semana (0=domingo..6=sábado)
    descripcion = Column(String(255))
    items = Column(JSON, default=list)  # [{producto_id, cantidad, precio}]
    descuento_global = Column(Numeric(12, 2), default=0)
    tipo = Column(String(30), default="credito")  # credito | contado
    medio_pago = Column(String(50), default="efectivo")
    activo = Column(Boolean, default=True)
    proxima_fecha = Column(Date, nullable=True)
    ultima_fecha = Column(Date, nullable=True)
    ultima_venta_id = Column(Integer, nullable=True)
    observaciones = Column(String(500))