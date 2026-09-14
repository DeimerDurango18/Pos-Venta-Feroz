from datetime import date, datetime

from pydantic import BaseModel


class OrdenCompraDetalleCreate(BaseModel):
    producto_id: int
    cantidad: float
    costo_unitario: float = 0


class OrdenCompraCreate(BaseModel):
    empresa_id: int
    sucursal_id: int
    proveedor_id: int
    fecha_requerida: date | None = None
    notas: str | None = None
    detalle: list[OrdenCompraDetalleCreate]


class OrdenCompraDetalleOut(BaseModel):
    id: int
    producto_id: int
    cantidad: float | None = None
    costo_unitario: float | None = None

    class Config:
        from_attributes = True


class OrdenCompraOut(BaseModel):
    id: int
    empresa_id: int
    sucursal_id: int
    proveedor_id: int
    numero: str | None = None
    estado: str
    total_estimado: float | None = None
    notas: str | None = None
    created_at: datetime | None = None
    detalle: list[OrdenCompraDetalleOut] = []

    class Config:
        from_attributes = True


class CompraDetalleCreate(BaseModel):
    producto_id: int
    cantidad: float
    costo_unitario: float


class CompraCreate(BaseModel):
    empresa_id: int
    sucursal_id: int
    proveedor_id: int
    orden_compra_id: int | None = None
    tipo: str = "contado"  # contado, credito
    otros_costos: float = 0
    nota: str | None = None
    detalle: list[CompraDetalleCreate]


class CompraDetalleOut(BaseModel):
    id: int
    producto_id: int
    cantidad: float | None = None
    costo_unitario: float | None = None
    subtotal: float | None = None

    class Config:
        from_attributes = True


class CompraOut(BaseModel):
    id: int
    numero: str | None = None
    tipo: str
    estado: str
    subtotal: float | None = None
    impuesto: float | None = None
    otros_costos: float | None = None
    total: float | None = None
    proveedor_id: int
    created_at: datetime | None = None
    detalle: list[CompraDetalleOut] = []

    class Config:
        from_attributes = True


class CuentaPagarOut(BaseModel):
    id: int
    proveedor_id: int
    compra_id: int | None = None
    monto_total: float | None = None
    saldo: float | None = None
    estado: str
    fecha_vencimiento: date | None = None

    class Config:
        from_attributes = True


class AbonoProveedorCreate(BaseModel):
    cuenta_id: int
    monto: float
    medio: str = "efectivo"
    referencia: str | None = None
    observacion: str | None = None


class AbonoProveedorOut(BaseModel):
    id: int
    cuenta_id: int
    monto: float | None = None
    medio: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True