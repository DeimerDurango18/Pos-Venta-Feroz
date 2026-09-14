from pydantic import BaseModel, Field


class CategoriaCreate(BaseModel):
    nombre: str
    categoria_padre_id: int | None = None


class CategoriaOut(BaseModel):
    id: int
    nombre: str
    categoria_padre_id: int | None = None
    activa: bool

    class Config:
        from_attributes = True


class MarcaCreate(BaseModel):
    nombre: str


class MarcaOut(BaseModel):
    id: int
    nombre: str

    class Config:
        from_attributes = True


class PresentacionCreate(BaseModel):
    nombre: str
    unidad_medida: str | None = None
    cantidad: float = 1


class PresentacionOut(BaseModel):
    id: int
    nombre: str
    unidad_medida: str | None = None
    cantidad: float | None = None

    class Config:
        from_attributes = True


class ProductoCreate(BaseModel):
    empresa_id: int
    categoria_id: int | None = None
    marca_id: int | None = None
    nombre: str = Field(min_length=1)
    descripcion: str | None = None
    codigo_barras: str | None = None
    sku: str | None = None
    plu: str | None = None
    tipo: str = "unidad"
    es_compuesto: bool = False
    es_servicio: bool = False
    con_vencimiento: bool = False
    maneja_lotes: bool = False
    maneja_serie: bool = False
    imagen: str | None = None
    ficha_tecnica: str | None = None
    precio_compra: float = 0
    precio_venta: float = 0
    precio_mayorista: float = 0
    precio_minorista: float = 0
    precio_institucional: float = 0
    costo: float = 0
    margen: float = 0
    margen_minimo: float = 0
    bloquear_venta_bajo_costo: bool = False
    impuesto: float = 0
    stock_minimo: float = 0
    stock_maximo: float = 0
    stock_seguridad: float = 0
    punto_reorden: float = 0


class ProductoUpdate(BaseModel):
    categoria_id: int | None = None
    marca_id: int | None = None
    nombre: str | None = None
    descripcion: str | None = None
    codigo_barras: str | None = None
    sku: str | None = None
    plu: str | None = None
    tipo: str | None = None
    es_servicio: bool | None = None
    con_vencimiento: bool | None = None
    maneja_lotes: bool | None = None
    maneja_serie: bool | None = None
    imagen: str | None = None
    ficha_tecnica: str | None = None
    precio_compra: float | None = None
    precio_venta: float | None = None
    precio_mayorista: float | None = None
    precio_minorista: float | None = None
    precio_institucional: float | None = None
    costo: float | None = None
    margen_minimo: float | None = None
    bloquear_venta_bajo_costo: bool | None = None
    impuesto: float | None = None
    stock_minimo: float | None = None
    stock_maximo: float | None = None
    stock_seguridad: float | None = None
    punto_reorden: float | None = None
    activo: bool | None = None


class ProductoOut(BaseModel):
    id: int
    empresa_id: int
    categoria_id: int | None = None
    marca_id: int | None = None
    nombre: str
    descripcion: str | None = None
    codigo_barras: str | None = None
    sku: str | None = None
    plu: str | None = None
    tipo: str
    es_compuesto: bool
    es_servicio: bool
    maneja_serie: bool | None = None
    imagen: str | None = None
    ficha_tecnica: str | None = None
    precio_compra: float | None = None
    precio_venta: float | None = None
    precio_mayorista: float | None = None
    precio_minorista: float | None = None
    precio_institucional: float | None = None
    costo: float | None = None
    impuesto: float | None = None
    margen_minimo: float | None = None
    bloquear_venta_bajo_costo: bool | None = None
    stock_minimo: float | None = None
    stock_maximo: float | None = None
    stock_seguridad: float | None = None
    activo: bool

    class Config:
        from_attributes = True