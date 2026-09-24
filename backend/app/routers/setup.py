import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Caja, Configuracion, Empresa, PuntoVenta, Rol, Sesion, Sucursal, Usuario
from ..plan import TIPOS_NEGOCIO
from ..schemas.auth import Token
from ..security import create_access_token, hash_password

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/estado")
def estado_setup(db: Session = Depends(get_db)):
    """Estado del onboarding: pendiente solo si no hay empresas ni usuarios."""
    empresas = db.query(Empresa).count()
    usuarios = db.query(Usuario).count()
    sus = db.query(Configuracion).filter(Configuracion.clave == "suscripcion").first()
    return {
        "pendiente": empresas == 0 or usuarios == 0,
        "empresas": empresas,
        "usuarios": usuarios,
        "plan_activo": bool(sus and sus.valor),
    }


class RegistroSetupIn(BaseModel):
    nombre_negocio: str
    nit: str
    tipo_negocio: str = "general"
    admin_nombre: str = "Administrador"
    admin_usuario: str
    admin_email: EmailStr | None = None
    admin_clave: str


@router.post("/registro", response_model=Token)
def registrar_setup(data: RegistroSetupIn, db: Session = Depends(get_db)):
    """Crea el primer negocio con su administrador y activa la prueba del plan Esencial."""
    if db.query(Empresa).count() > 0:
        raise HTTPException(409, "El sistema ya tiene un negocio configurado")
    if not data.nombre_negocio.strip() or not data.nit.strip():
        raise HTTPException(400, "Requiere nombre del negocio y NIT")
    if len(data.admin_clave) < 6:
        raise HTTPException(400, "La contraseña debe tener al menos 6 caracteres")
    if data.tipo_negocio not in TIPOS_NEGOCIO:
        raise HTTPException(400, f"Tipo de negocio inválido: {data.tipo_negocio}")
    if db.query(Usuario).filter(Usuario.username == data.admin_usuario.strip()).first():
        raise HTTPException(400, "Ese nombre de usuario ya está en uso")

    empresa = Empresa(
        nombre=data.nombre_negocio.strip(),
        nit=data.nit.strip(),
        tipo_negocio=data.tipo_negocio,
        razon_social=data.nombre_negocio.strip(),
        regimen="simplificado",
    )
    db.add(empresa)
    db.flush()

    sucursal = Sucursal(
        empresa_id=empresa.id,
        nombre="Sucursal Principal",
        codigo="SUC-001",
        ciudad="",
    )
    db.add(sucursal)
    db.flush()

    pv = PuntoVenta(sucursal_id=sucursal.id, nombre="Punto de Venta Principal", tipo="POS")
    db.add(pv)
    db.flush()

    db.add(Caja(punto_venta_id=pv.id, nombre="Caja 1", codigo="CAJA-001", saldo_inicial=0))

    rol_admin = Rol(nombre="Administrador", descripcion="Acceso total al sistema", es_sistema=True)
    db.add(rol_admin)
    db.flush()

    admin = Usuario(
        empresa_id=empresa.id,
        sucursal_id=sucursal.id,
        rol_id=rol_admin.id,
        nombre=data.admin_nombre.strip() or "Administrador",
        username=data.admin_usuario.strip(),
        email=str(data.admin_email) if data.admin_email else None,
        password_hash=hash_password(data.admin_clave),
        activo=True,
        es_admin=True,
        vendedor=True,
        debe_cambiar_password=False,
    )
    db.add(admin)
    db.flush()

    db.add(
        Configuracion(
            clave="suscripcion",
            valor=json.dumps({"plan": "esencial", "vence": ""}, ensure_ascii=False),
            descripcion="Plan de suscripción del negocio",
        )
    )

    token = create_access_token(str(admin.id))
    db.add(Sesion(usuario_id=admin.id, token=token))
    db.commit()
    return Token(access_token=token, debe_cambiar_password=False)