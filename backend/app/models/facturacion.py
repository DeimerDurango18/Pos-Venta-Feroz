from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .base import BaseModel


class ResolucionFacturacion(BaseModel):
    __tablename__ = "resoluciones_facturacion"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    resolucion = Column(String(50), nullable=False)  # número de la resolución DIAN
    prefijo = Column(String(20), nullable=False)  # ej. FV, NC, ND
    tipo_documento = Column(String(50), nullable=False)  # factura, nota_credito, nota_debito, documento_equivalente, documento_pos
    rango_inicial = Column(Integer, nullable=False)
    rango_final = Column(Integer, nullable=False)
    numero_actual = Column(Integer, default=0)
    fecha_inicio = Column(Date)
    fecha_vencimiento = Column(Date)
    activa = Column(Boolean, default=True)
    tecnica = Column(String(30), default="habilitacion")

    ventas_emitir = relationship(
        "DocumentoFiscal", back_populates="resolucion", lazy="dynamic"
    )

    __table_args__ = (UniqueConstraint("empresa_id", "prefijo", name="uq_resolucion_prefijo"),)


class DocumentoFiscal(BaseModel):
    __tablename__ = "documentos_fiscales"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=True)
    resolucion_id = Column(Integer, ForeignKey("resoluciones_facturacion.id"), nullable=True)
    referencia = Column(String(50))  # documento fiscal que se está anulando/corrigiendo
    tipo_documento = Column(String(50), nullable=False)  # factura, nota_credito, nota_debito, documento_equivalente, documento_pos
    prefijo = Column(String(20))
    consecutivo = Column(Integer)
    numero = Column(String(50))
    fecha_emision = Column(String(30))
    cufe = Column(String(128))  # Código Único de Facturación Electrónica (SHA-384, 96 hex)
    xml_ubl = Column(Text)  # XML UBL 2.1 del documento
    qr = Column(Text)
    estado_dian = Column(String(30), default="pendiente")  # pendiente, enviado, aprobado, rechazado
    fecha_envio = Column(DateTime(timezone=True))
    respuesta_dian = Column(Text)
    motivo_rechazo = Column(String(255))
    anulado = Column(Boolean, default=False)
    motivo_anulacion = Column(String(255))
    monto = Column(Numeric(12, 2), default=0)
    concepto = Column(String(255))

    resolucion = relationship("ResolucionFacturacion", back_populates="ventas_emitir")
    venta = relationship("Venta")