import math

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    Pedido,
    PedidoEstadoTiempo,
    PedidoUbicacion,
    Repartidor,
    RutaEntrega,
    Usuario,
)


class RepartidorCreate(BaseModel):
    nombre: str
    telefono: str | None = None
    placa: str | None = None
    vehiculo: str = "moto"
    lat: float | None = None
    lng: float | None = None


class RutaCreate(BaseModel):
    nombre: str
    tarifa: float = 0
    repartidor_id: int | None = None
    detalle: str | None = None


class GpsUpdate(BaseModel):
    lat: float
    lng: float


class SeguimientoCreate(BaseModel):
    pedido_id: int
    repartidor_id: int
    lat: float
    lng: float
    dest_lat: float | None = None
    dest_lng: float | None = None
    direccion: str | None = None


router = APIRouter(prefix="/domicilios", tags=["domicilios"])

LAT_BASE, LNG_BASE = 4.6762, -74.0487


def _repartidor_out(r, db):
    en_ruta = (
        db.query(PedidoUbicacion)
        .join(Pedido, Pedido.id == PedidoUbicacion.pedido_id)
        .filter(PedidoUbicacion.repartidor_id == r.id, Pedido.estado_domicilio == "en_ruta")
        .count()
    )
    return {
        "id": r.id,
        "nombre": r.nombre,
        "telefono": r.telefono,
        "placa": r.placa,
        "vehiculo": r.vehiculo,
        "lat": r.lat,
        "lng": r.lng,
        "disponible": r.disponible,
        "activo": bool(r.activo),
        "en_ruta": en_ruta,
    }


@router.get("/repartidores")
def listar_repartidores(db: Session = Depends(get_db)):
    return [_repartidor_out(r, db) for r in db.query(Repartidor).order_by(Repartidor.id).all()]


