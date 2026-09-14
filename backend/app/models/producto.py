from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .base import BaseModel


class Categoria(BaseModel):
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(150), nullable=False)
    categoria_padre_id = Column(Integer, ForeignKey("categorias.id"), nullable=True)
    activa = Column(Boolean, default=True)

    padre = relationship("Categoria", remote_side=[id])
    productos = relationship("Producto", back_populates="categoria")


class Marca(BaseModel):
    __tablename__ = "marcas"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(150), nullable=False, unique=True)

    productos = relationship("Producto", back_populates="marca")


class Presentacion(BaseModel):
    __tablename__ = "presentaciones"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(150), nullable=False)
    unidad_medida = Column(String(50))  # unidad, peso, volumen, longitud, caja, paquete
    cantidad = Column(Numeric(12, 2), default=1)

    productos = relationship("ProductoPresentacion", back_populates="presentacion")


class Producto(BaseModel):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=True)
    marca_id = Column(Integer, ForeignKey("marcas.id"), nullable=True)
    nombre = Column(String(200), nullable=False)
    descripcion = Column(Text)
    codigo_barras = Column(String(100))
    sku = Column(String(100))
    plu = Column(String(100))
    tipo = Column(String(30), default="unidad")  # unidad, peso, volumen, longitud, caja, paquete
    es_compuesto = Column(Boolean, default=False)
    es_servicio = Column(Boolean, default=False)
    con_vencimiento = Column(Boolean, default=False)
    maneja_lotes = Column(Boolean, default=False)
    maneja_serie = Column(Boolean, default=False)
    imagen = Column(Text)
    ficha_tecnica = Column(Text)
    activo = Column(Boolean, default=True)

    precio_compra = Column(Numeric(12, 2), default=0)
    precio_venta = Column(Numeric(12, 2), default=0)
    precio_mayorista = Column(Numeric(12, 2), default=0)
    precio_minorista = Column(Numeric(12, 2), default=0)
    precio_institucional = Column(Numeric(12, 2), default=0)
    costo = Column(Numeric(12, 2), default=0)
    margen = Column(Numeric(5, 2), default=0)
    margen_minimo = Column(Numeric(5, 2), default=0)
    bloquear_venta_bajo_costo = Column(Boolean, default=False)
    impuesto = Column(Numeric(5, 2), default=0)  # tasa de impuesto % (0 = exento)

    stock_minimo = Column(Numeric(12, 3), default=0)
    stock_maximo = Column(Numeric(12, 3), default=0)
    stock_seguridad = Column(Numeric(12, 3), default=0)
    punto_reorden = Column(Numeric(12, 3), default=0)

    categoria = relationship("Categoria", back_populates="productos")
    marca = relationship("Marca", back_populates="productos")
    presentaciones = relationship(
        "ProductoPresentacion", back_populates="producto", cascade="all, delete-orphan"
    )
    componentes = relationship(
        "ProductoComponente",
        foreign_keys="[ProductoComponente.producto_id]",
        viewonly=True,
    )


class ProductoPresentacion(BaseModel):
    __tablename__ = "producto_presentacion"
    __table_args__ = (UniqueConstraint("producto_id", "presentacion_id"),)

    id = Column(Integer, primary_key=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    presentacion_id = Column(Integer, ForeignKey("presentaciones.id"), nullable=False)
    codigo_barras = Column(String(100))
    precio = Column(Numeric(12, 2), default=0)
    factor = Column(Numeric(12, 2), default=1)

    producto = relationship("Producto", back_populates="presentaciones")
    presentacion = relationship("Presentacion", back_populates="productos")


class ProductoComponente(BaseModel):
    __tablename__ = "producto_componente"

    id = Column(Integer, primary_key=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    componente_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Numeric(12, 3), default=1)

    producto = relationship(
        "Producto", foreign_keys=[producto_id]
    )
    componente = relationship(
        "Producto", foreign_keys=[componente_id]
    )
