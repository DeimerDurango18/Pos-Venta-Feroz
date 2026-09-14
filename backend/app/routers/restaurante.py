from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    Comanda,
    ComandaDetalle,
    Mesa,
    Producto,
    ReservaMesa,
    Salon,
    Usuario,
)
from ..schemas.ventas import VentaCreate, VentaDetalleCreate, VentaPagoCreate
from .ventas import crear_venta

router = APIRouter(prefix="/restaurante", tags=["restaurante"])


class SalonCreate(BaseModel):
    nombre: str


class MesaCreate(BaseModel):
    nombre: str
    capacidad: int = 4


class ComandaDetalleCreate(BaseModel):
    producto_id: int
    cantidad: float = 1
    precio: float = 0
    preparacion: str | None = None  # crudo/3/medio/termino/etc


class ComandaCreate(BaseModel):
    mesa_id: int
    cliente_id: int | None = None
    mesero_id: int | None = None
    detalle: list[ComandaDetalleCreate]


class ReservaCreate(BaseModel):
    mesa_id: int
    cliente: str
    telefono: str = ""
    inicio: datetime | None = None


def _get_salon(db: Session, salon_id: int, empresa_id: int) -> Salon:
    salon = db.get(Salon, salon_id)
    if not salon or salon.empresa_id != empresa_id:
        raise HTTPException(404, "Salón no encontrado")
    return salon


def _get_mesa(db: Session, mesa_id: int, empresa_id: int) -> Mesa:
    mesa = db.get(Mesa, mesa_id)
    if not mesa or mesa.salon.empresa_id != empresa_id:
        raise HTTPException(404, "Mesa no encontrada")
    return mesa


def _get_comanda(db: Session, comanda_id: int, empresa_id: int) -> Comanda:
    comanda = db.get(Comanda, comanda_id)
    if not comanda or comanda.empresa_id != empresa_id:
        raise HTTPException(404, "Comanda no encontrada")
    return comanda


# ---------- Salones (408) ----------