@router.post("/repartidores", status_code=201)
def crear_repartidor(
    data: RepartidorCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    r = Repartidor(
        empresa_id=1,
        nombre=data.nombre,
        telefono=data.telefono,
        placa=data.placa,
        vehiculo=data.vehiculo,
        lat=data.lat if data.lat is not None else LAT_BASE,
        lng=data.lng if data.lng is not None else LNG_BASE,
        disponible="disponible",
        activo=1,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return _repartidor_out(r, db)


@router.post("/repartidores/{repartidor_id}/estado")
def cambiar_estado_repartidor(
    repartidor_id: int,
    disponible: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    r = db.get(Repartidor, repartidor_id)
    if not r:
        raise HTTPException(404, "Repartidor no encontrado")
    if disponible not in ("disponible", "en_ruta", "inactivo"):
        raise HTTPException(400, "Estado inválido")
    r.disponible = disponible
    db.commit()
    return _repartidor_out(r, db)


@router.get("/repartidores/{repartidor_id}/gps")
def ubicacion_repartidor(repartidor_id: int, db: Session = Depends(get_db)):
    r = db.get(Repartidor, repartidor_id)
    if not r:
        raise HTTPException(404, "Repartidor no encontrado")
    return {"id": r.id, "nombre": r.nombre, "lat": r.lat, "lng": r.lng, "disponible": r.disponible}


@router.get("/rutas")
def listar_rutas(db: Session = Depends(get_db)):
    out = []
    for r in db.query(RutaEntrega).order_by(RutaEntrega.id).all():
        rep = db.get(Repartidor, r.repartidor_id) if r.repartidor_id else None
        out.append(
            {
                "id": r.id,
                "nombre": r.nombre,
                "tarifa": float(r.tarifa or 0),
                "repartidor_id": r.repartidor_id,
                "repartidor": rep.nombre if rep else "",
                "detalle": r.detalle,
            }
        )
    return out


@router.post("/rutas", status_code=201)
def crear_ruta(
    data: RutaCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    r = RutaEntrega(
        empresa_id=1,
        nombre=data.nombre,
        tarifa=data.tarifa,
        repartidor_id=data.repartidor_id,
        detalle=data.detalle,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return {"id": r.id, "nombre": r.nombre, "tarifa": float(r.tarifa or 0)}


@router.post("/seguimiento", status_code=201)
def iniciar_seguimiento(
    data: SeguimientoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    pedido = db.get(Pedido, data.pedido_id)
    if not pedido or pedido.tipo != "domicilio":
        raise HTTPException(400, "Pedido domicilio no válido")
    rep = db.get(Repartidor, data.repartidor_id)
    if not rep:
        raise HTTPException(404, "Repartidor no encontrado")

    ub = (
        db.query(PedidoUbicacion)
        .filter(PedidoUbicacion.pedido_id == pedido.id)
        .order_by(PedidoUbicacion.id.desc())
        .first()
    )
    if not ub:
        ub = PedidoUbicacion(pedido_id=pedido.id)
        db.add(ub)
    ub.repartidor_id = rep.id
    ub.lat = data.lat
    ub.lng = data.lng
    ub.latitud_destino = data.dest_lat
    ub.longitud_destino = data.dest_lng
    ub.direccion = data.direccion or pedido.direccion_entrega
    rep.lat = data.lat
    rep.lng = data.lng
    rep.disponible = "en_ruta"
    if pedido.repartidor_id is None and rep.usuario_id:
        pedido.repartidor_id = rep.usuario_id
    if pedido.estado_domicilio in (None, "pendiente"):
        pedido.estado_domicilio = "en_ruta"
        pedido.estado = "en_preparacion"
    db.add(
        PedidoEstadoTiempo(
            pedido_id=pedido.id,
            estado="en_ruta",
            nota="Repartidor asignado y en camino",
            lat=data.lat,
            lng=data.lng,
        )
    )
    db.commit()
    return _ubicacion_out(db, ub, pedido)


def _ubicacion_out(db, ub, pedido):
    rep = None
    if ub.repartidor_id:
        rep = db.get(Repartidor, ub.repartidor_id) if ub.repartidor_id else None
    return {
        "pedido_id": pedido.id,
        "numero": pedido.numero,
        "cliente_id": pedido.cliente_id,
        "total": float(pedido.total or 0),
        "estado_domicilio": pedido.estado_domicilio,
        "repartidor_id": ub.repartidor_id,
        "repartidor": rep.nombre if rep else "",
        "vehiculo": rep.vehiculo if rep else "",
        "lat": ub.lat,
        "lng": ub.lng,
        "dest_lat": ub.latitud_destino,
        "dest_lng": ub.longitud_destino,
        "direccion": ub.direccion,
    }


@router.get("/mapa")
def mapa_domicilios(db: Session = Depends(get_db)):
    rows = (
        db.query(PedidoUbicacion)
        .join(Pedido, Pedido.id == PedidoUbicacion.pedido_id)
        .filter(Pedido.estado_domicilio == "en_ruta")
        .order_by(Pedido.id.desc())
        .all()
    )
    out = []
    for ub in rows:
        pedido = db.get(Pedido, ub.pedido_id)
        out.append(_ubicacion_out(db, ub, pedido))
    return out


@router.post("/pedidos/{pedido_id}/gps")
def actualizar_gps(
    pedido_id: int,
    data: GpsUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    pedido = db.get(Pedido, pedido_id)
    if not pedido:
        raise HTTPException(404, "Pedido no encontrado")
    rep = None
    if pedido.repartidor_id:
        rep = (
            db.query(Repartidor)
            .filter(Repartidor.usuario_id == pedido.repartidor_id)
            .order_by(Repartidor.id.desc())
            .first()
        )
    tipo = (
        db.query(PedidoUbicacion)
        .filter(PedidoUbicacion.pedido_id == pedido.id)
        .order_by(PedidoUbicacion.id.desc())
        .first()
    )
    if not tipo:
        tipo = PedidoUbicacion(pedido_id=pedido.id)
        db.add(tipo)
    if rep:
        tipo.repartidor_id = rep.id
    tipo.lat = data.lat
    tipo.lng = data.lng
    if rep:
        rep.lat = data.lat
        rep.lng = data.lng
    db.add(
        PedidoEstadoTiempo(
            pedido_id=pedido.id,
            estado=pedido.estado_domicilio or "en_ruta",
            nota="Posición GPS actualizada",
            lat=data.lat,
            lng=data.lng,
        )
    )
    db.commit()
    return {"pedido_id": pedido.id, "lat": data.lat, "lng": data.lng}


@router.post("/pedidos/{pedido_id}/simular")
def simular_avance(
    pedido_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Mueve la posición del repartidor un 10% hacia el destino (demo GPS)."""
    pedido = db.get(Pedido, pedido_id)
    if not pedido:
        raise HTTPException(404, "Pedido no encontrado")
    ub = (
        db.query(PedidoUbicacion)
        .filter(PedidoUbicacion.pedido_id == pedido.id)
        .order_by(PedidoUbicacion.id.desc())
        .first()
    )
    if not ub or ub.latitud_destino is None:
        raise HTTPException(400, "El pedido no tiene seguimiento GPS con destino")
    if pedido.estado_domicilio == "entregado":
        raise HTTPException(400, "El pedido ya fue entregado")

    dlat = ub.latitud_destino - ub.lat
    dlng = ub.longitud_destino - ub.lng
    ub.lat += dlat * 0.10
    ub.lng += dlng * 0.10
    rep = None
    if ub.repartidor_id:
        rep = db.get(Repartidor, ub.repartidor_id)
        if rep:
            rep.lat = ub.lat
            rep.lng = ub.lng

    if abs(dlat) < 0.0002 and abs(dlng) < 0.0002:
        pedido.estado_domicilio = "entregado"
        pedido.estado = "entregado"
        if rep:
            rep.disponible = "disponible"
        db.add(PedidoEstadoTiempo(pedido_id=pedido.id, estado="entregado", nota="Entrega completada"))
    else:
        db.add(PedidoEstadoTiempo(pedido_id=pedido.id, estado="en_ruta", nota="Avance simulado", lat=ub.lat, lng=ub.lng))

    db.commit()
    return {"pedido_id": pedido.id, "lat": ub.lat, "lng": ub.lng, "estado_domicilio": pedido.estado_domicilio, "avance": 0.1}


@router.get("/pedidos/{pedido_id}/tracking")
def tracking_pedido(pedido_id: int, db: Session = Depends(get_db)):
    pedido = db.get(Pedido, pedido_id)
    if not pedido:
        raise HTTPException(404, "Pedido no encontrado")
    ub = (
        db.query(PedidoUbicacion)
        .filter(PedidoUbicacion.pedido_id == pedido.id)
        .order_by(PedidoUbicacion.id.desc())
        .first()
    )
    eventos = (
        db.query(PedidoEstadoTiempo)
        .filter(PedidoEstadoTiempo.pedido_id == pedido.id)
        .order_by(PedidoEstadoTiempo.id.desc())
        .limit(20)
        .all()
    )
    return {
        "pedido_id": pedido.id,
        "numero": pedido.numero,
        "estado": pedido.estado,
        "estado_domicilio": pedido.estado_domicilio,
        "ubicacion": _ubicacion_out(db, ub, pedido) if ub else None,
        "eventos": [
            {
                "estado": e.estado,
                "nota": e.nota,
                "lat": e.lat,
                "lng": e.lng,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in eventos
        ],
    }