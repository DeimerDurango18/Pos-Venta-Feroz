from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    AuditoriaLog,
    MovimientoInventario,
    Producto,
    ProductoComponente,
    ProduccionDetalle,
    ProduccionOrden,
    Stock,
    Usuario,
)

router = APIRouter(prefix="/produccion", tags=["produccion"])


class OrdenProduccionCreate(BaseModel):
    empresa_id: int = 1
    sucursal_id: int = 1
    producto_id: int
    cantidad: float = 1


def _out(db, orden):
    producto = db.get(Producto, orden.producto_id)
    componentes = []
    for d in orden.detalle:
        mp = db.get(Producto, d.producto_id)
        componentes.append(
            {
                "producto_id": d.producto_id,
                "materia_prima": mp.nombre if mp else "?",
                "cantidad": float(d.cantidad or 0),
                "costo_unitario": float(d.costo_unitario or 0),
            }
        )
    return {
        "id": orden.id,
        "numero": orden.numero,
        "sucursal_id": orden.sucursal_id,
        "producto_id": orden.producto_id,
        "producto": producto.nombre if producto else "?",
        "cantidad": float(orden.cantidad or 1),
        "costo_total": float(orden.costo_total or 0),
        "estado": orden.estado,
        "created_at": orden.created_at.isoformat() if orden.created_at else None,
        "detalle": componentes,
    }


@router.post("", status_code=201)
def crear_orden_produccion(
    data: OrdenProduccionCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    from ..seguridad import requiere_autorizacion

    requiere_autorizacion(db, usuario, "inventario", "ajustar", entidad="produccion")
    if data.cantidad <= 0:
        raise HTTPException(400, "La cantidad debe ser mayor que 0")
    terminado = db.get(Producto, data.producto_id)
    if not terminado:
        raise HTTPException(404, "Producto no encontrado")
    if not terminado.es_compuesto:
        raise HTTPException(400, "El producto no es compuesto (no tiene materias primas)")
    componentes = (
        db.query(ProductoComponente)
        .filter(ProductoComponente.producto_id == data.producto_id)
        .all()
    )
    if not componentes:
        raise HTTPException(400, "El producto no tiene materias primas configuradas")

    # Verificar disponibilidad de materias primas
    para_consumir = []
    costo_total = 0.0
    for c in componentes:
        mp = db.get(Producto, c.componente_id)
        necesario = float(c.cantidad or 1) * data.cantidad
        stock = (
            db.query(Stock)
            .filter_by(producto_id=c.componente_id, sucursal_id=data.sucursal_id)
            .first()
        )
        if not stock or float(stock.existencias or 0) < necesario:
            raise HTTPException(
                400,
                f"Materia prima insuficiente para {mp.nombre if mp else c.componente_id} "
                f"(requerido {necesario})",
            )
        costo_total += (float(mp.costo or 0) if mp else 0) * necesario
        para_consumir.append((c.componente_id, necesario, float(mp.costo or 0) if mp else 0))

    # Consumir materias primas
    for producto_id_mp, necesario, costo_u in para_consumir:
        stock = db.query(Stock).filter_by(producto_id=producto_id_mp, sucursal_id=data.sucursal_id).first()
        stock.existencias = float(stock.existencias or 0) - necesario
        stock.disponible = stock.existencias - float(stock.reservado or 0)
        db.add(
            MovimientoInventario(
                producto_id=producto_id_mp,
                sucursal_id=data.sucursal_id,
                tipo="salida",
                cantidad=-necesario,
                motivo="Producción",
                referencia="produccion",
                saldo=float(stock.existencias),
            )
        )

    # Generar producto terminado
    stock_term = db.query(Stock).filter_by(producto_id=data.producto_id, sucursal_id=data.sucursal_id).first()
    if not stock_term:
        stock_term = Stock(producto_id=data.producto_id, sucursal_id=data.sucursal_id)
        db.add(stock_term)
        db.flush()
    stock_term.existencias = float(stock_term.existencias or 0) + data.cantidad
    stock_term.disponible = stock_term.existencias - float(stock_term.reservado or 0)
    db.add(
        MovimientoInventario(
            producto_id=data.producto_id,
            sucursal_id=data.sucursal_id,
            tipo="entrada",
            cantidad=data.cantidad,
            motivo="Producción",
            referencia="produccion",
            saldo=float(stock_term.existencias),
        )
    )

    orden = ProduccionOrden(
        empresa_id=data.empresa_id,
        sucursal_id=data.sucursal_id,
        producto_id=data.producto_id,
        usuario_id=usuario.id,
        cantidad=data.cantidad,
        costo_total=costo_total,
        estado="procesada",
    )
    db.add(orden)
    db.flush()
    orden.numero = f"PR-{orden.id:06d}"
    for producto_id_mp, necesario, costo_u in para_consumir:
        db.add(
            ProduccionDetalle(
                produccion_id=orden.id,
                producto_id=producto_id_mp,
                cantidad=necesario,
                costo_unitario=costo_u,
            )
        )
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="produccion",
            accion="producir",
            entidad="produccion_orden",
            entidad_id=orden.id,
            detalle=f"Orden {orden.numero}: {data.cantidad} de {terminado.nombre}",
        )
    )
    db.commit()
    db.refresh(orden)
    return _out(db, orden)


@router.get("")
def listar_produccion(
    sucursal_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(ProduccionOrden)
    if sucursal_id:
        q = q.filter(ProduccionOrden.sucursal_id == sucursal_id)
    ordenes = q.order_by(ProduccionOrden.id.desc()).limit(100).all()
    return [_out(db, o) for o in ordenes]


@router.get("/resumen")
def resumen_produccion(db: Session = Depends(get_db)):
    """Materias primas consumidas, producción y desperdicios (mermas)."""
    from sqlalchemy import func

    producido = (
        db.query(
            Producto.nombre,
            func.sum(ProduccionOrden.cantidad).label("cantidad"),
            func.sum(ProduccionOrden.costo_total).label("costo"),
        )
        .join(Producto, Producto.id == ProduccionOrden.producto_id)
        .group_by(Producto.nombre)
        .all()
    )
    materias = (
        db.query(
            Producto.nombre,
            func.sum(ProduccionDetalle.cantidad).label("cantidad"),
        )
        .join(Producto, Producto.id == ProduccionDetalle.producto_id)
        .group_by(Producto.nombre)
        .all()
    )
    mermas = (
        db.query(
            Producto.nombre,
            func.sum(MovimientoInventario.cantidad).label("cantidad"),
        )
        .join(Producto, Producto.id == MovimientoInventario.producto_id)
        .filter(MovimientoInventario.tipo == "merma")
        .group_by(Producto.nombre)
        .all()
    )
    return {
        "producido": [
            {"producto": n, "cantidad": float(c or 0), "costo": float(ct or 0)}
            for n, c, ct in producido
        ],
        "materias_primas": [
            {"materia_prima": n, "cantidad": float(c or 0)} for n, c in materias
        ],
        "desperdicios": [
            {"producto": n, "cantidad": float(-c or 0)} for n, c in mermas
        ],
    }