from pydantic import BaseModel


class ConfiguracionCreate(BaseModel):
    clave: str
    valor: str
    descripcion: str | None = None


class ConfiguracionOut(BaseModel):
    id: int
    clave: str
    valor: str | None = None
    descripcion: str | None = None

    class Config:
        from_attributes = True


class ImpuestoCreate(BaseModel):
    nombre: str
    tasa: float


class ImpuestoOut(BaseModel):
    id: int
    nombre: str
    tasa: float | None = None
    activo: bool

    class Config:
        from_attributes = True