@router.get("/salones")
def listar_salones(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    return [
        {
            "id": s.id,
            "nombre": s.nombre,
            "mesas": [
                {"id": m.id, "nombre": m.nombre, "capacidad": m.capacidad, "estado": m.estado}
                for m in s.mesas
            ],
        }
        for s in db.query(Salon)
        .filter(Salon.empresa_id == usuario.empresa_id)
        .order_by(Salon.id)
        .all()
    ]


@router.post("/salones", status_code=201)
def crear_salon(data: SalonCreate, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    salon = Salon(
        empresa_id=usuario.empresa_id,
        sucursal_id=usuario.sucursal_id,
        nombre=data.nombre,
    )
    db.add(salon)
    db.commit()
    return {"id": salon.id, "nombre": salon.nombre}


# ---------- Mesas (410) ----------

@router.post("/mesas", status_code=201)
def crear_mesa(data: MesaCreate, salon_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    _get_salon(db, salon_id, usuario.empresa_id)
    asiento = (
        db.query(Mesa)
        .join(Salon, Mesa.salon_id == Salon.id)
        .filter(Salon.empresa_id == usuario.empresa_id, Mesa.nombre == data.nombre)
        .first()
    )
    if asiento:
        raise HTTPException(400, "Ya existe una mesa con ese nombre en este negocio")
    mesa = Mesa(salon_id=salon_id, nombre=data.nombre, capacidad=data.capacidad, estado="disponible")
    db.add(mesa)
    db.commit()
    return {"id": mesa.id, "nombre": mesa.nombre, "estado": mesa.estado}


@router.get("/mesas")
def listar_mesas(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    mesas = (
        db.query(Mesa)
        .join(Salon, Mesa.salon_id == Salon.id)
        .filter(Salon.empresa_id == usuario.empresa_id)
        .order_by(Mesa.id)
        .all()
    )
    return [
        {
            "id": m.id,
            "salon_id": m.salon_id,
            "nombre": m.nombre,
            "capacidad": m.capacidad,
            "estado": m.estado,
            "cliente_id": m.cliente_id,
            "comanda_abierta": any(c.estado == "abierta" for c in m.comandas),
        }
        for m in mesas
    ]


@router.post("/mesas/{mesa_id}/ocupar")
def ocupar_mesa(mesa_id: int, cliente_id: int | None = None, invitados: int = 0, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    mesa = _get_mesa(db, mesa_id, usuario.empresa_id)
    if mesa.estado == "ocupada":
        raise HTTPException(400, "La mesa ya está ocupada")
    mesa.estado = "ocupada"
    mesa.cliente_id = cliente_id
    mesa.invitados = invitados
    db.commit()
    return {"id": mesa.id, "estado": mesa.estado}


@router.post("/mesas/{mesa_id}/disponible")
def liberar_mesa(mesa_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    mesa = _get_mesa(db, mesa_id, usuario.empresa_id)
    abierta = (
        db.query(Comanda)
        .join(Mesa, Comanda.mesa_id == Mesa.id)
        .join(Salon, Mesa.salon_id == Salon.id)
        .filter(
            Comanda.estado == "abierta",
            Mesa.id == mesa_id,
            Salon.empresa_id == usuario.empresa_id,
        )
        .first()
    )
    if abierta:
        raise HTTPException(400, "Hay una comanda abierta sin cerrar en esta mesa")
    mesa.estado = "disponible"
    mesa.cliente_id = None
    mesa.invitados = 0
    db.commit()
    return {"id": mesa.id, "estado": mesa.estado}


# ---------- Comandas (411) ----------

def _comanda_out(db, c):
    detalle = []
    total = 0.0
    for d in c.detalle:
        linea_total = float(d.precio or 0) * float(d.cantidad or 1)
        total += linea_total
        detalle.append(
            {
                "id": d.id,
                "producto_id": d.producto_id,
                "producto": db.get(Producto, d.producto_id).nombre if d.producto_id else "",
                "cantidad": float(d.cantidad or 0),
                "precio": float(d.precio or 0),
                "preparacion": d.preparacion,
                "entregado": bool(d.entregado),
            }
        )
    return {
        "id": c.id,
        "numero": c.numero,
        "mesa_id": c.mesa_id,
        "cliente_id": c.cliente_id,
        "estado": c.estado,
        "total": total,
        "detalle": detalle,
    }


@router.post("/comandas", status_code=201)
def crear_comanda(
    data: ComandaCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    mesa = _get_mesa(db, data.mesa_id, usuario.empresa_id)
    if (
        db.query(Comanda)
        .join(Mesa, Comanda.mesa_id == Mesa.id)
        .join(Salon, Mesa.salon_id == Salon.id)
        .filter(
            Comanda.mesa_id == data.mesa_id,
            Comanda.estado == "abierta",
            Salon.empresa_id == usuario.empresa_id,
        )
        .first()
    ):
        raise HTTPException(400, "La mesa ya tiene una comanda abierta")
    if not data.detalle:
        raise HTTPException(400, "La comanda requiere al menos un producto")
    comanda = Comanda(
        empresa_id=usuario.empresa_id,
        mesa_id=data.mesa_id,
        cliente_id=data.cliente_id,
        mesero_id=data.mesero_id or usuario.id,
        estado="abierta",
    )
    db.add(comanda)
    db.flush()
    comanda.numero = f"CM-{comanda.id:06d}"
    for linea in data.detalle:
        if not db.get(Producto, linea.producto_id):
            raise HTTPException(404, f"Producto {linea.producto_id} no encontrado")
        db.add(
            ComandaDetalle(
                comanda_id=comanda.id,
                producto_id=linea.producto_id,
                cantidad=linea.cantidad,
                precio=linea.precio,
                preparacion=linea.preparacion,
                entregado=False,
            )
        )
    if mesa.estado == "disponible":
        mesa.estado = "ocupada"
    mesa.cliente_id = data.cliente_id
    db.commit()
    db.refresh(comanda)
    return _comanda_out(db, comanda)


@router.get("/comandas")
def listar_comandas(
    estado: str | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    q = (
        db.query(Comanda)
        .filter(Comanda.empresa_id == usuario.empresa_id)
        .order_by(Comanda.id.desc())
    )
    if estado:
        q = q.filter(Comanda.estado == estado)
    q = q.limit(100)
    return [_comanda_out(db, c) for c in q.all()]


@router.get("/comandas/{comanda_id}")
def detalle_comanda(
    comanda_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    comanda = _get_comanda(db, comanda_id, usuario.empresa_id)
    return _comanda_out(db, comanda)


@router.post("/comandas/{comanda_id}/agregar", status_code=201)
def agregar_a_comanda(
    comanda_id: int,
    data: list[ComandaDetalleCreate],
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    comanda = _get_comanda(db, comanda_id, usuario.empresa_id)
    if comanda.estado != "abierta":
        raise HTTPException(400, "Comanda no válida")
    for linea in data:
        if not db.get(Producto, linea.producto_id):
            raise HTTPException(404, f"Producto {linea.producto_id} no encontrado")
        db.add(
            ComandaDetalle(
                comanda_id=comanda.id,
                producto_id=linea.producto_id,
                cantidad=linea.cantidad,
                precio=linea.precio,
                preparacion=linea.preparacion,
                entregado=False,
            )
        )
    db.commit()
    return _comanda_out(db, comanda)


@router.post("/comandas/{comanda_id}/lineas/{linea_id}/servir")
def servir_linea(
    comanda_id: int,
    linea_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    comanda = _get_comanda(db, comanda_id, usuario.empresa_id)
    linea = next((d for d in comanda.detalle if d.id == linea_id), None)
    if not linea:
        raise HTTPException(404, "Línea no encontrada")
    linea.entregado = True
    db.commit()
    return {"linea_id": linea.id, "entregado": True}


@router.post("/comandas/{comanda_id}/cerrar", status_code=201)
def cerrar_comanda(
    comanda_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    comanda = _get_comanda(db, comanda_id, usuario.empresa_id)
    if comanda.estado != "abierta":
        raise HTTPException(400, "Comanda no válida")
    total = sum(float(d.precio or 0) * float(d.cantidad or 1) for d in comanda.detalle)
    mesa = db.get(Mesa, comanda.mesa_id)
    venta = crear_venta(
        VentaCreate(
            empresa_id=usuario.empresa_id,
            sucursal_id=usuario.sucursal_id,
            cliente_id=comanda.cliente_id,
            tipo="contado",
            caja_id=None,
            vendedor_id=usuario.id,
            detalle=[
                VentaDetalleCreate(
                    producto_id=d.producto_id,
                    cantidad=d.cantidad,
                    precio=d.precio,
                    descuento=0,
                )
                for d in comanda.detalle
            ],
            pagos=[VentaPagoCreate(medio="efectivo", monto=total)],
            nota=f"Comanda {comanda.numero}",
        ),
        db,
        usuario,
    )
    comanda.estado = "cerrada"
    comanda.venta_id = venta.id
    if mesa:
        mesa.estado = "disponible"
        mesa.cliente_id = None
        mesa.invitados = 0
    db.commit()
    return {"comanda_id": comanda.id, "estado": "cerrada", "venta_id": venta.id, "numero_venta": venta.numero, "total": total}


# ---------- Reservas (413-414) ----------

@router.get("/reservas")
def listar_reservas(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    reservas = (
        db.query(ReservaMesa)
        .join(Mesa, ReservaMesa.mesa_id == Mesa.id)
        .join(Salon, Mesa.salon_id == Salon.id)
        .filter(Salon.empresa_id == usuario.empresa_id)
        .order_by(ReservaMesa.inicio.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": r.id,
            "mesa_id": r.mesa_id,
            "cliente": r.cliente,
            "telefono": r.telefono,
            "inicio": r.inicio.isoformat() if r.inicio else None,
            "estado": r.estado,
        }
        for r in reservas
    ]


@router.post("/reservas", status_code=201)
def crear_reserva(data: ReservaCreate, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    _get_mesa(db, data.mesa_id, usuario.empresa_id)
    inicio = data.inicio or datetime.now()
    reserva = ReservaMesa(
        empresa_id=usuario.empresa_id,
        mesa_id=data.mesa_id,
        cliente=data.cliente,
        telefono=data.telefono,
        inicio=inicio,
        estado="confirmada",
    )
    db.add(reserva)
    db.commit()
    return {"id": reserva.id, "mesa_id": reserva.mesa_id, "cliente": reserva.cliente, "inicio": inicio.isoformat()}

# ---------- Seguridad ----------


@router.get("/seguridad")
def resumen_restaurante(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    return {
        "salones": int(db.query(Salon).filter(Salon.empresa_id == usuario.empresa_id).count()),
        "mesas": int(
            db.query(Mesa)
            .join(Salon, Mesa.salon_id == Salon.id)
            .filter(Salon.empresa_id == usuario.empresa_id)
            .count()
        ),
        "mesas_ocupadas": int(
            db.query(Mesa)
            .join(Salon, Mesa.salon_id == Salon.id)
            .filter(Salon.empresa_id == usuario.empresa_id, Mesa.estado == "ocupada")
            .count()
        ),
        "comandas_abiertas": int(
            db.query(Comanda).filter(Comanda.empresa_id == usuario.empresa_id, Comanda.estado == "abierta").count()
        ),
        "reservas_hoy": int(
            db.query(ReservaMesa)
            .join(Mesa, ReservaMesa.mesa_id == Mesa.id)
            .join(Salon, Mesa.salon_id == Salon.id)
            .filter(Salon.empresa_id == usuario.empresa_id, ReservaMesa.estado == "confirmada")
            .count()
        ),
    }