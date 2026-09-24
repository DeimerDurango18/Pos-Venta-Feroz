from datetime import date

from pydantic import BaseModel, Field


class RecurrenteItem(BaseModel):
    producto_id: int
    cantidad: float = 1
    precio: float | None = None


class FacturaRecurrenteCreate(BaseModel):
    empresa_id: int
    cliente_id: int | None = None
    sucursal_id: int | None = None
    periodicidad: str = "mensual"  # diaria | semanal | quincenal | mensual
    dia: int = 1
    descripcion: str = ""
    items: list[RecurrenteItem] = Field(min_length=1)
    descuento_global: float = 0
    tipo: str = "credito"  # credito | contado
    medio_pago: str = "efectivo"
    proxima_fecha: date | None = None
    observaciones: str = ""


class FacturaRecurrenteUpdate(BaseModel):
    periodicidad: str | None = None
    dia: int | None = None
    descripcion: str | None = None
    items: list[RecurrenteItem] | None = None
    descuento_global: float | None = None
    tipo: str | None = None
    medio_pago: str | None = None
    activo: bool | None = None
    proxima_fecha: date | None = None
    observaciones: str | None = None


class FacturaRecurrenteOut(BaseModel):
    id: int
    empresa_id: int
    cliente_id: int | None = None
    cliente_nombre: str | None = None
    sucursal_id: int | None = None
    periodicidad: str
    dia: int
    descripcion: str | None = None
    items: list
    descuento_global: float | None = None
    tipo: str
    medio_pago: str | None = None
    activo: bool
    proxima_fecha: date | None = None
    ultima_fecha: date | None = None
    ultima_venta_id: int | None = None
    total_estimado: float | None = None

    class Config:
        from_attributes = True


class RecordatorioEnviar(BaseModel):
    dias_mora: int = 1
    medio: str = "whatsapp"  # whatsapp | email


class RecordatorioOut(BaseModel):
    enviados: int
    clientes: list[dict]