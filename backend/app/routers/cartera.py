from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    AbonoCliente,
    AbonoProveedor,
    Cliente,
    Proveedor,
    Usuario,
    Venta,
)
from ..schemas.cartera import AbonoClienteCreate, AbonoClienteOut

router = APIRouter(prefix="/cartera", tags=["cartera"])


@router.post("/abonos/clientes", response_model=AbonoClienteOut, status_code=201)
def abonar_cliente(
    data: AbonoClienteCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    cliente = db.get(Cliente, data.cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    if data.monto <= 0:
        raise HTTPException(400, "Monto inválido")

    abono = AbonoCliente(
        empresa_id=data.empresa_id,
        cliente_id=data.cliente_id,
        venta_id=data.venta_id,
        usuario_id=usuario.id,
        monto=data.monto,
        medio=data.medio,
        referencia=data.referencia,
        observacion=data.observacion,
    )
    db.add(abono)

    if data.venta_id:
        venta = db.get(Venta, data.venta_id)
        if venta and venta.tipo == "credito":
            venta.saldo = max(0.0, float(venta.saldo or 0) - data.monto)

    cliente.creditos = max(0.0, float(cliente.creditos or 0) - data.monto)
    db.commit()
    db.refresh(abono)
    return abono


@router.get("/cuentas-cobrar")
def cuentas_cobrar(db: Session = Depends(get_db)):
    """Resumen de cartera por cliente (ventas a crédito no saldadas)."""
    filas = (
        db.query(Cliente, Venta)
        .join(Venta, Venta.cliente_id == Cliente.id)
        .filter(Venta.tipo == "credito", Venta.estado == "completada", Venta.saldo > 0)
        .all()
    )
    resumen = {}
    total = 0.0
    for cliente, venta in filas:
        saldo = float(venta.saldo or 0)
        total += saldo
        if cliente.id not in resumen:
            resumen[cliente.id] = {
                "cliente_id": cliente.id,
                "cliente": cliente.nombre,
                "saldo": 0.0,
                "ventas": [],
            }
        resumen[cliente.id]["saldo"] += saldo
        resumen[cliente.id]["ventas"].append(
            {"venta_id": venta.id, "numero": venta.numero, "total": float(venta.total or 0), "saldo": saldo}
        )
    return {"total_cartera": total, "clientes": list(resumen.values())}


@router.get("/estado-cuenta/{cliente_id}")
def estado_cuenta(cliente_id: int, db: Session = Depends(get_db)):
    cliente = db.get(Cliente, cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    ventas = (
        db.query(Venta)
        .filter(Venta.cliente_id == cliente_id, Venta.tipo == "credito", Venta.estado == "completada")
        .order_by(Venta.id.desc())
        .all()
    )
    abonos = (
        db.query(AbonoCliente).filter(AbonoCliente.cliente_id == cliente_id).order_by(AbonoCliente.id.desc()).all()
    )
    return {
        "cliente_id": cliente.id,
        "cliente": cliente.nombre,
        "saldo_total": sum(float(v.saldo or 0) for v in ventas),
        "ventas": [
            {"id": v.id, "numero": v.numero, "total": float(v.total or 0), "saldo": float(v.saldo or 0), "fecha": str(v.created_at)}
            for v in ventas
        ],
        "abonos": [
            {"id": a.id, "monto": float(a.monto or 0), "medio": a.medio, "fecha": str(a.created_at)}
            for a in abonos
        ],
    }


@router.get("/cobranza")
def cobranza(db: Session = Depends(get_db)):
    """Gestión de cobranza: cartera en mora con antigüedad de deuda."""
    from datetime import datetime, timezone

    ventas = (
        db.query(Venta)
        .filter(Venta.tipo == "credito", Venta.estado == "completada", Venta.saldo > 0)
        .all()
    )
    agrupado = {}
    total = 0.0
    ahora = datetime.now(timezone.utc)
    for v in ventas:
        cliente = db.get(Cliente, v.cliente_id)
        saldo = float(v.saldo or 0)
        total += saldo
        dias = max(0, (ahora - (v.created_at or ahora)).days)
        if dias <= 30:
            tramo = "corriente"
        elif dias <= 60:
            tramo = "mora 31-60"
        elif dias <= 90:
            tramo = "mora 61-90"
        else:
            tramo = "mora >90"
        d = agrupado.setdefault(tramo, {"tramo": tramo, "saldo": 0.0, "clientes": {}})
        d["saldo"] += saldo
        cid = v.cliente_id
        if cid not in d["clientes"]:
            d["clientes"][cid] = {"cliente_id": cid, "cliente": cliente.nombre if cliente else f"cliente_{cid}", "saldo": 0.0}
        d["clientes"][cid]["saldo"] += saldo
    orden = ["corriente", "mora 31-60", "mora 61-90", "mora >90"]
    resultado = []
    for tramo in orden:
        if tramo in agrupado:
            resultado.append(agrupado[tramo])
    return {"total_cartera": round(total, 2), "tramos": resultado}


@router.get("/cuentas-pagar")
def cuentas_pagar(db: Session = Depends(get_db)):
    """Resumen de deudas con proveedores."""
    filas = (
        db.query(Proveedor)
        .filter(Proveedor.activo == True)
        .all()
    )
    from ..models import CuentaPagar
    resultado = []
    total = 0.0
    for prov in filas:
        cuentas = (
            db.query(CuentaPagar)
            .filter(CuentaPagar.proveedor_id == prov.id, CuentaPagar.saldo > 0)
            .all()
        )
        saldo = sum(float(c.saldo or 0) for c in cuentas)
        if saldo > 0:
            total += saldo
            resultado.append(
                {
                    "proveedor_id": prov.id,
                    "proveedor": prov.nombre,
                    "saldo": saldo,
                    "cuentas": [
                        {"id": c.id, "monto_total": float(c.monto_total or 0), "saldo": float(c.saldo or 0)}
                        for c in cuentas
                    ],
                }
            )
    return {"total_deuda": total, "proveedores": resultado}