from datetime import datetime, timedelta, timezone
from html import escape
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..correo import enviar_correo, url_publica
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
        if data.email.strip():
            base = url_publica(db) or "http://localhost:28742"
            enlace = f"{base}/login?token={token}"
            asunto = "Restablece tu contraseña"
            html = (
                "<div style='font-family:Arial,Helvetica,sans-serif;background:#f1f5f9;padding:24px'>"
                "<div style='max-width:520px;margin:0 auto;background:#fff;border-radius:10px;"
                "border:1px solid #e2e8f0;overflow:hidden'>"
                "<div style='background:#0f172a;color:#fff;padding:14px 20px;font-weight:700;font-size:16px'>"
                "Restablecer contraseña</div>"
                "<div style='padding:20px'>"
                f"<p>Hola <b>{escape(data.email)}</b>,</p>"
                "<p>Recibimos una solicitud para restablecer tu contraseña. "
                "El enlace es válido por <b>30 minutos</b>.</p>"
                f"<p style='text-align:center;margin:22px 0'>"
                f"<a href='{enlace}' style='display:inline-block;background:#4338ca;color:#fff;"
                "padding:11px 22px;border-radius:8px;text-decoration:none;font-weight:700'>"
                "Restablecer contraseña</a></p>"
                f"<p style='color:#64748b;font-size:13px'>Si no solicitaste este cambio, ignora este correo. "
                f"Pega el enlace si no abre: <span style='word-break:break-all'>{enlace}</span></p>"
                "</div></div></div>"
            )
            plano = f"Restablece tu contraseña en: {enlace}"
            resultado = enviar_correo(db, data.email, asunto, html, texto_plano=plano)
            db.add(
                AuditoriaLog(
                    usuario_id=usuario.id,
                    modulo="auth",
                    accion="recuperar-clave",
                    entidad="usuario",
                    entidad_id=usuario.id,
                    detalle=(
                        f"Correo de recuperación enviado a {data.email}"
                        if resultado.get("ok")
                        else f"Fallo al enviar correo de recuperación a {data.email}: {resultado.get('error')}"
                    ),
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