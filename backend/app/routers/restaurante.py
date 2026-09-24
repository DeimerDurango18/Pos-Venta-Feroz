from datetime import datetime, timedelta

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
    preparacion: str | None = None
    cortesia: bool = False


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
    total_cortesia = 0.0
    for d in c.detalle:
        linea_total = float(d.precio or 0) * float(d.cantidad or 1)
        if d.cortesia:
            total_cortesia += linea_total
        else:
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
                "cortesia": bool(d.cortesia),
            }
        )
    return {
        "id": c.id,
        "numero": c.numero,
        "mesa_id": c.mesa_id,
        "cliente_id": c.cliente_id,
        "estado": c.estado,
        "total": total,
        "total_cortesia": total_cortesia,
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
                cortesia=linea.cortesia,
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
                cortesia=linea.cortesia,
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


class CortesiaToggle(BaseModel):
    cortesia: bool


@router.post("/comandas/{comanda_id}/lineas/{linea_id}/cortesia")
def toggle_cortesia(
    comanda_id: int,
    linea_id: int,
    data: CortesiaToggle,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    comanda = _get_comanda(db, comanda_id, usuario.empresa_id)
    if comanda.estado != "abierta":
        raise HTTPException(400, "Comanda no válida")
    linea = next((d for d in comanda.detalle if d.id == linea_id), None)
    if not linea:
        raise HTTPException(404, "Línea no encontrada")
    linea.cortesia = data.cortesia
    db.commit()
    return _comanda_out(db, comanda)


class SplitParte(BaseModel):
    linea_ids: list[int]
    medio: str = "efectivo"


class SplitRequest(BaseModel):
    partes: list[SplitParte]


@router.post("/comandas/{comanda_id}/split", status_code=201)
def split_comanda(
    comanda_id: int,
    data: SplitRequest,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    comanda = _get_comanda(db, comanda_id, usuario.empresa_id)
    if comanda.estado != "abierta":
        raise HTTPException(400, "Comanda no válida")
    all_pay_lines = [d for d in comanda.detalle if not d.cortesia]
    used_ids = set()
    ventas_creadas = []
    for parte in data.partes:
        lineas = []
        for lid in parte.linea_ids:
            ln = next((d for d in comanda.detalle if d.id == lid), None)
            if not ln:
                raise HTTPException(404, f"Línea {lid} no encontrada")
            if ln.cortesia:
                raise HTTPException(400, f"Línea {lid} es cortesía, exclúyela del split")
            if lid in used_ids:
                raise HTTPException(400, f"Línea {lid} ya asignada a otra parte")
            used_ids.add(lid)
            lineas.append(ln)
        subtotal = sum(float(d.precio or 0) * float(d.cantidad or 1) for d in lineas)
        if subtotal <= 0:
            continue
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
                    for d in lineas
                ],
                pagos=[VentaPagoCreate(medio=parte.medio, monto=round(subtotal, 2))],
                nota=f"Split {comanda.numero}",
            ),
            db,
            usuario,
        )
        ventas_creadas.append({"venta_id": venta.id, "numero": venta.numero, "total": round(subtotal, 2), "medio": parte.medio})
    unassigned = [d.id for d in all_pay_lines if d.id not in used_ids]
    if unassigned:
        raise HTTPException(400, f"Líneas sin asignar: {unassigned}. Asigna todas las líneas antes de dividir.")
    mesa = db.get(Mesa, comanda.mesa_id)
    comanda.estado = "cerrada"
    if mesa:
        mesa.estado = "disponible"
        mesa.cliente_id = None
        mesa.invitados = 0
    db.commit()
    return {"comanda_id": comanda.id, "estado": "cerrada", "ventas": ventas_creadas}


@router.post("/comandas/{comanda_id}/cerrar", status_code=201)
def cerrar_comanda(
    comanda_id: int,
    pagos: list[dict] | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    comanda = _get_comanda(db, comanda_id, usuario.empresa_id)
    if comanda.estado != "abierta":
        raise HTTPException(400, "Comanda no válida")
    lineas_pago = [d for d in comanda.detalle if not d.cortesia]
    total = sum(float(d.precio or 0) * float(d.cantidad or 1) for d in lineas_pago)
    mesa = db.get(Mesa, comanda.mesa_id)
    pagos_final = pagos or [{"medio": "efectivo", "monto": total}]
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
                for d in lineas_pago
            ],
            pagos=[VentaPagoCreate(medio=p.get("medio", "efectivo"), monto=float(p.get("monto", total))) for p in pagos_final],
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
    mesa = _get_mesa(db, data.mesa_id, usuario.empresa_id)
    if mesa.estado == "ocupada":
        raise HTTPException(400, "La mesa está ocupada en este momento")
    inicio = data.inicio or datetime.now()
    # Evitar doble reserva confirmada de la misma mesa el mismo día
    desde = datetime.combine(inicio.date(), datetime.min.time())
    hasta = datetime.combine(inicio.date() + timedelta(days=1), datetime.min.time())
    conflicto = (
        db.query(ReservaMesa)
        .filter(
            ReservaMesa.mesa_id == data.mesa_id,
            ReservaMesa.estado.in_(["confirmada", "completada"]),
            ReservaMesa.inicio >= desde,
            ReservaMesa.inicio < hasta,
        )
        .first()
    )
    if conflicto:
        raise HTTPException(400, f"La mesa ya tiene una {conflicto.estado} el {inicio.date()}")
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
    db.refresh(reserva)
    return {
        "id": reserva.id,
        "mesa_id": reserva.mesa_id,
        "cliente": reserva.cliente,
        "telefono": reserva.telefono,
        "inicio": reserva.inicio.isoformat() if reserva.inicio else None,
        "estado": reserva.estado,
    }


class ReservaEstadoIn(BaseModel):
    estado: str  # confirmada | completada | cancelada


@router.post("/reservas/{reserva_id}/estado")
def cambiar_estado_reserva(
    reserva_id: int,
    data: ReservaEstadoIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    if data.estado not in ("confirmada", "completada", "cancelada"):
        raise HTTPException(400, "Estado inválido")
    reserva = db.get(ReservaMesa, reserva_id)
    if not reserva or reserva.empresa_id != usuario.empresa_id:
        raise HTTPException(404, "Reserva no encontrada")
    reserva.estado = data.estado
    db.commit()
    return {"id": reserva.id, "estado": reserva.estado}

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