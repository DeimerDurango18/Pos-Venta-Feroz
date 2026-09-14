from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..fidelizacion import previsualizar_cupon
from ..models import (
    AuditoriaLog,
    Bono,
    Cliente,
    Cupon,
    PuntosMovimiento,
    TarjetaRegalo,
    Usuario,
)


class CuponCreate(BaseModel):
    codigo: str
    tipo: str = "valor"  # porcentaje, valor
    valor: float = 0
    vigencia_desde: date | None = None
    vigencia_hasta: date | None = None
    cliente_id: int | None = None
    usos_max: int = 1
    descripcion: str | None = None


class BonoCreate(BaseModel):
    cliente_id: int
    codigo: str
    valor_total: float
    motivo: str | None = None
    vencimiento: date | None = None


class TarjetaCreate(BaseModel):
    cliente_id: int
    codigo: str
    saldo: float


class AjustePuntos(BaseModel):
    cliente_id: int
    delta: int
    motivo: str


router = APIRouter(prefix="/fidelizacion", tags=["fidelizacion"])


def _cliente(db, cliente_id):
    cliente = db.get(Cliente, cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    return cliente


# ---------- Puntos (168-169) ----------

@router.get("/puntos")
def lista_puntos(db: Session = Depends(get_db)):
    clientes = db.query(Cliente).filter(Cliente.puntos > 0).order_by(Cliente.puntos.desc()).limit(50).all()
    return [
        {"cliente_id": c.id, "cliente": c.nombre, "documento": c.documento, "puntos": int(c.puntos or 0)}
        for c in clientes
    ]


@router.post("/puntos/ajustar")
def ajustar_puntos(
    data: AjustePuntos,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    cliente = _cliente(db, data.cliente_id)
    anterior = int(cliente.puntos or 0)
    nuevo = max(0, anterior + data.delta)
    cliente.puntos = nuevo
    db.add(
        PuntosMovimiento(
            cliente_id=cliente.id,
            delta=data.delta,
            saldo_anterior=anterior,
            saldo_nuevo=nuevo,
            motivo=data.motivo,
            usuario_id=usuario.id,
        )
    )
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="fidelizacion",
            accion="ajustar-puntos",
            entidad="cliente",
            entidad_id=cliente.id,
            detalle=f"{data.motivo}: {data.delta:+d} puntos",
        )
    )
    db.commit()
    return {"cliente_id": cliente.id, "puntos": nuevo}


@router.get("/puntos/historial/{cliente_id}")
def historial_puntos(cliente_id: int, db: Session = Depends(get_db)):
    movs = db.query(PuntosMovimiento).filter_by(cliente_id=cliente_id).order_by(PuntosMovimiento.id.desc()).limit(50).all()
    return [
        {
            "id": m.id,
            "delta": m.delta,
            "saldo_anterior": m.saldo_anterior,
            "saldo_nuevo": m.saldo_nuevo,
            "motivo": m.motivo,
            "fecha": m.created_at.isoformat() if m.created_at else None,
        }
        for m in movs
    ]


# ---------- Cupones (165) ----------

class ValidarCuponIn(BaseModel):
    codigo: str
    subtotal: float
    cliente_id: int | None = None


