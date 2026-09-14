from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    debe_cambiar_password: bool = False


class CambiarPasswordRequest(BaseModel):
    password_actual: str
    password_nueva: str = Field(min_length=8)


class RecuperarRequest(BaseModel):
    email: str


class RestablecerRequest(BaseModel):
    token: str
    nueva_password: str = Field(min_length=6)


class SesionOut(BaseModel):
    id: int
    ip: str | None = None
    user_agent: str | None = None
    activa: bool | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str
    password: str


class UsuarioCreate(BaseModel):
    empresa_id: int
    nombre: str = Field(min_length=1)
    username: str = Field(min_length=3)
    email: EmailStr | None = None
    password: str = Field(min_length=6)
    rol_id: int | None = None
    sucursal_id: int | None = None
    es_admin: bool = False
    vendedor: bool = True


class UsuarioUpdate(BaseModel):
    nombre: str | None = None
    email: EmailStr | None = None
    activo: bool | None = None
    rol_id: int | None = None
    sucursal_id: int | None = None
    password: str | None = None


class UsuarioOut(BaseModel):
    id: int
    nombre: str
    username: str
    email: EmailStr | None = None
    activo: bool
    es_admin: bool
    empresa_id: int
    sucursal_id: int | None = None
    debe_cambiar_password: bool = False
    rol: "RolOut | None" = None

    class Config:
        from_attributes = True


class RolOut(BaseModel):
    id: int
    nombre: str
    descripcion: str | None = None

    class Config:
        from_attributes = True