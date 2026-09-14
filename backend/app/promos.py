from datetime import datetime

from sqlalchemy.orm import Session

from .models import Promocion, Producto


def _en_vigencia(prom, ahora=None):
    """Verifica vigencia por fechas y horario."""
    hoy = ahora.date() if ahora else datetime.now().date()
    if prom.desde and prom.desde > hoy:
        return False
    if prom.hasta and prom.hasta < hoy:
        return False
    if prom.hora_desde or prom.hora_hasta:
        hora_actual = (ahora or datetime.now()).strftime("%H:%M")
        if prom.hora_desde and hora_actual < prom.hora_desde:
            return False
        if prom.hora_hasta and hora_actual > prom.hora_hasta:
            return False
    return True


def _cubre(prom, producto_id, categoria_id):
    if prom.aplica_a == "general":
        return True
    if prom.aplica_a == "categoria":
        return categoria_id is not None and categoria_id == prom.categoria_id
    if prom.aplica_a == "producto":
        return any(p.producto_id == producto_id for p in prom.productos)
    return False


def calcular_promociones(db: Session, lineas, cliente_id: int | None = None) -> float:
    """Devuelve el descuento total por promociones vigentes.

    lineas: iterable de dicts con producto_id, cantidad, precio.
    cliente_id: si se pasa, solo aplican promociones sin cliente o del cliente indicado.
    """
    ahora = datetime.now()
    promos = (
        db.query(Promocion)
        .filter(Promocion.activa == True)
        .all()
    )
    total_descuento = 0.0
    for prom in promos:
        if not _en_vigencia(prom, ahora):
            continue
        if prom.cliente_id and prom.cliente_id != cliente_id:
            continue
        for linea in lineas:
            producto = db.get(Producto, linea["producto_id"])
            if not producto or not _cubre(prom, linea["producto_id"], producto.categoria_id):
                continue
            cantidad = float(linea["cantidad"] or 0)
            precio = float(linea["precio"] or 0)
            if float(prom.cantidad_minima or 0) > 0 and cantidad < float(prom.cantidad_minima):
                continue
            base = precio * cantidad
            if base <= 0:
                continue
            if prom.tipo == "porcentaje":
                desc = base * float(prom.valor or 0) / 100
            elif prom.tipo == "valor":
                desc = float(prom.valor or 0) * cantidad
            elif prom.tipo == "2x1":
                desc = int(cantidad // 2) * precio
            elif prom.tipo == "3x2":
                desc = int(cantidad // 3) * precio
            else:
                continue
            total_descuento += min(desc, base)
    return round(total_descuento, 2)