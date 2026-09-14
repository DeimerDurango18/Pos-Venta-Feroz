from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .base import BaseModel


class Repartidor(BaseModel):
    __tablename__ = "repartidores"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    nombre = Column(String(150), nullable=False)
    telefono = Column(String(50))
    placa = Column(String(30))
    vehiculo = Column(String(50))  # moto, bicicleta, carro, a pie
    lat = Column(Float)  # ubicación GPS actual
    lng = Column(Float)
    disponible = Column(String(20), default="disponible")  # disponible, en_ruta, inactivo
    activo = Column(Integer, default=1)


class PedidoUbicacion(BaseModel):
    __tablename__ = "pedido_ubicacion"

    id = Column(Integer, primary_key=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    latitud_destino = Column(Float)
    longitud_destino = Column(Float)
    direccion = Column(String(255))
    repartidor_id = Column(Integer, ForeignKey("repartidores.id"), nullable=True)


class PedidoEstadoTiempo(BaseModel):
    __tablename__ = "pedido_estado_tiempo"

    id = Column(Integer, primary_key=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=False)
    estado = Column(String(30))
    nota = Column(String(255))
    lat = Column(Float)
    lng = Column(Float)


class RutaEntrega(BaseModel):
    __tablename__ = "rutas_entrega"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    nombre = Column(String(150), nullable=False)
    repartidor_id = Column(Integer, ForeignKey("repartidores.id"), nullable=True)
    tarifa = Column(Float, default=0)
    detalle = Column(String(500))