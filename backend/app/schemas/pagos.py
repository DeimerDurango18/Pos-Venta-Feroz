from datetime import datetime

from pydantic import BaseModel


class TarjetaAutorizar(BaseModel):
    monto: float
    marca: str = "Visa"
    ultimos4: str | None = None


class TarjetaTransaccionOut(BaseModel):
    id: int
    monto: float
    marca: str
    ultimos4: str | None = None
    estado: str
    codigo_autorizacion: str | None = None
    referencia: str | None = None
    venta_id: int | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}