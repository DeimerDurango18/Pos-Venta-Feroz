import traceback as _tb

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_permiso
from ..models import ErrorLog, Usuario
from ..schemas.avanzado import ErrorLogOut

router = APIRouter(prefix="/sistema", tags=["sistema"])


def registrar_error(db: Session, exc: Exception, endpoint: str | None = None, metodo: str | None = None, usuario_id: int | None = None):
    """Guarda un error en el registro de errores."""
    db.add(
        ErrorLog(
            usuario_id=usuario_id,
            modulo=(endpoint or "/").split("/")[1] if endpoint else None,
            endpoint=endpoint,
            metodo=metodo,
            mensaje=str(exc)[:2000],
            traceback=_tb.format_exc()[-8000:],
            resuelto=False,
        )
    )
    db.commit()


class SimularErrorIn(BaseModel):
    modulo: str = "test"
    mensaje: str = "Error simulado de prueba"


@router.get("/errores", response_model=list[ErrorLogOut])
def listar_errores(
    modulo: str | None = None,
    resuelto: bool | None = None,
    limite: int = Query(50, ge=1, le=500),
    _: Usuario = Depends(require_permiso("sistema", "errores")),
    db: Session = Depends(get_db),
):
    q = db.query(ErrorLog)
    if modulo:
        q = q.filter(ErrorLog.modulo == modulo)
    if resuelto is not None:
        q = q.filter(ErrorLog.resuelto == resuelto)
    return q.order_by(ErrorLog.id.desc()).limit(limite).all()


@router.post("/errores/simular", response_model=ErrorLogOut, status_code=201)
def simular_error(
    data: SimularErrorIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reg = ErrorLog(
        usuario_id=usuario.id,
        modulo=data.modulo,
        endpoint="POST /sistema/errores/simular",
        metodo="POST",
        mensaje=data.mensaje,
        traceback="Error simulado de prueba (346)",
        resuelto=False,
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)
    return reg


@router.patch("/errores/{error_id}/resolver", response_model=ErrorLogOut)
def resolver_error(
    error_id: int,
    _: Usuario = Depends(require_permiso("sistema", "errores")),
    db: Session = Depends(get_db),
):
    reg = db.get(ErrorLog, error_id)
    if not reg:
        raise HTTPException(404, "Error no encontrado")
    reg.resuelto = True
    db.commit()
    db.refresh(reg)
    return reg