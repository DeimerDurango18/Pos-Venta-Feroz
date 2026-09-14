import json

from fastapi import HTTPException

from .models import Autorizacion


def solicitar_autorizacion(db, usuario, modulo, accion, entidad=None, entidad_id=None, datos=None):
    """Registra una solicitud de autorización pendiente."""
    autorizacion = Autorizacion(
        empresa_id=1,
        modulo=modulo,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        solicitante_id=usuario.id if usuario else None,
        datos=json.dumps(datos, ensure_ascii=False) if datos is not None else None,
        estado="pendiente",
    )
    db.add(autorizacion)
    db.commit()
    return autorizacion


def negar_con_autorizacion(db, usuario, modulo, accion, entidad=None, entidad_id=None, datos=None):
    """Bloquea la acción por falta de permiso y genera la solicitud de autorización."""
    solicitud = solicitar_autorizacion(db, usuario, modulo, accion, entidad, entidad_id, datos)
    raise HTTPException(
        403,
        f"Acción requiere autorización ({modulo}/{accion}). "
        f"Solicitud #{solicitud.id} registrada en espera de aprobación.",
    )


def requiere_autorizacion(db, usuario, modulo, accion, entidad=None, entidad_id=None, datos=None):
    """Escala una operación sensible a autorización cuando el usuario no tiene el permiso.

    Si el usuario tiene el permiso se continúa; en caso contrario se registra una
    solicitud pendiente y se bloquea la acción con 403.
    """
    from .deps import tiene_permiso

    if tiene_permiso(db, usuario, modulo, accion):
        return
    negar_con_autorizacion(db, usuario, modulo, accion, entidad, entidad_id, datos)