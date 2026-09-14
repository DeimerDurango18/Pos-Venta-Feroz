from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .base import BaseModel


class Moneda(BaseModel):
    __tablename__ = "monedas"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    codigo = Column(String(10), nullable=False)  # USD, EUR, COP...
    nombre = Column(String(50))
    simbolo = Column(String(10))
    tasa_cambio = Column(Numeric(12, 4), default=1)  # cantidad por 1 unidad de la moneda base
    activa = Column(Boolean, default=True)


class Balanza(BaseModel):
    __tablename__ = "balanzas"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=True)
    nombre = Column(String(100), nullable=False)
    modelo = Column(String(100))
    puerto = Column(String(50))  # COM1, /dev/ttyUSB0...
    formato = Column(String(30), default="SAP")  # SAP, CAS, DIGI...
    tasa = Column(Integer, default=1)
    activa = Column(Boolean, default=True)


class CuentaBanco(BaseModel):
    __tablename__ = "cuentas_banco"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    banco = Column(String(100), nullable=False)
    numero_cuenta = Column(String(50))
    tipo = Column(String(30), default="corriente")  # corriente, ahorro
    titular = Column(String(150))
    saldo_inicial = Column(Numeric(12, 2), default=0)
    activa = Column(Boolean, default=True)

    movimientos = relationship(
        "MovimientoBanco", back_populates="cuenta", cascade="all, delete-orphan"
    )


class MovimientoBanco(BaseModel):
    __tablename__ = "movimientos_banco"

    id = Column(Integer, primary_key=True)
    cuenta_id = Column(Integer, ForeignKey("cuentas_banco.id"), nullable=False)
    tipo = Column(String(30), nullable=False)  # ingreso, egreso
    monto = Column(Numeric(12, 2), nullable=False)
    concepto = Column(String(255))
    referencia = Column(String(100))
    fecha_movimiento = Column(Date)
    conciliado = Column(Boolean, default=False)

    cuenta = relationship("CuentaBanco", back_populates="movimientos")


class Webhook(BaseModel):
    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    evento = Column(String(100), nullable=False)  # venta.creada, producto.actualizado...
    url = Column(String(500), nullable=False)
    token = Column(String(255))
    activo = Column(Boolean, default=True)


class MensajeWhatsapp(BaseModel):
    __tablename__ = "mensajes_whatsapp"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    telefono = Column(String(30))
    plantilla = Column(String(100), default="recibo_venta")
    contenido = Column(Text)
    estado = Column(String(30), default="enviado")  # enviado, fallido
    referencia = Column(String(100))


class BackupRegistro(BaseModel):
    __tablename__ = "backups"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(200))
    tabla = Column(String(100))
    tipo = Column(String(30), default="automatico")  # manual, automatico, restauracion
    tamano = Column(Integer, default=0)
    detalle = Column(Text, default="{}")