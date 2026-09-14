from pydantic import BaseModel, EmailStr


class EmpresaCreate(BaseModel):
    nombre: str
    nit: str
    tipo_negocio: str = "general"
    razon_social: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    email: EmailStr | None = None
    regimen: str | None = None
    logo: str | None = None


class EmpresaUpdate(BaseModel):
    nombre: str | None = None
    nit: str | None = None
    tipo_negocio: str | None = None
    razon_social: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    email: EmailStr | None = None
    regimen: str | None = None
    activa: bool | None = None


class EmpresaOut(BaseModel):
    id: int
    nombre: str
    nit: str
    tipo_negocio: str
    razon_social: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    email: EmailStr | None = None
    regimen: str | None = None
    activa: bool

    class Config:
        from_attributes = True


class SucursalCreate(BaseModel):
    empresa_id: int
    nombre: str
    codigo: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    ciudad: str | None = None


class SucursalUpdate(BaseModel):
    nombre: str | None = None
    codigo: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    ciudad: str | None = None
    activa: bool | None = None


class SucursalOut(BaseModel):
    id: int
    empresa_id: int
    nombre: str
    codigo: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    ciudad: str | None = None
    activa: bool

    class Config:
        from_attributes = True


class PuntoVentaCreate(BaseModel):
    sucursal_id: int
    nombre: str
    tipo: str | None = None


class PuntoVentaOut(BaseModel):
    id: int
    sucursal_id: int
    nombre: str
    tipo: str | None = None
    activo: bool

    class Config:
        from_attributes = True


class CajaCreate(BaseModel):
    punto_venta_id: int
    nombre: str
    codigo: str | None = None
    saldo_inicial: float = 0
    es_principal: bool = False


class CajaUpdate(BaseModel):
    nombre: str | None = None
    codigo: str | None = None
    activa: bool | None = None
    saldo_inicial: float | None = None
    es_principal: bool | None = None


class CajaOut(BaseModel):
    id: int
    punto_venta_id: int
    nombre: str
    codigo: str | None = None
    activa: bool
    saldo_inicial: float | None = None
    es_principal: bool

    class Config:
        from_attributes = True