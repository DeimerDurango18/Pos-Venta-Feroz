from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .database import get_db
from .models import Usuario
from .security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
        )
    try:
        payload = decode_token(credentials.credentials)
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )
    user = db.get(Usuario, user_id)
    if not user or not user.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo",
        )
    return user


def tiene_permiso(db: Session, usuario: Usuario, modulo: str, accion: str) -> bool:
    """Verifica permiso módulo/acción. Los administradores siempre tienen acceso."""
    if usuario.es_admin:
        return True
    if not usuario.rol:
        return False
    for p in usuario.rol.permisos:
        if p.modulo == modulo and (p.accion == accion or p.accion == "*"):
            return True
    return False


def require_permiso(modulo: str, accion: str):
    """Dependencia de FastAPI que exige permiso módulo/acción."""

    def _dep(
        usuario: Usuario = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> Usuario:
        if not tiene_permiso(db, usuario, modulo, accion):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requiere permiso {modulo}/{accion}",
            )
        return usuario

    return _dep