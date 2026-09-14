from pydantic import BaseModel, EmailStr


class ClienteCreate(BaseModel):
    nombre: str
    tipo_documento: str | None = None
    documento: str | None = None
    email: EmailStr | None = None
    telefono: str | None = None
    direccion: str | None = None
    ciudad: str | None = None
    tipo: str = "ocasional"  # ocasional, frecuente, mayorista
    limite_credito: float = 0


class ClienteUpdate(BaseModel):
    nombre: str | None = None
    tipo_documento: str | None = None
    documento: str | None = None
    email: EmailStr | None = None
    telefono: str | None = None
    direccion: str | None = None
    ciudad: str | None = None
    tipo: str | None = None
    limite_credito: float | None = None
    activo: bool | None = None


class ClienteOut(BaseModel):
    id: int
    nombre: str
    tipo_documento: str | None = None
    documento: str | None = None
    email: EmailStr | None = None
    telefono: str | None = None
    direccion: str | None = None
    ciudad: str | None = None
    tipo: str
    limite_credito: float | None = None
    creditos: float | None = None
    activo: bool

    class Config:
        from_attributes = True


class ProveedorCreate(BaseModel):
    nombre: str
    nit: str | None = None
    contacto: str | None = None
    email: EmailStr | None = None
    telefono: str | None = None
    direccion: str | None = None
    ciudad: str | None = None


class ProveedorUpdate(BaseModel):
    nombre: str | None = None
    nit: str | None = None
    contacto: str | None = None
    email: EmailStr | None = None
    telefono: str | None = None
    direccion: str | None = None
    ciudad: str | None = None
    activo: bool | None = None


class ProveedorOut(BaseModel):
    id: int
    nombre: str
    nit: str | None = None
    contacto: str | None = None
    email: EmailStr | None = None
    telefono: str | None = None
    direccion: str | None = None
    ciudad: str | None = None
    activo: bool

    class Config:
        from_attributes = True