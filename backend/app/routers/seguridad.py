from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, tiene_permiso
from ..models import (
    Autorizacion,
    AuditoriaLog,
    Permiso,
    Rol,
    Usuario,
    rol_permiso,
)


class PermisoAsignar(BaseModel):
    roles: list[int]  # ids de roles a asignar el permiso


class PermisoRequest(BaseModel):
    modulo: str
    accion: str

router = APIRouter(prefix="/seguridad", tags=["seguridad"])


def _roles_por_permiso(db, permiso_id):
    rows = db.execute(
        rol_permiso.select().where(rol_permiso.c.permiso_id == permiso_id)
    ).fetchall()
    return [r.rol_id for r in rows]


def _permisos_por_rol(db, rol_id):
    rows = db.execute(
        rol_permiso.select().where(rol_permiso.c.rol_id == rol_id)
    ).fetchall()
    return [r.permiso_id for r in rows]


# ---------- Permisos por módulo (348-352) ----------

@router.get("/permisos")
def listar_permisos(db: Session = Depends(get_db)):
    permisos = db.query(Permiso).order_by(Permiso.modulo, Permiso.accion).all()
    return [
        {
            "id": p.id,
            "modulo": p.modulo,
            "accion": p.accion,
            "nombre": p.descripcion,
            "roles": _roles_por_permiso(db, p.id),
        }
        for p in permisos
    ]


CATALOGO_PERMISOS = [
    ("ventas", "crear", "Crear venta"),
    ("ventas", "leer", "Ver ventas"),
    ("ventas", "editar", "Editar venta"),
    ("ventas", "anular", "Anular venta"),
    ("ventas", "descuento", "Descuentos especiales"),
    ("ventas", "devolucion", "Devoluciones y cambios"),
    ("pos", "operar", "Operar punto de venta"),
    ("caja", "apertura", "Abrir caja"),
    ("caja", "cierre", "Cerrar caja"),
    ("caja", "movimientos", "Movimientos de caja"),
    ("caja", "gastos", "Registrar gastos"),
    ("inventario", "leer", "Ver inventario"),
    ("inventario", "ajustar", "Ajustes, mermas y conteos"),
    ("inventario", "transferir", "Transferencias de stock"),
    ("productos", "leer", "Ver productos"),
    ("productos", "editar", "Editar productos"),
    ("clientes", "leer", "Ver clientes"),
    ("clientes", "crear", "Crear clientes"),
    ("clientes", "editar", "Editar clientes"),
    ("proveedores", "leer", "Ver proveedores"),
    ("proveedores", "editar", "Editar proveedores"),
    ("compras", "crear", "Crear compras"),
    ("financiero", "leer", "Ver reportes financieros"),
    ("reportes", "leer", "Ver reportes"),
    ("seguridad", "gestionar", "Gestionar usuarios y permisos"),
    ("facturacion", "gestionar", "Gestionar facturación DIAN"),
]

BASE_CAJERO_PERMISOS = {
    ("ventas", "crear"),
    ("ventas", "leer"),
    ("pos", "operar"),
    ("caja", "apertura"),
    ("caja", "cierre"),
    ("caja", "movimientos"),
    ("caja", "gastos"),
    ("inventario", "leer"),
    ("productos", "leer"),
    ("clientes", "leer"),
    ("clientes", "crear"),
    ("reportes", "leer"),
}


@router.post("/permisos/sincronizar")
def sincronizar_permisos(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    """Crea los permisos del catálogo que falten."""
    creados = 0
    for modulo, accion, desc in CATALOGO_PERMISOS:
        permiso = db.query(Permiso).filter(Permiso.modulo == modulo, Permiso.accion == accion).first()
        if not permiso:
            permiso = Permiso(modulo=modulo, accion=accion, descripcion=desc)
            db.add(permiso)
            creados += 1
            db.flush()
    admin = db.query(Rol).filter_by(nombre="Administrador").first()
    if admin:
        for permiso in db.query(Permiso).all():
            existe = db.execute(
                rol_permiso.select().where(
                    rol_permiso.c.rol_id == admin.id, rol_permiso.c.permiso_id == permiso.id
                )
            ).first()
            if not existe:
                db.execute(
                    rol_permiso.insert().values(rol_id=admin.id, permiso_id=permiso.id)
                )
    cajero = db.query(Rol).filter_by(nombre="Cajero").first()
    if cajero:
        for permiso in db.query(Permiso).all():
            if (permiso.modulo, permiso.accion) in BASE_CAJERO_PERMISOS:
                existe = db.execute(
                    rol_permiso.select().where(
                        rol_permiso.c.rol_id == cajero.id, rol_permiso.c.permiso_id == permiso.id
                    )
                ).first()
                if not existe:
                    db.execute(
                        rol_permiso.insert().values(rol_id=cajero.id, permiso_id=permiso.id)
                    )
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="seguridad",
            accion="sincronizar-permisos",
            entidad="permisos",
            detalle="Catálogo de permisos sincronizado",
        )
    )
    db.commit()
    return {"total": len(CATALOGO_PERMISOS), "creados": creados, "ok": True}


