from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import AcuerdoPago, AuditoriaLog, Cliente, CuotaAcuerdo, Usuario

router = APIRouter(prefix="/acuerdos-pago", tags=["acuerdos de pago"])

_PERIODOS = {"semanal": 7, "quincenal": 15, "mensual": 30}


class AcuerdoPagoCreate(BaseModel):
    empresa_id: int = 1
    sucursal_id: int = 1
    cliente_id: int
    monto_total: float
    numero_cuotas: int = 1
    periodicidad: str = "mensual"
    fecha_inicio: date | None = None
    notas: str | None = None


def _out(db, ac): 
    cliente = db.get(Cliente, ac.cliente_id)
    nombre = cliente.nombre if cliente else "?"
    cuotas = []
    for c in sorted(ac.cuotas, key=lambda x: x.numero):
        cuotas.append(
            {
                "id": c.id,
                "numero": c.numero,
                "monto": float(c.monto or 0),
                "estado": c.estado,
                "fecha_programada": c.fecha_programada.isoformat() if c.fecha_programada else None,
                "fecha_pago": c.fecha_pago.isoformat() if c.fecha_pago else None,
            }
        )
    return {
        "id": ac.id,
        "numero": ac.numero,
        "cliente_id": ac.cliente_id,
        "cliente": nombre,
        "monto_total": float(ac.monto_total or 0),
        "abonado": float(ac.abonado or 0),
        "saldo": float(ac.saldo or 0),
        "estado": ac.estado,
        "periodicidad": ac.periodicidad,
        "fecha_inicio": ac.fecha_inicio.isoformat() if ac.fecha_inicio else None,
        "notas": ac.notas,
        "cuotas": cuotas,
    }


@router.post("", status_code=201)
def crear_acuerdo(
    data: AcuerdoPagoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    if data.monto_total <= 0:
        raise HTTPException(400, "El monto total debe ser mayor que 0")
    if data.numero_cuotas < 1:
        raise HTTPException(400, "Debe haber al menos una cuota")
    cliente = db.get(Cliente, data.cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    inicio = data.fecha_inicio or date.today()
    paso = _PERIODOS.get(data.periodicidad, 30)
    base = round(data.monto_total / data.numero_cuotas, 2)
    cuota_base = base
    ac = AcuerdoPago(
        empresa_id=data.empresa_id,
        sucursal_id=data.sucursal_id,
        cliente_id=data.cliente_id,
        usuario_id=usuario.id,
        monto_total=data.monto_total,
        abonado=0,
        saldo=data.monto_total,
        periodicidad=data.periodicidad,
        fecha_inicio=inicio,
        notas=data.notas,
    )
    db.add(ac)
    db.flush()
    ac.numero = f"AP-{ac.id:06d}"
    for i in range(1, data.numero_cuotas + 1):
        es_ultima = i == data.numero_cuotas
        monto = round(data.monto_total - cuota_base * (data.numero_cuotas - 1), 2) if es_ultima else cuota_base
        db.add(
            CuotaAcuerdo(
                acuerdo_id=ac.id,
                numero=i,
                monto=monto,
                estado="pendiente",
                fecha_programada=inicio + timedelta(days=paso * (i - 1)),
            )
        )
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="cartera",
            accion="crear_acuerdo",
            entidad="acuerdo_pago",
            entidad_id=ac.id,
            detalle=f"Acuerdo {ac.numero} por {data.monto_total}",
        )
    )
    db.commit()
    db.refresh(ac)
    return _out(db, ac)


@router.get("")
def listar_acuerdos(
    estado: str | None = None,
    cliente_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(AcuerdoPago)
    if estado:
        q = q.filter(AcuerdoPago.estado == estado)
    if cliente_id:
        q = q.filter(AcuerdoPago.cliente_id == cliente_id)
    acuerdos = q.order_by(AcuerdoPago.id.desc()).limit(100).all()
    return [_out(db, a) for a in acuerdos]


@router.get("/{acuerdo_id}")
def obtener_acuerdo(acuerdo_id: int, db: Session = Depends(get_db)):
    ac = db.get(AcuerdoPago, acuerdo_id)
    if not ac:
        raise HTTPException(404, "Acuerdo no encontrado")
    return _out(db, ac)


@router.post("/{acuerdo_id}/pagar-cuota")
def pagar_cuota(
    acuerdo_id: int,
    cuota_id: int | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    ac = db.get(AcuerdoPago, acuerdo_id)
    if not ac:
        raise HTTPException(404, "Acuerdo no encontrado")
    if ac.estado == "pagado":
        raise HTTPException(400, "El acuerdo ya está pagado")
    if cuota_id:
        cuota = db.get(CuotaAcuerdo, cuota_id)
    else:
        cuota = (
            db.query(CuotaAcuerdo)
            .filter(CuotaAcuerdo.acuerdo_id == acuerdo_id, CuotaAcuerdo.estado == "pendiente")
            .order_by(CuotaAcuerdo.numero.asc())
            .first()
        )
    if not cuota:
        raise HTTPException(404, "Cuota pendiente no encontrada")

    cuota.estado = "pagada"
    cuota.fecha_pago = date.today()
    ac.abonado = float(ac.abonado or 0) + float(cuota.monto or 0)
    ac.saldo = round(float(ac.saldo or 0) - float(cuota.monto or 0), 2)
    if ac.saldo <= 0:
        ac.saldo = 0
        ac.estado = "pagado"

    cliente = db.get(Cliente, ac.cliente_id)
    if cliente:
        cliente.creditos = max(0.0, float(cliente.creditos or 0) - float(cuota.monto or 0))

    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="cartera",
            accion="pagar_cuota",
            entidad="acuerdo_pago",
            entidad_id=ac.id,
            detalle=f"Cuota {cuota.numero} de {ac.numero}",
        )
    )
    db.commit()
    db.refresh(ac)
    return _out(db, ac)