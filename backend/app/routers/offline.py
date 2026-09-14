from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    Cliente,
    PendienteSincronizacion,
    Producto,
    Stock,
    Usuario,
    Venta,
)
from ..schemas.ventas import VentaCreate, VentaDetalleCreate, VentaPagoCreate

router = APIRouter(prefix="/offline", tags=["operación offline y sincronización"])


class PendienteCreate(BaseModel):
    cliente_uuid: str
    tipo: str = "venta"
    payload: dict


@router.get("/catalogo")
def catalogo_offline(
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    """Instantánea compacta para operar sin conexión (catálogo, stock y clientes)."""
    stocks = dict(
        db.query(Stock.producto_id, func.coalesce(func.sum(Stock.existencias), 0))
        .group_by(Stock.producto_id)
        .all()
    )
    productos = db.query(Producto).filter(Producto.activo == True).all()
    return {
        "productos": [
            {
                "id": p.id,
                "nombre": p.nombre,
                "codigo_barras": p.codigo_barras,
                "sku": p.sku,
                "precio_venta": float(p.precio_venta or 0),
                "costo": float(p.costo or 0),
                "impuesto": float(p.impuesto or 0),
                "existencias": float(stocks.get(p.id, 0) or 0),
            }
            for p in productos
        ],
        "clientes": [
            {"id": c.id, "nombre": c.nombre, "creditos": float(c.creditos or 0)}
            for c in db.query(Cliente).all()
        ],
    }


@router.get("/pendientes")
def listar_pendientes(
    estado: str | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    q = db.query(PendienteSincronizacion)
    if estado:
        q = q.filter(PendienteSincronizacion.estado == estado)
    q = q.order_by(PendienteSincronizacion.id.asc())
    return [
        {
            "id": p.id,
            "cliente_uuid": p.cliente_uuid,
            "tipo": p.tipo,
            "estado": p.estado,
            "error": p.error,
            "resultado_id": p.resultado_id,
            "payload": p.payload,
            "created_at": str(p.created_at),
        }
        for p in q.all()
    ]


@router.post("/pendientes", status_code=201)
def crear_pendiente(
    data: PendienteCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    dup = (
        db.query(PendienteSincronizacion)
        .filter(PendienteSincronizacion.cliente_uuid == data.cliente_uuid)
        .first()
    )
    if dup:
        return {
            "id": dup.id,
            "ya_existia": True,
            "estado": dup.estado,
            "resultado_id": dup.resultado_id,
        }
    p = PendienteSincronizacion(cliente_uuid=data.cliente_uuid, tipo=data.tipo, payload=data.payload)
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"id": p.id, "ya_existia": False, "estado": p.estado}


def _aplicar(db: Session, p: PendienteSincronizacion, usuario: Usuario):
    """Replica la operación registrada offline (hoy: ventas) en el servidor."""
    if p.tipo == "venta":
        detalle = p.payload.get("detalle") or []
        pagos = p.payload.get("pagos") or []
        data = VentaCreate(
            empresa_id=int(p.payload.get("empresa_id", 1)),
            sucursal_id=int(p.payload.get("sucursal_id", 1)),
            caja_id=p.payload.get("caja_id"),
            punto_venta_id=p.payload.get("punto_venta_id"),
            cliente_id=p.payload.get("cliente_id"),
            tipo=p.payload.get("tipo", "contado"),
            descuento_global=float(p.payload.get("descuento_global", 0) or 0),
            propina=float(p.payload.get("propina", 0) or 0),
            nota=p.payload.get("nota"),
            cupon_codigo=p.payload.get("cupon_codigo"),
            detalle=[
                VentaDetalleCreate(
                    producto_id=int(d["producto_id"]),
                    cantidad=float(d["cantidad"]),
                    precio=d.get("precio"),
                    descuento=float(d.get("descuento", 0) or 0),
                )
                for d in detalle
            ],
            pagos=[
                VentaPagoCreate(
                    medio=pg.get("medio", "efectivo"),
                    monto=float(pg["monto"]),
                    referencia=pg.get("referencia"),
                )
                for pg in pagos
            ],
        )
        from .ventas import crear_venta

        venta = crear_venta(data, db, usuario)
        p.resultado_id = venta.id
        return {"id": venta.id, "numero": venta.numero, "total": float(venta.total)}
    raise HTTPException(400, f"Tipo de operación offline no soportado: {p.tipo}")


@router.post("/pendientes/{pid}/sincronizar")
def sincronizar_pendiente(
    pid: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    p = db.get(PendienteSincronizacion, pid)
    if not p:
        raise HTTPException(404, "Operación pendiente no encontrada")
    if p.estado == "sincronizada":
        return {"ok": True, "id": p.id, "ya_sincronizada": True, "resultado_id": p.resultado_id}
    try:
        res = _aplicar(db, p, usuario)
        p.estado = "sincronizada"
        p.error = None
        p.sincronizada_at = datetime.now()
        db.commit()
        return {"ok": True, "id": p.id, "tipo": p.tipo, "resultado": res}
    except Exception as e:  # noqa: BLE001
        db.rollback()
        p = db.get(PendienteSincronizacion, pid)
        p.estado = "error"
        p.error = str(e)[:250]
        db.commit()
        raise HTTPException(422, f"Error al sincronizar: {str(e)[:250]}")


@router.post("/sincronizar")
def sincronizar_todo(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Replica todas las operaciones offline pendientes en orden."""
    pendientes = (
        db.query(PendienteSincronizacion)
        .filter(PendienteSincronizacion.estado == "pendiente")
        .order_by(PendienteSincronizacion.id.asc())
        .all()
    )
    sincronizadas = []
    errores = []
    for p in pendientes:
        try:
            res = _aplicar(db, p, usuario)
            p.estado = "sincronizada"
            p.error = None
            p.sincronizada_at = datetime.now()
            db.commit()
            sincronizadas.append({"id": p.id, "tipo": p.tipo, "resultado": res})
        except Exception as e:  # noqa: BLE001
            db.rollback()
            p = db.get(PendienteSincronizacion, p.id)
            p.estado = "error"
            p.error = str(e)[:250]
            db.commit()
            errores.append({"id": p.id, "error": str(e)[:250]})
    return {
        "procesadas": len(sincronizadas),
        "errores": len(errores),
        "sincronizadas": sincronizadas,
        "pendientes_que_fallaron": errores,
    }


@router.get("/novedades")
def novedades(
    desde: str | None = Query(None),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    """Delta de datos nuevos desde una fecha (usado para sincronizar dispositivos)."""
    try:
        fdesde = datetime.fromisoformat(desde) if desde else datetime.now() - timedelta(days=30)
    except ValueError:
        raise HTTPException(400, "Formato de 'desde' inválido (use ISO, ej. 2026-09-01T00:00:00)")
    ventas = (
        db.query(Venta)
        .filter(Venta.estado == "completada", Venta.created_at >= fdesde)
        .order_by(Venta.id.desc())
        .limit(200)
        .all()
    )
    sincronizadas = (
        db.query(PendienteSincronizacion)
        .filter(PendienteSincronizacion.sincronizada_at >= fdesde)
        .order_by(PendienteSincronizacion.id.asc())
        .all()
    )
    return {
        "desde": str(fdesde),
        "ventas_nuevas": [
            {
                "id": v.id,
                "numero": v.numero,
                "cliente_id": v.cliente_id,
                "total": float(v.total),
                "estado": v.estado,
                "created_at": str(v.created_at),
            }
            for v in ventas
        ],
        "sincronizaciones": [
            {"id": s.id, "tipo": s.tipo, "resultado_id": s.resultado_id, "estado": s.estado}
            for s in sincronizadas
        ],
        "clientes": [
            {"id": c.id, "nombre": c.nombre, "creditos": float(c.creditos or 0)}
            for c in db.query(Cliente).all()
        ],
    }