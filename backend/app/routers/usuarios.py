from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Rol, Usuario
from ..schemas.auth import UsuarioCreate, UsuarioOut, UsuarioUpdate
from ..security import hash_password

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get("", response_model=list[UsuarioOut])
def listar_usuarios(db: Session = Depends(get_db)):
    return db.query(Usuario).all()


@router.post("", response_model=UsuarioOut, status_code=201)
def crear_usuario(data: UsuarioCreate, db: Session = Depends(get_db)):
    if db.query(Usuario).filter(Usuario.username == data.username).first():
        raise HTTPException(400, "Username ya existe")
    if not data.rol_id:
        data.rol_id = 2  # rol cajero por defecto
    if not db.get(Rol, data.rol_id):
        raise HTTPException(400, "Rol no existe")
    usr = Usuario(
        empresa_id=data.empresa_id,
        nombre=data.nombre,
        username=data.username,
        email=data.email,
        rol_id=data.rol_id,
        sucursal_id=data.sucursal_id,
        es_admin=data.es_admin,
        vendedor=data.vendedor,
        password_hash=hash_password(data.password),
    )
    db.add(usr)
    db.commit()
    db.refresh(usr)
    return usr


@router.put("/{usuario_id}", response_model=UsuarioOut)
def actualizar_usuario(
    usuario_id: int, data: UsuarioUpdate, db: Session = Depends(get_db)
):
    usr = db.get(Usuario, usuario_id)
    if not usr:
        raise HTTPException(404, "Usuario no encontrado")
    values = data.model_dump(exclude_unset=True)
    password = values.pop("password", None)
    for k, v in values.items():
        setattr(usr, k, v)
    if password:
        usr.password_hash = hash_password(password)
    db.commit()
    db.refresh(usr)
    return usr