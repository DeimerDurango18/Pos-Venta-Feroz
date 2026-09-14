from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    AuditoriaLog,
    Pedido,
    PedidoDetalle,
    Producto,
    Stock,
    Usuario,
)


class PedidoDetalleCreate(BaseModel):
    producto_id: int
    cantidad: float = 1
    precio: float = 0


class PedidoCreate(BaseModel):
    cliente_id: int | None = None
    tipo: str = "mostrador"  # mostrador, domicilio
    direccion_entrega: str | None = None
    costo_domicilio: float = 0
    repartidor_id: int | None = None
    plato_principal: int | None = None
    nota: str | None = None
    detalle: list[PedidoDetalleCreate]


router = APIRouter(prefix="/pedidos", tags=["pedidos"])


def _detalle(db, pedido):
    return [
        {
            "id": d.id,
            "producto_id": d.producto_id,
            "producto": db.get(Producto, d.producto_id).nombre if d.producto_id else "",
            "cantidad": float(d.cantidad or 0),
            "precio": float(d.precio or 0),
        }
        for d in pedido.detalle
    ]


def _to_out(db, p):
    repartidor = db.get(Usuario, p.repartidor_id) if p.repartidor_id else None
    return {
        "id": p.id,
        "numero": p.numero,
        "cliente_id": p.cliente_id,
        "tipo": p.tipo,
        "estado": p.estado,
        "estado_domicilio": p.estado_domicilio,
        "direccion_entrega": p.direccion_entrega,
        "costo_domicilio": float(p.costo_domicilio or 0),
        "repartidor_id": p.repartidor_id,
        "repartidor": repartidor.nombre if repartidor else "",
        "plato_principal": p.plato_principal,
        "nota": p.nota,
        "total": float(p.total or 0),
        "detalle": _detalle(db, p),
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _get_pedido(db: Session, pedido_id: int, empresa_id: int) -> Pedido:
    pedido = db.get(Pedido, pedido_id)
    if not pedido or pedido.empresa_id != empresa_id:
        raise HTTPException(404, "Pedido no encontrado")
    return pedido


def _recalcular(db, pedido):
    total = sum(float(d.precio or 0) * float(d.cantidad or 1) for d in pedido.detalle)
    if pedido.tipo == "domicilio":
        total += float(pedido.costo_domicilio or 0)
    pedido.total = total


@router.get("")
def listar_pedidos(
    estado: str | None = None,
    tipo: str | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    q = (
        db.query(Pedido)
        .filter(Pedido.empresa_id == usuario.empresa_id)
        .order_by(Pedido.id.desc())
    )
    if estado:
        q = q.filter(Pedido.estado == estado)
    if tipo:
        q = q.filter(Pedido.tipo == tipo)
    q = q.limit(100)
    return [_to_out(db, p) for p in q.all()]


@router.get("/domicilios/resumen")
def resumen_domicilios(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    base = db.query(Pedido).filter(Pedido.empresa_id == usuario.empresa_id, Pedido.tipo == "domicilio")
    pendientes = base.filter(Pedido.estado_domicilio == "pendiente").count()
    en_ruta = base.filter(Pedido.estado_domicilio == "en_ruta").count()
    entregados = base.filter(Pedido.estado_domicilio == "entregado").count()
    return {"pendientes": pendientes, "en_ruta": en_ruta, "entregados": entregados}


@router.get("/{pedido_id}")
def detalle_pedido(
    pedido_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    pedido = _get_pedido(db, pedido_id, usuario.empresa_id)
    return _to_out(db, pedido)


@router.post("", status_code=201)
def crear_pedido(
    data: PedidoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    if not data.detalle:
        raise HTTPException(400, "El pedido requiere al menos un producto")
    pedido = Pedido(
        empresa_id=usuario.empresa_id,
        sucursal_id=usuario.sucursal_id,
        cliente_id=data.cliente_id,
        usuario_id=usuario.id,
        tipo=data.tipo,
        estado="pendiente",
        direccion_entrega=data.direccion_entrega,
        costo_domicilio=data.costo_domicilio,
        repartidor_id=data.repartidor_id,
        plato_principal=data.plato_principal,
        nota=data.nota,
        total=0,
    )
    if data.tipo == "domicilio":
        pedido.estado_domicilio = "pendiente"
    db.add(pedido)
    db.flush()
    pedido.numero = f"PD-{pedido.id:06d}"
    for linea in data.detalle:
        producto = db.get(Producto, linea.producto_id)
        if not producto:
            raise HTTPException(404, f"Producto {linea.producto_id} no encontrado")
        precio = linea.precio if linea.precio else float(producto.precio_venta or 0)
        pedido.total = float(pedido.total or 0) + precio * float(linea.cantidad or 1)
        db.add(
            PedidoDetalle(
                pedido_id=pedido.id,
                producto_id=linea.producto_id,
                cantidad=linea.cantidad,
                precio=precio,
            )
        )
    if data.tipo == "domicilio":
        pedido.total = float(pedido.total or 0) + float(pedido.costo_domicilio or 0)
    db.commit()
    db.refresh(pedido)
    return _to_out(db, pedido)


@router.post("/{pedido_id}/estado")
def cambiar_estado_pedido(
    pedido_id: int,
    estado: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    pedido = _get_pedido(db, pedido_id, usuario.empresa_id)
    estados = ("pendiente", "en_preparacion", "listo", "entregado", "cancelado")
    if estado not in estados:
        raise HTTPException(400, f"Estado inválido, use: {', '.join(estados)}")
    pedido.estado = estado
    db.commit()
    return {"id": pedido.id, "estado": pedido.estado}


@router.post("/{pedido_id}/despachar")
def despachar_domicilio(
    pedido_id: int,
    repartidor_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    pedido = _get_pedido(db, pedido_id, usuario.empresa_id)
    if pedido.tipo != "domicilio":
        raise HTTPException(400, "Pedido no válido")
    if not db.get(Usuario, repartidor_id):
        raise HTTPException(404, "Repartidor no encontrado")
    pedido.repartidor_id = repartidor_id
    if pedido.estado == "entregado":
        raise HTTPException(400, "El pedido ya fue entregado")
    if not pedido.estado_domicilio or pedido.estado_domicilio == "pendiente":
        pedido.estado_domicilio = "en_ruta"
    db.commit()
    return {"id": pedido.id, "estado_domicilio": pedido.estado_domicilio, "repartidor_id": repartidor_id}


@router.post("/{pedido_id}/estado-domicilio")
def estado_domicilio(
    pedido_id: int,
    estado: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    pedido = _get_pedido(db, pedido_id, usuario.empresa_id)
    if pedido.tipo != "domicilio":
        raise HTTPException(400, "Pedido no válido")
    estados = ("pendiente", "en_ruta", "entregado")
    if estado not in estados:
        raise HTTPException(400, "Estado de domicilio inválido")
    pedido.estado_domicilio = estado
    if estado == "entregado":
        pedido.estado = "entregado"
    db.commit()
    return {"id": pedido.id, "estado_domicilio": pedido.estado_domicilio}


@router.post("/{pedido_id}/entregar")
def entregar_pedido(
    pedido_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    pedido = _get_pedido(db, pedido_id, usuario.empresa_id)
    if pedido.estado == "cancelado":
        raise HTTPException(400, "Pedido no válido")
    stock_ok = True
    for linea in pedido.detalle:
        stock = (
            db.query(Stock)
            .filter(
                Stock.producto_id == linea.producto_id,
                Stock.sucursal_id == usuario.sucursal_id,
            )
            .first()
        )
        if not stock or float(stock.existencias or 0) < float(linea.cantidad or 0):
            stock_ok = False
            break
    if not stock_ok:
        raise HTTPException(400, "Stock insuficiente para entregar el pedido")
    for linea in pedido.detalle:
        stock = (
            db.query(Stock)
            .filter(
                Stock.producto_id == linea.producto_id,
                Stock.sucursal_id == usuario.sucursal_id,
            )
            .first()
        )
        stock.existencias = float(stock.existencias or 0) - float(linea.cantidad or 1)
        stock.disponible = stock.existencias - float(stock.reservado or 0)
    pedido.estado = "entregado"
    if pedido.tipo == "domicilio":
        pedido.estado_domicilio = "entregado"
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="pedidos",
            accion="entregar",
            entidad="pedido",
            entidad_id=pedido.id,
            detalle=f"Entregado pedido {pedido.numero}",
        )
    )
    db.commit()
    return {"id": pedido.id, "estado": pedido.estado, "total": float(pedido.total or 0)}