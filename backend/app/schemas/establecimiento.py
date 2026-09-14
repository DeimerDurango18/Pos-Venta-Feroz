from pydantic import BaseModel


class EstablecimientoUpdate(BaseModel):
    nit: str
    nombre: str | None = None
    razon_social: str | None = None
    tipo_negocio: str = "general"
    regimen: str | None = None
    actividad_economica: str | None = None
    direccion: str | None = None
    ciudad: str | None = None
    departamento: str | None = None
    telefono: str | None = None
    email: str | None = None
    activo: bool = True
    modelo_negocio_id: int | None = None


class EstablecimientoOut(BaseModel):
    id: int
    nit: str
    nombre: str
    razon_social: str | None = None
    tipo_negocio: str
    regimen: str | None = None
    actividad_economica: str | None = None
    direccion: str | None = None
    ciudad: str | None = None
    departamento: str | None = None
    telefono: str | None = None
    email: str | None = None
    activo: bool
    modelo_negocio_id: int | None = None

    class Config:
        from_attributes = True