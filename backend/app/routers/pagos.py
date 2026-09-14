from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import TarjetaTransaccion, Usuario
from ..schemas.pagos import TarjetaAutorizar, TarjetaTransaccionOut

router = APIRouter(prefix="/pagos", tags=["pagos con tarjeta"])

LIMITE_MAXIMO = 50_000_000


@router.post("/tarjeta/autorizar", response_model=TarjetaTransaccionOut)
def autorizar_tarjeta(
    data: TarjetaAutorizar,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    """Simula la autorización en una pasarela: aprueba salvo montos inválidos o excesivos."""
    if data.monto <= 0 or data.monto > LIMITE_MAXIMO:
        return _guardar(db, data, estado="rechazada", codigo="REJ000000")
    tx = _guardar(db, data, estado="aprobada")
    tx.codigo_autorizacion = f"APR{tx.id:06d}"
    tx.referencia = f"PYSL-{tx.id:06d}"
    if data.ultimos4:
        tx.ultimos4 = data.ultimos4.zfill(4)
    db.commit()
    db.refresh(tx)
    return tx


@router.get("/tarjeta", response_model=list[TarjetaTransaccionOut])
def listar_transacciones(
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    return (
        db.query(TarjetaTransaccion)
        .order_by(TarjetaTransaccion.id.desc())
        .limit(100)
        .all()
    )


@router.post("/tarjeta/{tx_id}/confirmar", response_model=TarjetaTransaccionOut)
def confirmar(tx_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_user)):
    tx = db.get(TarjetaTransaccion, tx_id)
    if not tx:
        raise HTTPException(404, "Transacción no encontrada")
    if tx.estado != "aprobada":
        raise HTTPException(400, f"No se puede confirmar una transacción en estado '{tx.estado}'")
    tx.estado = "confirmada"
    db.commit()
    db.refresh(tx)
    return tx


@router.post("/tarjeta/{tx_id}/reversar", response_model=TarjetaTransaccionOut)
def reversar(tx_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_user)):
    tx = db.get(TarjetaTransaccion, tx_id)
    if not tx:
        raise HTTPException(404, "Transacción no encontrada")
    if tx.estado not in ("aprobada", "confirmada"):
        raise HTTPException(400, f"No se puede reversar una transacción en estado '{tx.estado}'")
    tx.estado = "reversada"
    db.commit()
    db.refresh(tx)
    return tx


def _guardar(db: Session, data: TarjetaAutorizar, estado: str, codigo: str = "") -> TarjetaTransaccion:
    tx = TarjetaTransaccion(
        monto=data.monto,
        marca=data.marca or "Visa",
        ultimos4=data.ultimos4,
        estado=estado,
        codigo_autorizacion=codigo,
        referencia=codigo,
        created_at=datetime.now(),
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx