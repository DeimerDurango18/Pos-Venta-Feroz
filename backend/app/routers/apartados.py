from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    Apartado,
    ApartadoAbono,
    ApartadoDetalle,
    AuditoriaLog,
    Producto,
    Stock,
    Usuario,
)
from ..schemas.ventas import VentaCreate, VentaDetalleCreate, VentaPagoCreate
from .ventas import crear_venta

router = APIRouter(prefix="/apartados", tags=["apartados"])


class ApartadoDetalleCreate(BaseModel):
    producto_id: int
    cantidad: float = 1
    precio: float = 0


class ApartadoCreate(BaseModel):
    cliente_id: int
    abono_inicial: float = 0
    fecha_compromiso: date | None = None
    nota: str | None = None
    detalle: list[ApartadoDetalleCreate]


class ApartadoAbonoCreate(BaseModel):
    monto: float


def _detalle_apartado(db, apartado):
    return [
        {
            "id": d.id,
            "producto_id": d.producto_id,
            "producto": db.get(Producto, d.producto_id).nombre if d.producto_id else "",
            "cantidad": float(d.cantidad or 0),
            "precio": float(d.precio or 0),
            "descuento": float(d.descuento or 0),
        }
        for d in apartado.detalle
    ]


def _abonos(db, apartado):
    return [
        {"id": a.id, "monto": float(a.monto), "fecha": a.created_at.isoformat() if a.created_at else None}
        for a in apartado.abonos
    ]


def _out(db, apartado):
    return {
        "id": apartado.id,
        "numero": apartado.numero,
        "cliente_id": apartado.cliente_id,
        "estado": apartado.estado,
        "fecha_compromiso": apartado.fecha_compromiso.isoformat() if apartado.fecha_compromiso else None,
        "nota": apartado.nota,
        "total": float(apartado.total or 0),
        "abonado": float(apartado.abonado or 0),
        "pendiente": float(apartado.pendiente or 0),
        "venta_id": apartado.venta_id,
        "detalle": _detalle_apartado(db, apartado),
        "abonos": _abonos(db, apartado),
    }


@router.get("")
def listar_apartados(
    estado: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Apartado).order_by(Apartado.id.desc())
    if estado:
        q = q.filter(Apartado.estado == estado)
    q = q.limit(100)
    return [_out(db, a) for a in q.all()]


@router.get("/{apartado_id}")
def detalle_apartado(apartado_id: int, db: Session = Depends(get_db)):
    apartado = db.get(Apartado, apartado_id)
    if not apartado:
        raise HTTPException(404, "Apartado no encontrado")
    return _out(db, apartado)


@router.post("", status_code=201)
def crear_apartado(
    data: ApartadoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    if not data.detalle:
        raise HTTPException(400, "El apartado requiere al menos un producto")
    total = 0.0
    for linea in data.detalle:
        if not db.get(Producto, linea.producto_id):
            raise HTTPException(404, f"Producto {linea.producto_id} no encontrado")
        total += float(linea.precio or 0) * float(linea.cantidad or 1)
    abono_inicial = min(float(data.abono_inicial or 0), total)
    pendiente = total - abono_inicial
    apartado = Apartado(
        empresa_id=usuario.empresa_id,
        sucursal_id=usuario.sucursal_id,
        cliente_id=data.cliente_id,
        usuario_id=usuario.id,
        estado="abierto",
        fecha_compromiso=data.fecha_compromiso,
        nota=data.nota,
        total=total,
        abonado=abono_inicial,
        pendiente=pendiente,
    )
    db.add(apartado)
    db.flush()
    apartado.numero = f"AP-{apartado.id:06d}"
    for linea in data.detalle:
        db.add(
            ApartadoDetalle(
                apartado_id=apartado.id,
                producto_id=linea.producto_id,
                cantidad=linea.cantidad,
                precio=linea.precio,
                descuento=0,
            )
        )
    if abono_inicial > 0:
        db.add(
            ApartadoAbono(
                apartado_id=apartado.id,
                usuario_id=usuario.id,
                monto=abono_inicial,
                medio="efectivo",
            )
        )
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="apartados",
            accion="crear",
            entidad="apartado",
            entidad_id=apartado.id,
            detalle=f"Apartado {apartado.numero} por {total:,.2f}",
        )
    )
    db.commit()
    db.refresh(apartado)
    return _out(db, apartado)


