from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)

from .base import BaseModel


class LinkPago(BaseModel):
    """Enlace público de cobro. El comercio crea un link con monto/descripción,
    lo comparte por WhatsApp y la página pública muestra los QR de pago."""

    __tablename__ = "links_pago"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    token = Column(String(24), unique=True, nullable=False, index=True)
    descripcion = Column(String(255))
    monto = Column(Numeric(12, 2), default=0)
    items = Column(JSON, default=list)  # [{producto_id, cantidad, nombre, precio}]
    medio = Column(String(50), default="")  # medio sugerido (vacío = cualquiera)
    estado = Column(String(15), default="activo")  # activo | pagado | cancelado | vencido
    vence = Column(Date, nullable=True)
    confirmado_fecha = Column(DateTime, nullable=True)
    venta_id = Column(Integer, nullable=True)
    visitas = Column(Integer, default=0)
    notificado = Column(Boolean, default=False)