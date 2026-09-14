from datetime import datetime

from pydantic import BaseModel


class AbonoClienteCreate(BaseModel):
    empresa_id: int
    cliente_id: int
    venta_id: int | None = None
    monto: float
    medio: str = "efectivo"
    referencia: str | None = None
    observacion: str | None = None


class AbonoClienteOut(BaseModel):
    id: int
    cliente_id: int
    venta_id: int | None = None
    monto: float | None = None
    medio: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True