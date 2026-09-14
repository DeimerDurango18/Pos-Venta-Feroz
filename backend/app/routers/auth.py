from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import AuditoriaLog, RestablecerClave, Sesion, Usuario
from ..schemas.auth import (
    CambiarPasswordRequest,
    LoginRequest,
    RecuperarRequest,
    RestablecerRequest,
    SesionOut,
    Token,
    UsuarioOut,
)
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    usuario = (
        db.query(Usuario)
        .filter(Usuario.username == data.username)
        .first()
    )
    if not usuario or not verify_password(data.password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )
    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo",
        )
    token = create_access_token(str(usuario.id))
    db.add(Sesion(usuario_id=usuario.id, token=token))
    db.commit()
    return Token(
        access_token=token,
        debe_cambiar_password=bool(usuario.debe_cambiar_password),
    )


@router.post("/cambiar-password")
def cambiar_password(
    data: CambiarPasswordRequest,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    if not verify_password(data.password_actual, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual no es correcta",
        )
    if data.password_actual == data.password_nueva:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe ser diferente a la actual",
        )
    usuario.password_hash = hash_password(data.password_nueva)
    usuario.debe_cambiar_password = False
    db.query(Sesion).filter(Sesion.usuario_id == usuario.id).update(
        {Sesion.activa: False}
    )
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="auth",
            accion="cambiar-password",
            entidad="usuario",
            entidad_id=usuario.id,
            detalle="Contraseña cambiada",
        )
    )
    db.commit()
    return {"ok": True, "mensaje": "Contraseña actualizada"}


@router.get("/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(get_current_user)):
    return usuario


@router.post("/recuperar")
def recuperar_contrasena(
    data: RecuperarRequest,
    db: Session = Depends(get_db),
):
    usuario = db.query(Usuario).filter(Usuario.email == data.email).first()
    if usuario:
        token = secrets.token_urlsafe(32)
        db.add(
            RestablecerClave(
                usuario_id=usuario.id,
                token=token,
                expira_en=datetime.now(timezone.utc) + timedelta(minutes=30),
            )
        )
        db.commit()
    return {"ok": True, "mensaje": "Si el correo existe, recibirás instrucciones para restablecer tu contraseña"}


@router.post("/restablecer")
def restablecer_contrasena(
    data: RestablecerRequest,
    db: Session = Depends(get_db),
):
    fila = (
        db.query(RestablecerClave)
        .filter(RestablecerClave.token == data.token)
        .first()
    )
    if (
        not fila
        or fila.usado
        or (fila.expira_en and fila.expira_en < datetime.now(timezone.utc))
    ):
        raise HTTPException(400, "Token inválido o expirado")
    usuario = db.get(Usuario, fila.usuario_id)
    if not usuario:
        raise HTTPException(400, "Usuario no encontrado")
    usuario.password_hash = hash_password(data.nueva_password)
    fila.usado = True
    db.query(Sesion).filter(Sesion.usuario_id == usuario.id).update(
        {Sesion.activa: False}
    )
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="auth",
            accion="restablecer-clave",
            entidad="usuario",
            entidad_id=usuario.id,
            detalle="Contraseña restablecida",
        )
    )
    db.commit()
    return {"ok": True}


@router.get("/sesiones", response_model=list[SesionOut])
def listar_sesiones(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    return (
        db.query(Sesion)
        .filter(Sesion.usuario_id == usuario.id, Sesion.activa == True)
        .order_by(Sesion.id.desc())
        .all()
    )


@router.post("/sesiones/{sesion_id}/cerrar")
def cerrar_sesion(
    sesion_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    sesion = db.get(Sesion, sesion_id)
    if not sesion or sesion.usuario_id != usuario.id:
        raise HTTPException(404, "Sesión no encontrada")
    sesion.activa = False
    db.commit()
    return {"ok": True, "sesion_id": sesion_id}