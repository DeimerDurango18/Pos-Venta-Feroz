from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Promocion, PromocionProducto, Usuario
from ..deps import get_current_user
from ..schemas.avanzado import PromocionCreate, PromocionOut

router = APIRouter(prefix="/promociones", tags=["promociones"])


@router.get("", response_model=list[PromocionOut])
def listar_promociones(activa: bool | None = None, db: Session = Depends(get_db)):
    q = db.query(Promocion)
    if activa is not None:
        q = q.filter(Promocion.activa == activa)
    return q.order_by(Promocion.id.desc()).all()


@router.post("", response_model=PromocionOut, status_code=201)
def crear_promocion(
    data: PromocionCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    prom = Promocion(
        empresa_id=data.empresa_id,
        nombre=data.nombre,
        tipo=data.tipo,
        valor=data.valor,
        aplica_a=data.aplica_a,
        categoria_id=data.categoria_id,
        desde=data.desde,
        hasta=data.hasta,
        hora_desde=data.hora_desde,
        hora_hasta=data.hora_hasta,
        descripcion=data.descripcion,
        activa=data.activa,
        cliente_id=data.cliente_id,
        cantidad_minima=data.cantidad_minima,
    )
    db.add(prom)
    db.flush()
    for p in data.productos:
        db.add(PromocionProducto(promocion_id=prom.id, producto_id=p.producto_id))
    db.commit()
    db.refresh(prom)
    return prom


@router.get("/{promocion_id}", response_model=PromocionOut)
def obtener_promocion(promocion_id: int, db: Session = Depends(get_db)):
    prom = db.get(Promocion, promocion_id)
    if not prom:
        raise HTTPException(404, "Promoción no encontrada")
    return prom


@router.put("/{promocion_id}", response_model=PromocionOut)
def actualizar_promocion(
    promocion_id: int,
    data: PromocionCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    prom = db.get(Promocion, promocion_id)
    if not prom:
        raise HTTPException(404, "Promoción no encontrada")
    prom.nombre = data.nombre
    prom.tipo = data.tipo
    prom.valor = data.valor
    prom.aplica_a = data.aplica_a
    prom.categoria_id = data.categoria_id
    prom.desde = data.desde
    prom.hasta = data.hasta
    prom.hora_desde = data.hora_desde
    prom.hora_hasta = data.hora_hasta
    prom.descripcion = data.descripcion
    prom.activa = data.activa
    prom.cliente_id = data.cliente_id
    prom.productos.clear()
    for p in data.productos:
        db.add(PromocionProducto(promocion_id=prom.id, producto_id=p.producto_id))
    db.commit()
    db.refresh(prom)
    return prom


@router.post("/{promocion_id}/toggle")
def toggle_promocion(
    promocion_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    prom = db.get(Promocion, promocion_id)
    if not prom:
        raise HTTPException(404, "Promoción no encontrada")
    prom.activa = not prom.activa
    db.commit()
    return {"activa": prom.activa}