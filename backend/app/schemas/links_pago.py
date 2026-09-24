from datetime import date

from pydantic import BaseModel, Field


class LinkItem(BaseModel):
    producto_id: int | None = None
    nombre: str = ""
    cantidad: float = 1
    precio: float | None = None


class LinkPagoCreate(BaseModel):
    empresa_id: int
    cliente_id: int | None = None
    descripcion: str = ""
    monto: float = 0
    items: list[LinkItem] = []
    medio: str = ""
    vence_dias: int | None = None


class LinkPagoOut(BaseModel):
    id: int
    empresa_id: int
    usuario_id: int
    cliente_id: int | None = None
    cliente_nombre: str | None = None
    token: str
    descripcion: str | None = None
    monto: float | None = None
    items: list | None = None
    medio: str | None = None
    estado: str
    vence: date | None = None
    confirmado_fecha: str | None = None
    venta_id: int | None = None
    visitas: int | None = None
    url: str | None = None
    created_at: str | None = None

    class Config:
        from_attributes = True