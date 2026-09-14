from datetime import date, datetime

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
)
from sqlalchemy.orm import relationship

from .base import BaseModel


class Promocion(BaseModel):
    __tablename__ = "promociones"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    nombre = Column(String(150), nullable=False)
    tipo = Column(String(30), nullable=False)  # porcentaje, valor, 2x1, 3x2
    valor = Column(Numeric(12, 2), default=0)  # % o valor de descuento
    aplica_a = Column(String(30), default="general")  # general, categoria, producto
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=True)
    desde = Column(Date)
    hasta = Column(Date)
    hora_desde = Column(String(5))  # "HH:MM"
    hora_hasta = Column(String(5))
    cantidad_minima = Column(Numeric(12, 3), default=0)  # aplica solo desde esta cantidad
    descripcion = Column(String(255))
    activa = Column(Boolean, default=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)  # None = cualquier cliente

    productos = relationship(
        "PromocionProducto", back_populates="promocion", cascade="all, delete-orphan"
    )


class PromocionProducto(BaseModel):
    __tablename__ = "promocion_producto"

    id = Column(Integer, primary_key=True)
    promocion_id = Column(Integer, ForeignKey("promociones.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)

    promocion = relationship("Promocion", back_populates="productos")


class PrecioHistorico(BaseModel):
    __tablename__ = "precio_historico"

    id = Column(Integer, primary_key=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    campo = Column(String(50), nullable=False)  # precio_venta, precio_compra, costo, etc.
    valor_anterior = Column(Numeric(12, 2), default=0)
    valor_nuevo = Column(Numeric(12, 2), default=0)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)


class DevolucionCompra(BaseModel):
    __tablename__ = "devoluciones_compra"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"), nullable=False)
    compra_id = Column(Integer, ForeignKey("compras.id"), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    numero = Column(String(50))
    tipo = Column(String(30), default="parcial")  # total, parcial
    motivo = Column(String(255))
    total_devolucion = Column(Numeric(12, 2), default=0)
    estado = Column(String(30), default="aplicada")

    detalle = relationship(
        "DevolucionCompraDetalle", back_populates="devolucion", cascade="all, delete-orphan"
    )


class DevolucionCompraDetalle(BaseModel):
    __tablename__ = "devolucion_compra_detalle"

    id = Column(Integer, primary_key=True)
    devolucion_id = Column(Integer, ForeignKey("devoluciones_compra.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Numeric(12, 3), nullable=False)
    costo_unitario = Column(Numeric(12, 2), default=0)
    lote = Column(String(100))
    vencimiento = Column(Date)

    devolucion = relationship("DevolucionCompra", back_populates="detalle")


class CotizacionProveedor(BaseModel):
    __tablename__ = "cotizaciones_proveedor"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    numero = Column(String(50))
    estado = Column(String(30), default="solicitada")  # solicitada, aprobada, vencida
    fecha_validez = Column(Date)
    total_estimado = Column(Numeric(12, 2), default=0)
    notas = Column(Text)

    detalle = relationship(
        "CotizacionProveedorDetalle", back_populates="cotizacion", cascade="all, delete-orphan"
    )


class CotizacionProveedorDetalle(BaseModel):
    __tablename__ = "cotizacion_proveedor_detalle"

    id = Column(Integer, primary_key=True)
    cotizacion_id = Column(Integer, ForeignKey("cotizaciones_proveedor.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Numeric(12, 3), nullable=False)
    costo_unitario = Column(Numeric(12, 2), default=0)

    cotizacion = relationship("CotizacionProveedor", back_populates="detalle")


class ConteoFisico(BaseModel):
    __tablename__ = "conteos_fisicos"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    numero = Column(String(50))
    tipo = Column(String(30), default="fisico")  # fisico, ciclico
    observacion = Column(String(255))
    estado = Column(String(30), default="abierto")  # abierto, liquidado, cancelado

    detalle = relationship(
        "ConteoFisicoDetalle", back_populates="conteo", cascade="all, delete-orphan"
    )


class ConteoFisicoDetalle(BaseModel):
    __tablename__ = "conteo_fisico_detalle"

    id = Column(Integer, primary_key=True)
    conteo_id = Column(Integer, ForeignKey("conteos_fisicos.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    esperado = Column(Numeric(12, 3), default=0)
    contado = Column(Numeric(12, 3), default=0)
    diferencia = Column(Numeric(12, 3), default=0)

    conteo = relationship("ConteoFisico", back_populates="detalle")


class AuditoriaLog(BaseModel):
    __tablename__ = "auditoria_log"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    modulo = Column(String(50), nullable=False)
    accion = Column(String(50), nullable=False)
    entidad = Column(String(100))
    entidad_id = Column(Integer)
    detalle = Column(String(500))


class MetaVendedor(BaseModel):
    __tablename__ = "metas_vendedor"

    id = Column(Integer, primary_key=True)
    vendedor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    periodo = Column(String(20), nullable=False)  # "YYYY-MM"
    meta_ventas = Column(Numeric(12, 2), default=0)
    meta_utilidad = Column(Numeric(12, 2), default=0)


class ReglaComision(BaseModel):
    __tablename__ = "reglas_comision"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    vendedor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=True)
    porcentaje = Column(Numeric(5, 2), default=0)


class ErrorLog(BaseModel):
    __tablename__ = "error_log"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    modulo = Column(String(100))
    endpoint = Column(String(250))
    metodo = Column(String(10))
    mensaje = Column(Text)
    traceback = Column(Text)
    resuelto = Column(Boolean, default=False)


class PrecioCompetencia(BaseModel):
    __tablename__ = "precio_competencia"

    id = Column(Integer, primary_key=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    competidor = Column(String(150), nullable=False)
    precio = Column(Numeric(12, 2), default=0)
    fecha = Column(Date)
    notas = Column(String(255))