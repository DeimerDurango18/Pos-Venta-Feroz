from datetime import datetime

from pydantic import BaseModel


class DevolucionDetalleCreate(BaseModel):
    producto_id: int
    cantidad: float


class DevolucionCreate(BaseModel):
    empresa_id: int
    sucursal_id: int
    venta_id: int
    tipo: str = "total"  # total, parcial
    motivo: str | None = None
    reembolso_medio: str = "efectivo"
    detalle: list[DevolucionDetalleCreate] | None = None  # si total, se toma la venta completa


class DevolucionDetalleOut(BaseModel):
    id: int
    producto_id: int
    cantidad: float | None = None
    precio: float | None = None
    subtotal: float | None = None

    class Config:
        from_attributes = True


class DevolucionOut(BaseModel):
    id: int
    venta_id: int
    tipo: str
    motivo: str | None = None
    estado: str
    total_devolucion: float | None = None
    reembolso_medio: str | None = None
    numero_nota: str | None = None
    created_at: datetime | None = None
    detalle: list[DevolucionDetalleOut] = []

    class Config:
        from_attributes = True