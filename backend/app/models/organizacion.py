from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .base import BaseModel


class Empresa(BaseModel):
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(200), nullable=False)
    nit = Column(String(50), unique=True, nullable=False)
    tipo_negocio = Column(String(30), nullable=False, default="general")
    razon_social = Column(String(200))
    direccion = Column(String(255))
    telefono = Column(String(50))
    email = Column(String(200))
    regimen = Column(String(50))
    logo = Column(Text)
    activa = Column(Boolean, default=True)

    sucursales = relationship(
        "Sucursal", back_populates="empresa", cascade="all, delete-orphan"
    )


class Sucursal(BaseModel):
    __tablename__ = "sucursales"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    nombre = Column(String(200), nullable=False)
    codigo = Column(String(30))
    direccion = Column(String(255))
    telefono = Column(String(50))
    ciudad = Column(String(100))
    activa = Column(Boolean, default=True)

    empresa = relationship("Empresa", back_populates="sucursales")
    puntos_venta = relationship("PuntoVenta", back_populates="sucursal")


class Bodega(BaseModel):
    __tablename__ = "bodegas"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    nombre = Column(String(150), nullable=False)
    codigo = Column(String(30))
    direccion = Column(String(255))
    activa = Column(Boolean, default=True)

    sucursal = relationship("Sucursal")
    ubicaciones = relationship(
        "Ubicacion", back_populates="bodega", cascade="all, delete-orphan"
    )


class Ubicacion(BaseModel):
    __tablename__ = "ubicaciones"

    id = Column(Integer, primary_key=True)
    bodega_id = Column(Integer, ForeignKey("bodegas.id"), nullable=False)
    nombre = Column(String(150), nullable=False)
    codigo = Column(String(30))
    activa = Column(Boolean, default=True)

    bodega = relationship("Bodega", back_populates="ubicaciones")


class PuntoVenta(BaseModel):
    __tablename__ = "puntos_venta"

    id = Column(Integer, primary_key=True)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    nombre = Column(String(200), nullable=False)
    tipo = Column(String(30))  # POS, mostrador, etc.
    activo = Column(Boolean, default=True)

    sucursal = relationship("Sucursal", back_populates="puntos_venta")
    cajas = relationship("Caja", back_populates="punto_venta")


class Caja(BaseModel):
    __tablename__ = "cajas"

    id = Column(Integer, primary_key=True)
    punto_venta_id = Column(Integer, ForeignKey("puntos_venta.id"), nullable=False)
    nombre = Column(String(100), nullable=False)
    codigo = Column(String(30))
    activa = Column(Boolean, default=True)
    saldo_inicial = Column(Numeric(12, 2), default=0)
    es_principal = Column(Boolean, default=False, nullable=False)

    punto_venta = relationship("PuntoVenta", back_populates="cajas")