@router.post("/cupones/validar")
def validar_cupon(
    data: ValidarCuponIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Valida un cupón en el checkout sin consumir usos (previsualización)."""
    res = previsualizar_cupon(db, usuario, data.codigo, data.cliente_id, data.subtotal)
    return {
        "codigo": data.codigo,
        "valido": bool(res["cupon"]),
        "descuento": res["descuento"],
        "cliente_id": res["cupon"].cliente_id if res["cupon"] else None,
    }


@router.get("/cupones")
def listar_cupones(db: Session = Depends(get_db)):
    cupones = db.query(Cupon).order_by(Cupon.id.desc()).limit(100).all()
    return [
        {
            "id": c.id,
            "codigo": c.codigo,
            "tipo": c.tipo,
            "valor": float(c.valor or 0),
            "vigencia_desde": c.vigencia_desde.isoformat() if c.vigencia_desde else None,
            "vigencia_hasta": c.vigencia_hasta.isoformat() if c.vigencia_hasta else None,
            "cliente_id": c.cliente_id,
            "usos_actuales": c.usos_actuales,
            "usos_max": c.usos_max,
            "activo": c.activo,
            "descripcion": c.descripcion,
        }
        for c in cupones
    ]


@router.post("/cupones", status_code=201)
def crear_cupon(data: CuponCreate, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    if db.query(Cupon).filter_by(codigo=data.codigo).first():
        raise HTTPException(400, f"El código {data.codigo} ya existe")
    cupon = Cupon(
        empresa_id=1,
        codigo=data.codigo.upper(),
        tipo=data.tipo,
        valor=data.valor,
        vigencia_desde=data.vigencia_desde,
        vigencia_hasta=data.vigencia_hasta,
        cliente_id=data.cliente_id,
        usos_max=data.usos_max,
        descripcion=data.descripcion,
        activo=True,
    )
    db.add(cupon)
    db.commit()
    return {"id": cupon.id, "codigo": cupon.codigo, "ok": True}


@router.post("/cupones/{cupon_id}/toggle")
def toggle_cupon(cupon_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    cupon = db.get(Cupon, cupon_id)
    if not cupon:
        raise HTTPException(404, "Cupón no encontrado")
    cupon.activo = not bool(cupon.activo)
    db.commit()
    return {"id": cupon.id, "activo": cupon.activo}


# ---------- Bonos (166) ----------

@router.get("/bonos")
def listar_bonos(db: Session = Depends(get_db)):
    bonos = db.query(Bono).order_by(Bono.id.desc()).limit(100).all()
    return [
        {
            "id": b.id,
            "cliente_id": b.cliente_id,
            "cliente": (db.get(Cliente, b.cliente_id).nombre if b.cliente_id else ""),
            "codigo": b.codigo,
            "valor_total": float(b.valor_total or 0),
            "saldo": float(b.saldo or 0),
            "motivo": b.motivo,
            "estado": b.estado,
        }
        for b in bonos
    ]


@router.post("/bonos", status_code=201)
def crear_bono(data: BonoCreate, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    _cliente(db, data.cliente_id)
    bono = Bono(
        empresa_id=1,
        cliente_id=data.cliente_id,
        codigo=data.codigo.upper(),
        valor_total=data.valor_total,
        saldo=data.valor_total,
        motivo=data.motivo,
        vencimiento=data.vencimiento,
        estado="activo",
    )
    db.add(bono)
    db.commit()
    return {"id": bono.id, "codigo": bono.codigo, "saldo": float(bono.saldo), "ok": True}


@router.post("/bonos/{bono_id}/consumir")
def consumir_bono(bono_id: int, monto: float, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    bono = db.get(Bono, bono_id)
    if not bono or bono.estado != "activo":
        raise HTTPException(400, "Bono no válido")
    if float(bono.saldo or 0) + 1e-9 < monto:
        raise HTTPException(400, "Saldo insuficiente")
    bono.saldo = float(bono.saldo or 0) - monto
    if float(bono.saldo or 0) <= 0:
        bono.saldo = 0
        bono.estado = "agotado"
    db.commit()
    return {"id": bono.id, "saldo": float(bono.saldo), "ok": True}


# ---------- Tarjetas de regalo (167) ----------

@router.get("/tarjetas-regalo")
def listar_tarjetas(db: Session = Depends(get_db)):
    tarjetas = db.query(TarjetaRegalo).order_by(TarjetaRegalo.id.desc()).limit(100).all()
    return [
        {
            "id": t.id,
            "cliente_id": t.cliente_id,
            "cliente": (db.get(Cliente, t.cliente_id).nombre if t.cliente_id else ""),
            "codigo": t.codigo,
            "saldo": float(t.saldo or 0),
            "estado": t.estado,
        }
        for t in tarjetas
    ]


@router.post("/tarjetas-regalo", status_code=201)
def crear_tarjeta(data: TarjetaCreate, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    _cliente(db, data.cliente_id)
    tarjeta = TarjetaRegalo(
        empresa_id=1,
        cliente_id=data.cliente_id,
        codigo=data.codigo.upper(),
        saldo=data.saldo,
        estado="activa",
    )
    db.add(tarjeta)
    db.commit()
    return {"id": tarjeta.id, "codigo": tarjeta.codigo, "saldo": float(tarjeta.saldo), "ok": True}


@router.post("/tarjetas-regalo/{tarjeta_id}/consumir")
def consumir_tarjeta(tarjeta_id: int, monto: float, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    tarjeta = db.get(TarjetaRegalo, tarjeta_id)
    if not tarjeta or tarjeta.estado != "activa":
        raise HTTPException(400, "Tarjeta no válida")
    if float(tarjeta.saldo or 0) + 1e-9 < monto:
        raise HTTPException(400, "Saldo insuficiente")
    tarjeta.saldo = float(tarjeta.saldo or 0) - monto
    if float(tarjeta.saldo or 0) <= 0:
        tarjeta.saldo = 0
        tarjeta.estado = "agotada"
    db.commit()
    return {"id": tarjeta.id, "saldo": float(tarjeta.saldo), "ok": True}


@router.post("/tarjetas-regalo/{tarjeta_id}/recargar")
def recargar_tarjeta(tarjeta_id: int, monto: float, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    tarjeta = db.get(TarjetaRegalo, tarjeta_id)
    if not tarjeta or tarjeta.estado == "cancelada":
        raise HTTPException(400, "Tarjeta no válida")
    tarjeta.saldo = float(tarjeta.saldo or 0) + monto
    if tarjeta.estado != "activa":
        tarjeta.estado = "activa"
    db.commit()
    return {"id": tarjeta.id, "saldo": float(tarjeta.saldo), "ok": True}


@router.get("/resumen")
def resumen(db: Session = Depends(get_db)):
    return {
        "puntos_total": int(db.query(func.coalesce(func.sum(Cliente.puntos), 0)).scalar()),
        "clientes_con_puntos": int(db.query(Cliente).filter(Cliente.puntos > 0).count()),
        "cupones_activos": int(db.query(Cupon).filter(Cupon.activo == True).count()),
        "bonos_activos": int(db.query(Bono).filter(Bono.estado == "activo").count()),
        "tarjetas_activas": int(db.query(TarjetaRegalo).filter(TarjetaRegalo.estado == "activa").count()),
        "saldo_tarjetas": float(db.query(func.coalesce(func.sum(TarjetaRegalo.saldo), 0)).scalar()),
    }