@router.post("/permisos/{permiso_id}/asignar")
def asignar_permiso(
    permiso_id: int,
    data: PermisoAsignar,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    permiso = db.get(Permiso, permiso_id)
    if not permiso:
        raise HTTPException(404, "Permiso no encontrado")
    for rol_id in data.roles:
        if not db.get(Rol, rol_id):
            raise HTTPException(404, f"Rol {rol_id} no encontrado")
        existe = db.execute(
            rol_permiso.select().where(
                rol_permiso.c.rol_id == rol_id, rol_permiso.c.permiso_id == permiso.id
            )
        ).first()
        if not existe:
            db.execute(
                rol_permiso.insert().values(rol_id=rol_id, permiso_id=permiso.id)
            )
    db.commit()
    return {"permiso_id": permiso.id, "roles": data.roles, "ok": True}


@router.post("/permisos/{permiso_id}/quitar")
def quitar_permiso(
    permiso_id: int,
    rol_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    db.execute(
        rol_permiso.delete().where(
            rol_permiso.c.rol_id == rol_id, rol_permiso.c.permiso_id == permiso_id
        )
    )
    db.commit()
    return {"permiso_id": permiso_id, "rol_id": rol_id, "ok": True}


@router.get("/roles")
def listar_roles(db: Session = Depends(get_db)):
    roles = db.query(Rol).all()
    por_rol = {r.id: _permisos_por_rol(db, r.id) for r in roles}
    permisos = {p.id: p for p in db.query(Permiso).all()}
    return [
        {
            "id": r.id,
            "nombre": r.nombre,
            "permisos": [
                {
                    "id": pid,
                    "modulo": permisos[pid].modulo,
                    "accion": permisos[pid].accion,
                    "nombre": permisos[pid].descripcion,
                }
                for pid in por_rol[r.id]
                if pid in permisos
            ],
        }
        for r in roles
    ]


@router.get("/mi-permisos")
def mis_permisos(usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    if usuario.es_admin:
        return {"es_admin": True, "permisos": None}
    pid_list = _permisos_por_rol(db, usuario.rol_id) if usuario.rol_id else []
    permisos_objs = [db.get(Permiso, pid) for pid in pid_list]
    return {
        "es_admin": False,
        "permisos": [
            {"modulo": p.modulo, "accion": p.accion} for p in permisos_objs if p
        ],
    }


@router.get("/verificar/{modulo}/{accion}")
def verificar_permiso(
    modulo: str,
    accion: str,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"permitido": tiene_permiso(db, usuario, modulo, accion)}


# ---------- Autorizaciones (455-459) ----------

@router.get("/autorizaciones")
def listar_autorizaciones(estado: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Autorizacion).order_by(Autorizacion.id.desc())
    if estado:
        q = q.filter(Autorizacion.estado == estado)
    q = q.limit(100)
    return [
        {
            "id": a.id,
            "modulo": a.modulo,
            "accion": a.accion,
            "entidad": a.entidad,
            "entidad_id": a.entidad_id,
            "solicitante_id": a.solicitante_id,
            "solicitante": db.get(Usuario, a.solicitante_id).nombre if a.solicitante_id else "",
            "datos": a.datos,
            "estado": a.estado,
            "resolutor_id": a.resolutor_id,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in q.all()
    ]


def _resolver(db, autorizacion, aprobar, usuario):
    if autorizacion.estado != "pendiente":
        raise HTTPException(400, "La solicitud ya fue resuelta")
    autorizacion.estado = "aprobada" if aprobar else "rechazada"
    autorizacion.resolutor_id = usuario.id
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="seguridad",
            accion="aprobar" if aprobar else "rechazar",
            entidad="autorizacion",
            entidad_id=autorizacion.id,
            detalle=f"{'Aprobada' if aprobar else 'Rechazada'} solicitud {autorizacion.modulo}/{autorizacion.accion}",
        )
    )
    db.commit()
    return {"id": autorizacion.id, "estado": autorizacion.estado}


@router.post("/autorizaciones/{autorizacion_id}/aprobar")
def aprobar_autorizacion(
    autorizacion_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    if not tiene_permiso(db, usuario, "seguridad", "gestionar"):
        raise HTTPException(403, "Requiere permiso seguridad/gestionar")
    autorizacion = db.get(Autorizacion, autorizacion_id)
    if not autorizacion:
        raise HTTPException(404, "Solicitud no encontrada")
    return _resolver(db, autorizacion, True, usuario)


@router.post("/autorizaciones/{autorizacion_id}/rechazar")
def rechazar_autorizacion(
    autorizacion_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    if not tiene_permiso(db, usuario, "seguridad", "gestionar"):
        raise HTTPException(403, "Requiere permiso seguridad/gestionar")
    autorizacion = db.get(Autorizacion, autorizacion_id)
    if not autorizacion:
        raise HTTPException(404, "Solicitud no encontrada")
    return _resolver(db, autorizacion, False, usuario)