from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from .base import BaseModel


class Cliente(BaseModel):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    nombre = Column(String(200), nullable=False)
    tipo_documento = Column(String(30))
    documento = Column(String(50))
    email = Column(String(200))
    telefono = Column(String(50))
    direccion = Column(String(255))
    ciudad = Column(String(100))
    tipo = Column(String(30), default="ocasional")  # ocasional, frecuente, mayorista
    limite_credito = Column(Numeric(12, 2), default=0)
    creditos = Column(Numeric(12, 2), default=0)
    puntos = Column(Integer, default=0)
    activo = Column(Boolean, default=True)

    empresa = relationship("Empresa")


class Proveedor(BaseModel):
    __tablename__ = "proveedores"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    nombre = Column(String(200), nullable=False)
    nit = Column(String(50))
    contacto = Column(String(150))
    email = Column(String(200))
    telefono = Column(String(50))
    direccion = Column(String(255))
    ciudad = Column(String(100))
    activo = Column(Boolean, default=True)

    empresa = relationship("Empresa")
