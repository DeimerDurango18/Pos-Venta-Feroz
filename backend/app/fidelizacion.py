from datetime import date

from fastapi import HTTPException

from .models import (
    Bono,
    Cliente,
    Configuracion,
    Cupon,
    PuntosMovimiento,
    TarjetaRegalo,
)


def _parametro_int(db, clave, default):
    cfg = (
        db.query(Configuracion)
        .filter(Configuracion.clave == clave)
        .first()
    )
    try:
        return int(float(cfg.valor)) if cfg and cfg.valor else default
    except ValueError:
        return default


def aplicar_cupon(db, usuario, codigo, cliente_id, subtotal):
    """Aplica un cupón y devuelve el descuento en pesos (0 si no aplica)."""
    return _calcular_descuento_cupon(db, usuario, codigo, cliente_id, subtotal, consumir=True)["descuento"]


def previsualizar_cupon(db, usuario, codigo, cliente_id, subtotal):
    """Valida un cupón sin consumir usos y devuelve el descuento proyectado."""
    return _calcular_descuento_cupon(db, usuario, codigo, cliente_id, subtotal, consumir=False)


def _calcular_descuento_cupon(db, usuario, codigo, cliente_id, subtotal, consumir):
    if not codigo:
        return {"cupon": None, "descuento": 0.0}
    cupon = (
        db.query(Cupon)
        .filter(Cupon.codigo == codigo, Cupon.empresa_id == usuario.empresa_id)
        .first()
    )
    if not cupon or not cupon.activo:
        raise HTTPException(400, f"Cupón '{codigo}' no existe o está inactivo")
    hoy = date.today()
    if cupon.vigencia_desde and cupon.vigencia_desde > hoy:
        raise HTTPException(400, "El cupón aún no está vigente")
    if cupon.vigencia_hasta and cupon.vigencia_hasta < hoy:
        raise HTTPException(400, "El cupón está vencido")
    if cupon.cliente_id and cupon.cliente_id != cliente_id:
        raise HTTPException(400, "El cupón no aplica para este cliente")
    if cupon.usos_actuales >= cupon.usos_max:
        raise HTTPException(400, "El cupón ya agotó sus usos")
    descuento = float(cupon.valor or 0) if cupon.tipo == "valor" else subtotal * float(cupon.valor or 0) / 100
    if consumir:
        cupon.usos_actuales += 1
        db.commit()
    return {"cupon": cupon, "descuento": min(descuento, subtotal)}


def consumir_pago_fidelidad(db, cliente_id, medio, referencia, monto):
    """Valida y consume un pago con tarjeta de regalo o bono."""
    if medio not in ("tarjeta_regalo", "bono"):
        return
    if not cliente_id:
        raise HTTPException(400, f"El pago con {medio} requiere cliente")
    if medio == "tarjeta_regalo":
        tarjeta = db.query(TarjetaRegalo).filter(TarjetaRegalo.codigo == referencia, TarjetaRegalo.cliente_id == cliente_id).first()
        if not tarjeta or tarjeta.estado != "activa":
            raise HTTPException(400, "Tarjeta de regalo no válida")
        if float(tarjeta.saldo or 0) + 1e-9 < monto:
            raise HTTPException(400, "Saldo insuficiente en la tarjeta de regalo")
        tarjeta.saldo = float(tarjeta.saldo or 0) - monto
        if float(tarjeta.saldo or 0) <= 0:
            tarjeta.saldo = 0
            tarjeta.estado = "agotada"
    else:
        bono = db.query(Bono).filter(Bono.id == referencia, Bono.cliente_id == cliente_id, Bono.estado == "activo").first()
        if not bono:
            raise HTTPException(400, "Bono no válido")
        if float(bono.saldo or 0) + 1e-9 < monto:
            raise HTTPException(400, "Saldo insuficiente en el bono")
        bono.saldo = float(bono.saldo or 0) - monto
        if float(bono.saldo or 0) <= 0:
            bono.saldo = 0
            bono.estado = "agotado"
    db.commit()


def acumular_puntos(db, cliente_id, total, usuario_id=None, motivo="Venta"):
    """Suma puntos de fidelización al cliente según configuración."""
    if not cliente_id:
        return
    puntos_por_monto = _parametro_int(db, "puntos_por_monto", 1000)
    ganados = int(float(total or 0) // puntos_por_monto)
    if ganados <= 0:
        return
    cliente = db.get(Cliente, cliente_id)
    if not cliente:
        return
    anterior = int(cliente.puntos or 0)
    cliente.puntos = anterior + ganados
    db.add(
        PuntosMovimiento(
            cliente_id=cliente_id,
            delta=ganados,
            saldo_anterior=anterior,
            saldo_nuevo=anterior + ganados,
            motivo=motivo,
            usuario_id=usuario_id,
        )
    )
    db.commit()