@router.post("/{apartado_id}/abonos", status_code=201)
def abonar_apartado(
    apartado_id: int,
    data: ApartadoAbonoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    apartado = db.get(Apartado, apartado_id)
    if not apartado or apartado.estado != "abierto":
        raise HTTPException(400, "Apartado no válido")
    if data.monto <= 0:
        raise HTTPException(400, "El abono debe ser mayor a cero")
    monto = min(data.monto, float(apartado.pendiente or 0))
    apartado.abonado = float(apartado.abonado or 0) + monto
    apartado.pendiente = max(0.0, float(apartado.pendiente or 0) - monto)
    db.add(
        ApartadoAbono(
            apartado_id=apartado.id,
            usuario_id=usuario.id,
            monto=monto,
            medio="efectivo",
        )
    )
    total = float(apartado.total or 0)
    if float(apartado.abonado or 0) + 1e-9 >= total:
        apartado.pendiente = 0
        apartado.estado = "pagado"
    db.commit()
    db.refresh(apartado)
    return {"apartado_id": apartado.id, "abonado": float(apartado.abonado), "pendiente": float(apartado.pendiente), "estado": apartado.estado}


@router.post("/{apartado_id}/liquidar", status_code=201)
def liquidar_apartado(
    apartado_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    apartado = db.get(Apartado, apartado_id)
    if not apartado or apartado.estado in ("liquidado", "cancelado"):
        raise HTTPException(400, "Apartado no válido")
    if float(apartado.pendiente or 0) > 0.001:
        raise HTTPException(400, "El apartado tiene saldo pendiente por abonar")
    venta = crear_venta(
        VentaCreate(
            empresa_id=usuario.empresa_id,
            sucursal_id=usuario.sucursal_id,
            cliente_id=apartado.cliente_id,
            tipo="contado",
            caja_id=None,
            vendedor_id=usuario.id,
            detalle=[
                VentaDetalleCreate(
                    producto_id=d.producto_id,
                    cantidad=d.cantidad,
                    precio=d.precio,
                    descuento=d.descuento,
                )
                for d in apartado.detalle
            ],
            pagos=[VentaPagoCreate(medio="efectivo", monto=float(apartado.total))],
            nota=f"Liquidación de apartado {apartado.numero}",
        ),
        db,
        usuario,
    )
    apartado.venta_id = venta.id
    apartado.estado = "liquidado"
    db.commit()
    return {"apartado_id": apartado.id, "estado": "liquidado", "venta_id": venta.id, "numero_venta": venta.numero}


@router.post("/{apartado_id}/cancelar")
def cancelar_apartado(
    apartado_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    apartado = db.get(Apartado, apartado_id)
    if not apartado or apartado.estado != "abierto":
        raise HTTPException(400, "Apartado no válido para cancelar")
    apartado.estado = "cancelado"
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="apartados",
            accion="cancelar",
            entidad="apartado",
            entidad_id=apartado.id,
            detalle=f"Cancelado apartado {apartado.numero}, saldo devolver {apartado.abonado:,.2f}",
        )
    )
    db.commit()
    return {"apartado_id": apartado.id, "estado": "cancelado", "a_devolver": float(apartado.abonado or 0)}


@router.get("/resumen/estado")
def resumen_apartados(db: Session = Depends(get_db)):
    abiertos = db.query(Apartado).filter(Apartado.estado == "abierto").all()
    return {
        "abiertos": len(abiertos),
        "por_liquidar": int(db.query(Apartado).filter(Apartado.estado == "pagado").count()),
        "pendiente_cobrar": float(sum(float(a.pendiente or 0) for a in abiertos)),
    }