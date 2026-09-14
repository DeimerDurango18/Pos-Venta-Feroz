from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
)
from sqlalchemy.orm import relationship

from .base import BaseModel


class Rol(BaseModel):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False, unique=True)
    descripcion = Column(String(255))
    es_sistema = Column(Boolean, default=False)

    permisos = relationship(
        "Permiso",
        secondary="rol_permiso",
        back_populates="roles",
    )
    usuarios = relationship("Usuario", back_populates="rol")


class Permiso(BaseModel):
    __tablename__ = "permisos"

    id = Column(Integer, primary_key=True)
    modulo = Column(String(100), nullable=False)
    accion = Column(String(100), nullable=False)  # crear, leer, editar, eliminar, autorizar
    descripcion = Column(String(255))

    roles = relationship(
        "Rol",
        secondary="rol_permiso",
        back_populates="permisos",
    )


rol_permiso = Table(
    "rol_permiso",
    BaseModel.metadata,
    Column("rol_id", Integer, ForeignKey("roles.id"), primary_key=True),
    Column("permiso_id", Integer, ForeignKey("permisos.id"), primary_key=True),
)


class Usuario(BaseModel):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=True)
    rol_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    nombre = Column(String(150), nullable=False)
    username = Column(String(100), nullable=False, unique=True)
    email = Column(String(200), unique=True)
    password_hash = Column(String(255), nullable=False)
    activo = Column(Boolean, default=True)
    es_admin = Column(Boolean, default=False)
    vendedor = Column(Boolean, default=False)
    debe_cambiar_password = Column(Boolean, default=False)

    rol = relationship("Rol", back_populates="usuarios")


class Sesion(BaseModel):
    __tablename__ = "sesiones"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    token = Column(String(255), nullable=False)
    activa = Column(Boolean, default=True)
    ip = Column(String(50))
    user_agent = Column(String(255))

    usuario = relationship("Usuario")


class RestablecerClave(BaseModel):
    __tablename__ = "restablecer_clave"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    token = Column(String(255), nullable=False, index=True)
    usado = Column(Boolean, default=False)
    expira_en = Column(DateTime(timezone=True))

    usuario = relationship("Usuario")
