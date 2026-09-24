from datetime import datetime

from pydantic import BaseModel


class VentaDetalleCreate(BaseModel):
    producto_id: int
    cantidad: float
    precio: float | None = None  # si no, usa precio_venta
    descuento: float = 0
    lote: str | None = None
    vencimiento: str | None = None


class VentaPagoCreate(BaseModel):
    medio: str  # efectivo, tarjeta, transferencia, QR, nequi, daviplata, breb, otro
    monto: float
    referencia: str | None = None


class VentaCreate(BaseModel):
    empresa_id: int
    sucursal_id: int
    caja_id: int | None = None
    punto_venta_id: int | None = None
    cliente_id: int | None = None
    tipo: str = "contado"
    descuento_global: float = 0
    propina: float = 0
    nota: str | None = None
    cupon_codigo: str | None = None
    detalle: list[VentaDetalleCreate]
    pagos: list[VentaPagoCreate]


class VentaDetalleOut(BaseModel):
    id: int
    producto_id: int
    cantidad: float | None = None
    precio: float | None = None
    descuento: float | None = None
    subtotal: float | None = None

    class Config:
        from_attributes = True


class VentaPagoOut(BaseModel):
    id: int
    medio: str
    monto: float | None = None
    referencia: str | None = None

    class Config:
        from_attributes = True


class VentaOut(BaseModel):
    id: int
    numero: str | None = None
    tipo: str
    estado: str
    subtotal: float | None = None
    descuento: float | None = None
    impuesto: float | None = None
    total: float | None = None
    propina: float | None = None
    saldo: float | None = None
    created_at: datetime | None = None
    detalle: list[VentaDetalleOut] = []
    pagos: list[VentaPagoOut] = []

    class Config:
        from_attributes = True


class AperturaCajaCreate(BaseModel):
    caja_id: int
    saldo_inicial: float


class AperturaCajaOut(BaseModel):
    id: int
    caja_id: int
    saldo_inicial: float | None = None
    saldo_cierre: float | None = None
    estado: str

    class Config:
        from_attributes = True


class MovimientoCajaCreate(BaseModel):
    apertura_caja_id: int
    tipo: str  # ingreso, egreso, gasto, retiro
    concepto: str
    monto: float
    medio: str = "efectivo"


class MovimientoCajaOut(BaseModel):
    id: int
    tipo: str
    concepto: str | None = None
    monto: float | None = None
    medio: str | None = None

    class Config:
        from_attributes = True


class GastoCreate(BaseModel):
    empresa_id: int
    sucursal_id: int | None = None
    categoria: str
    concepto: str
    monto: float
    medio: str = "efectivo"


class GastoOut(BaseModel):
    id: int
    categoria: str | None = None
    concepto: str | None = None
    monto: float | None = None
    medio: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class CambioCajeroIn(BaseModel):
    usuario_id: int


class TransferenciaCajaCreate(BaseModel):
    origen_apertura_id: int
    destino_apertura_id: int
    monto: float
    concepto: str = "Transferencia de efectivo"


class TurnoOut(BaseModel):
    id: int
    caja_id: int
    caja_nombre: str | None = None
    cajero_id: int | None = None
    cajero_nombre: str | None = None
    saldo_inicial: float | None = None
    saldo_cierre: float | None = None
    estado: str
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class AbonoVentaIn(BaseModel):
    medio: str = "efectivo"
    monto: float
    referencia: str | None = None