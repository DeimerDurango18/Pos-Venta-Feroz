from datetime import date, datetime

from pydantic import BaseModel


# ---------- Registro de errores ----------
class ErrorLogOut(BaseModel):
    id: int
    usuario_id: int | None = None
    modulo: str | None = None
    endpoint: str | None = None
    metodo: str | None = None
    mensaje: str | None = None
    traceback: str | None = None
    resuelto: bool | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


# ---------- Precios de competencia ----------
class PrecioCompetenciaCreate(BaseModel):
    competidor: str
    precio: float
    fecha: date | None = None
    notas: str | None = None


class PrecioCompetenciaOut(BaseModel):
    id: int
    producto_id: int
    competidor: str
    precio: float | None = None
    fecha: date | None = None
    notas: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


# ---------- Promociones ----------
class PromocionProductoIn(BaseModel):
    producto_id: int


class PromocionCreate(BaseModel):
    empresa_id: int = 1
    nombre: str
    tipo: str  # porcentaje, valor, 2x1, 3x2
    valor: float = 0
    aplica_a: str = "general"
    categoria_id: int | None = None
    desde: date | None = None
    hasta: date | None = None
    hora_desde: str | None = None
    hora_hasta: str | None = None
    cantidad_minima: float = 0
    descripcion: str | None = None
    activa: bool = True
    cliente_id: int | None = None
    productos: list[PromocionProductoIn] = []


class PromocionProductoOut(BaseModel):
    producto_id: int | None = None

    class Config:
        from_attributes = True


class PromocionOut(BaseModel):
    id: int
    nombre: str
    tipo: str
    valor: float | None = None
    aplica_a: str | None = None
    categoria_id: int | None = None
    desde: date | None = None
    hasta: date | None = None
    hora_desde: str | None = None
    hora_hasta: str | None = None
    cantidad_minima: float | None = None
    descripcion: str | None = None
    activa: bool | None = None
    cliente_id: int | None = None
    created_at: datetime | None = None
    productos: list[PromocionProductoOut] = []

    class Config:
        from_attributes = True


# ---------- Historial de precios ----------
class PrecioHistoricoOut(BaseModel):
    id: int
    producto_id: int
    campo: str
    valor_anterior: float | None = None
    valor_nuevo: float | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


# ---------- Devoluciones a proveedor ----------
class DevolucionCompraDetalleCreate(BaseModel):
    producto_id: int
    cantidad: float
    costo_unitario: float | None = None
    lote: str | None = None
    vencimiento: date | None = None


class DevolucionCompraCreate(BaseModel):
    empresa_id: int = 1
    sucursal_id: int = 1
    proveedor_id: int
    compra_id: int | None = None
    tipo: str = "parcial"
    motivo: str | None = None
    detalle: list[DevolucionCompraDetalleCreate]


class DevolucionCompraDetalleOut(BaseModel):
    id: int
    producto_id: int
    cantidad: float | None = None
    costo_unitario: float | None = None

    class Config:
        from_attributes = True


class DevolucionCompraOut(BaseModel):
    id: int
    numero: str | None = None
    proveedor_id: int
    compra_id: int | None = None
    tipo: str | None = None
    motivo: str | None = None
    total_devolucion: float | None = None
    estado: str | None = None
    created_at: datetime | None = None
    detalle: list[DevolucionCompraDetalleOut] = []

    class Config:
        from_attributes = True


# ---------- Cotizaciones de proveedor ----------
class CotizacionProveedorDetalleCreate(BaseModel):
    producto_id: int
    cantidad: float
    costo_unitario: float | None = None


class CotizacionProveedorCreate(BaseModel):
    empresa_id: int = 1
    proveedor_id: int
    fecha_validez: date | None = None
    notas: str | None = None
    detalle: list[CotizacionProveedorDetalleCreate]


class CotizacionProveedorDetalleOut(BaseModel):
    id: int
    producto_id: int
    cantidad: float | None = None
    costo_unitario: float | None = None

    class Config:
        from_attributes = True


class CotizacionProveedorOut(BaseModel):
    id: int
    numero: str | None = None
    proveedor_id: int
    estado: str | None = None
    fecha_validez: date | None = None
    total_estimado: float | None = None
    notas: str | None = None
    created_at: datetime | None = None
    detalle: list[CotizacionProveedorDetalleOut] = []

    class Config:
        from_attributes = True


# ---------- Conteo físico ----------
class ConteoFisicoDetalleCreate(BaseModel):
    producto_id: int
    contado: float


class ConteoFisicoCreate(BaseModel):
    empresa_id: int = 1
    sucursal_id: int = 1
    tipo: str = "fisico"  # fisico, ciclico
    observacion: str | None = None
    detalle: list[ConteoFisicoDetalleCreate]


class ConteoFisicoDetalleOut(BaseModel):
    id: int
    producto_id: int
    esperado: float | None = None
    contado: float | None = None
    diferencia: float | None = None

    class Config:
        from_attributes = True


class ConteoFisicoOut(BaseModel):
    id: int
    numero: str | None = None
    sucursal_id: int
    tipo: str | None = None
    estado: str | None = None
    observacion: str | None = None
    created_at: datetime | None = None
    detalle: list[ConteoFisicoDetalleOut] = []

    class Config:
        from_attributes = True


# ---------- Auditoría ----------
class AuditoriaLogOut(BaseModel):
    id: int
    usuario_id: int | None = None
    modulo: str
    accion: str
    entidad: str | None = None
    entidad_id: int | None = None
    detalle: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


# ---------- Vendedores / comisiones / metas ----------
class MetaVendedorCreate(BaseModel):
    vendedor_id: int
    periodo: str
    meta_ventas: float = 0
    meta_utilidad: float = 0


class MetaVendedorOut(BaseModel):
    id: int
    vendedor_id: int
    periodo: str
    meta_ventas: float | None = None
    meta_utilidad: float | None = None

    class Config:
        from_attributes = True


class ReglaComisionCreate(BaseModel):
    empresa_id: int = 1
    vendedor_id: int | None = None
    producto_id: int | None = None
    porcentaje: float


class ReglaComisionOut(BaseModel):
    id: int
    vendedor_id: int | None = None
    producto_id: int | None = None
    porcentaje: float | None = None

    class Config:
        from_attributes = True