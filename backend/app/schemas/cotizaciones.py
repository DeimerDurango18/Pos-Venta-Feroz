from datetime import date

from pydantic import BaseModel


class CotizacionDetalleIn(BaseModel):
    producto_id: int
    cantidad: float
    precio: float | None = None
    descuento: float = 0


class CotizacionIn(BaseModel):
    empresa_id: int
    sucursal_id: int
    cliente_id: int | None = None
    cliente_nombre: str | None = None
    cliente_documento: str | None = None
    cliente_telefono: str | None = None
    vence: str | None = None
    observaciones: str | None = None
    descuento_global: float = 0
    detalle: list[CotizacionDetalleIn]


class CotizacionClienteOut(BaseModel):
    id: int
    numero: str | None = None
    cliente_nombre: str | None = None
    cliente_documento: str | None = None
    cliente_telefono: str | None = None
    vence: str | None = None
    estado: str
    subtotal: float | None = None
    descuento_global: float | None = None
    impuesto: float | None = None
    total: float | None = None
    venta_id: int | None = None
    created_at: str | None = None
    detalle: list[dict] = []

    class Config:
        from_attributes = True