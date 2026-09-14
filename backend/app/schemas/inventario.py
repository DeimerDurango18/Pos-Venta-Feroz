from datetime import date, datetime

from pydantic import BaseModel


class StockOut(BaseModel):
    id: int
    producto_id: int
    sucursal_id: int
    existencias: float | None = None
    reservado: float | None = None
    disponible: float | None = None

    class Config:
        from_attributes = True


class MovimientoInventarioCreate(BaseModel):
    producto_id: int
    sucursal_id: int
    tipo: str  # entrada, salida, ajuste, traslado
    cantidad: float
    motivo: str | None = None
    referencia: str | None = None
    lote: str | None = None
    vencimiento: date | None = None


class MovimientoInventarioOut(BaseModel):
    id: int
    producto_id: int
    sucursal_id: int
    tipo: str
    cantidad: float | None = None
    motivo: str | None = None
    referencia: str | None = None
    saldo: float | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class AjusteStock(BaseModel):
    producto_id: int
    sucursal_id: int
    existencias: float  # nuevo valor absoluto
    motivo: str


class TransferenciaStock(BaseModel):
    producto_id: int
    origen_sucursal_id: int
    destino_sucursal_id: int
    cantidad: float
    motivo: str | None = None


# ---------- Multibodega ----------
class BodegaCreate(BaseModel):
    empresa_id: int = 1
    sucursal_id: int = 1
    nombre: str
    codigo: str | None = None
    direccion: str | None = None
    activa: bool = True


class BodegaOut(BaseModel):
    id: int
    empresa_id: int
    sucursal_id: int
    nombre: str
    codigo: str | None = None
    direccion: str | None = None
    activa: bool | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class UbicacionCreate(BaseModel):
    bodega_id: int
    nombre: str
    codigo: str | None = None


class UbicacionOut(BaseModel):
    id: int
    bodega_id: int
    nombre: str
    codigo: str | None = None
    activa: bool | None = None

    class Config:
        from_attributes = True


class StockBodegaMovimiento(BaseModel):
    producto_id: int
    bodega_id: int
    ubicacion_id: int | None = None
    tipo: str  # entrada, salida, ajuste, reubicar
    cantidad: float
    motivo: str | None = None


class StockBodegaOut(BaseModel):
    id: int
    producto_id: int
    sucursal_id: int
    bodega_id: int
    ubicacion_id: int | None = None
    existencias: float | None = None
    disponible: float | None = None

    class Config:
        from_attributes = True


class TransferenciaBodegaCreate(BaseModel):
    producto_id: int
    cantidad: float
    origen_bodega_id: int
    destino_bodega_id: int
    origen_ubicacion_id: int | None = None
    destino_ubicacion_id: int | None = None
    motivo: str | None = None


class RecibirTransito(BaseModel):
    transferencia_id: int


# ---------- Lotes ----------
class LoteCreate(BaseModel):
    producto_id: int
    codigo: str
    vencimiento: date | None = None
    cantidad: float = 0


class LoteMovimiento(BaseModel):
    lote_id: int
    cantidad: float
    motivo: str | None = None


class LoteOut(BaseModel):
    id: int
    producto_id: int
    codigo: str
    vencimiento: date | None = None
    cantidad: float | None = None
    activo: bool | None = None

    class Config:
        from_attributes = True