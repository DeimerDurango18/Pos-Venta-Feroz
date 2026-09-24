from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import Date, and_, case, cast, func, or_, extract
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    AbonoProveedor,
    AperturaCaja,
    ArqueoCaja,
    Caja,
    Categoria,
    Cliente,
    Compra,
    CuentaPagar,
    Gasto,
    Marca,
    MovimientoCaja,
    Producto,
    Proveedor,
    Stock,
    Sucursal,
    Usuario,
    Venta,
    VentaDetalle,
    VentaPago,
)

router = APIRouter(prefix="/reportes", tags=["reportes"])


def _parse_fecha(valor, fin_de_dia=False):
    """Acepta YYYY-MM-DD o ISO; 'fin_de_dia' devuelve el inicio del día siguiente (hasta exclusivo)."""
    if not valor:
        return None
    try:
        dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = datetime.strptime(str(valor), "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "Formato de fecha inválido (use YYYY-MM-DD)")
    if fin_de_dia:
        dt = dt + timedelta(days=1)
    return dt


@router.get("/ventas")
def reporte_ventas(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    sucursal_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Venta).filter(Venta.estado == "completada")
    if sucursal_id:
        query = query.filter(Venta.sucursal_id == sucursal_id)
    fdesde = _parse_fecha(desde)
    fhasta = _parse_fecha(hasta, fin_de_dia=True)
    if fdesde:
        query = query.filter(Venta.created_at >= fdesde)
    if fhasta:
        query = query.filter(Venta.created_at < fhasta)

    ventas = query.all()
    total = sum(float(v.total) for v in ventas)
    costo = sum(float(v.costo_total or 0) for v in ventas)
    utilidad = total - costo
    numero = len(ventas)
    ticket_promedio = total / numero if numero else 0

    por_medio = {}
    por_cajero = {}
    nombres_usr = {u.id: u.nombre for u in db.query(Usuario).all()}
    for v in ventas:
        for p in v.pagos:
            por_medio[p.medio] = por_medio.get(p.medio, 0) + float(p.monto)
        usr_key = nombres_usr.get(v.usuario_id) or f"usuario_{v.usuario_id}"
        por_cajero[usr_key] = por_cajero.get(usr_key, 0) + float(v.total)

    return {
        "total_ventas": total,
        "costo_total": costo,
        "utilidad_bruta": utilidad,
        "numero_transacciones": numero,
        "ticket_promedio": ticket_promedio,
        "por_medio_pago": por_medio,
        "por_cajero": por_cajero,
    }


@router.get("/ventas-dia")
def ventas_ultimos_dias(dias: int = 7, db: Session = Depends(get_db)):
    inicio = datetime.now() - timedelta(days=dias)
    filas = (
        db.query(cast(Venta.created_at, Date).label("dia"), func.sum(Venta.total).label("total"))
        .filter(Venta.estado == "completada", Venta.created_at >= inicio)
        .group_by(cast(Venta.created_at, Date))
        .order_by(cast(Venta.created_at, Date))
        .all()
    )
    return [{"dia": str(dia), "total": float(total or 0)} for dia, total in filas]


@router.get("/ventas-por-producto")
def ventas_por_producto(db: Session = Depends(get_db)):
    filas = (
        db.query(
            Producto.nombre,
            func.sum(VentaDetalle.cantidad).label("cantidad"),
            func.sum(VentaDetalle.subtotal).label("total"),
        )
        .join(VentaDetalle, VentaDetalle.producto_id == Producto.id)
        .group_by(Producto.nombre)
        .order_by(func.sum(VentaDetalle.cantidad).desc())
        .limit(20)
        .all()
    )
    return [
        {"producto": nombre, "cantidad": float(cantidad or 0), "total": float(total or 0)}
        for nombre, cantidad, total in filas
    ]


@router.get("/productos-menos-vendidos")
def productos_menos_vendidos(db: Session = Depends(get_db)):
    filas = (
        db.query(
            Producto.nombre,
            func.sum(VentaDetalle.cantidad).label("cantidad"),
            func.sum(VentaDetalle.subtotal).label("total"),
        )
        .join(VentaDetalle, VentaDetalle.producto_id == Producto.id)
        .group_by(Producto.nombre)
        .order_by(func.sum(VentaDetalle.cantidad).asc())
        .limit(20)
        .all()
    )
    return [
        {"producto": nombre, "cantidad": float(cantidad or 0), "total": float(total or 0)}
        for nombre, cantidad, total in filas
    ]


@router.get("/productos-sin-movimiento")
def productos_sin_movimiento(db: Session = Depends(get_db)):
    """Productos activos sin ventas registradas en los últimos 30 días y con existencias."""
    desde = datetime.now() - timedelta(days=30)
    vendidos = (
        db.query(VentaDetalle.producto_id)
        .join(Venta, Venta.id == VentaDetalle.venta_id)
        .filter(Venta.estado == "completada", Venta.created_at >= desde)
        .distinct()
        .subquery()
    )
    filas = (
        db.query(
            Producto.nombre,
            func.coalesce(func.sum(Stock.existencias), 0).label("existencias"),
        )
        .outerjoin(Stock, Stock.producto_id == Producto.id)
        .filter(Producto.activo == True, ~Producto.id.in_(db.query(vendidos.c.producto_id)))
        .group_by(Producto.nombre)
        .having(func.coalesce(func.sum(Stock.existencias), 0) > 0)
        .order_by(Producto.nombre.asc())
        .all()
    )
    return [
        {"producto": nombre, "existencias": float(exist or 0)}
        for nombre, exist in filas
    ]


@router.get("/productos-mas-rentables")
def productos_mas_rentables(db: Session = Depends(get_db)):
    filas = (
        db.query(
            Producto.id,
            Producto.nombre,
            Producto.costo,
            func.sum(VentaDetalle.cantidad).label("cantidad"),
            func.sum(VentaDetalle.subtotal).label("total"),
        )
        .join(VentaDetalle, VentaDetalle.producto_id == Producto.id)
        .group_by(Producto.id, Producto.nombre, Producto.costo)
        .order_by(func.sum(VentaDetalle.subtotal).desc())
        .limit(20)
        .all()
    )
    out = []
    for pid, nombre, costo, cantidad, total in filas:
        utilidad = (total or 0) - (cantidad or 0) * (costo or 0)
        out.append(
            {
                "producto": nombre,
                "cantidad": float(cantidad or 0),
                "total": float(total or 0),
                "utilidad": float(utilidad),
                "margen": round((utilidad / total) * 100, 1) if total else 0,
            }
        )
    out.sort(key=lambda r: r["utilidad"], reverse=True)
    return out


def _filtro_ventas_fecha(modelo, q, desde, hasta):
    fdesde = _parse_fecha(desde)
    fhasta = _parse_fecha(hasta, fin_de_dia=True)
    if fdesde:
        q = q.filter(modelo.created_at >= fdesde)
    if fhasta:
        q = q.filter(modelo.created_at < fhasta)
    return q


@router.get("/ventas-por-sucursal")
def ventas_por_sucursal(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = _filtro_ventas_fecha(
        Venta,
        db.query(Venta).filter(Venta.estado == "completada"),
        desde,
        hasta,
    )
    nombres = {s.id: s.nombre for s in db.query(Sucursal).all()}
    agg = {}
    for v in q.all():
        clave = nombres.get(v.sucursal_id) or f"sucursal_{v.sucursal_id}"
        fila = agg.setdefault(clave, {"ventas": 0.0, "transacciones": 0})
        fila["ventas"] += float(v.total or 0)
        fila["transacciones"] += 1
    out = [{"sucursal": c, **d} for c, d in agg.items()]
    out.sort(key=lambda r: r["ventas"], reverse=True)
    return out


@router.get("/ventas-por-caja")
def ventas_por_caja(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = _filtro_ventas_fecha(
        Venta,
        db.query(Venta).filter(Venta.estado == "completada"),
        desde,
        hasta,
    )
    nombres = {c.id: c.nombre for c in db.query(Caja).all()}
    agg = {}
    for v in q.all():
        clave = nombres.get(v.caja_id) if v.caja_id else "Sin caja"
        fila = agg.setdefault(clave, {"ventas": 0.0, "transacciones": 0})
        fila["ventas"] += float(v.total or 0)
        fila["transacciones"] += 1
    out = [{"caja": c, **d} for c, d in agg.items()]
    out.sort(key=lambda r: r["ventas"], reverse=True)
    return out


@router.get("/ventas-por-cliente")
def ventas_por_cliente(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = _filtro_ventas_fecha(
        Venta,
        db.query(Venta).filter(Venta.estado == "completada"),
        desde,
        hasta,
    )
    nombres = {c.id: c.nombre for c in db.query(Cliente).all()}
    agg = {}
    for v in q.all():
        clave = nombres.get(v.cliente_id) if v.cliente_id else "Consumidor final"
        fila = agg.setdefault(clave, {"ventas": 0.0, "transacciones": 0})
        fila["ventas"] += float(v.total or 0)
        fila["transacciones"] += 1
    out = [{"cliente": c, **d} for c, d in agg.items()]
    out.sort(key=lambda r: r["ventas"], reverse=True)
    return out


@router.get("/ventas-por-categoria")
def ventas_por_categoria(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
):
    nombres = {c.id: c.nombre for c in db.query(Categoria).all()}
    q = _filtro_ventas_fecha(
        Venta,
        db.query(Venta).filter(Venta.estado == "completada"),
        desde,
        hasta,
    )
    ids = [v.id for v in q.all()]
    if not ids:
        return []
    filas = (
        db.query(Producto.categoria_id, func.sum(VentaDetalle.cantidad), func.sum(VentaDetalle.subtotal))
        .join(VentaDetalle, VentaDetalle.producto_id == Producto.id)
        .filter(VentaDetalle.venta_id.in_(ids))
        .group_by(Producto.categoria_id)
        .all()
    )
    out = [
        {
            "categoria": nombres.get(cid) or "Sin categoría",
            "cantidad": float(cant or 0),
            "total": float(total or 0),
        }
        for cid, cant, total in filas
    ]
    out.sort(key=lambda r: r["total"], reverse=True)
    return out


@router.get("/ventas-por-marca")
def ventas_por_marca(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
):
    nombres = {m.id: m.nombre for m in db.query(Marca).all()}
    q = _filtro_ventas_fecha(
        Venta,
        db.query(Venta).filter(Venta.estado == "completada"),
        desde,
        hasta,
    )
    ids = [v.id for v in q.all()]
    if not ids:
        return []
    filas = (
        db.query(Producto.marca_id, func.sum(VentaDetalle.cantidad), func.sum(VentaDetalle.subtotal))
        .join(VentaDetalle, VentaDetalle.producto_id == Producto.id)
        .filter(VentaDetalle.venta_id.in_(ids))
        .group_by(Producto.marca_id)
        .all()
    )
    out = [
        {
            "marca": nombres.get(mid) if mid else "Sin marca",
            "cantidad": float(cant or 0),
            "total": float(total or 0),
        }
        for mid, cant, total in filas
    ]
    out.sort(key=lambda r: r["total"], reverse=True)
    return out


@router.get("/ventas-por-hora")
def ventas_por_hora(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
):
    hora = func.extract("hour", Venta.created_at).label("hora")
    q = db.query(hora, func.sum(Venta.total).label("total"), func.count(Venta.id).label("n"))
    q = q.filter(Venta.estado == "completada")
    q = _filtro_ventas_fecha(Venta, q, desde, hasta)
    filas = q.group_by(hora).order_by(hora).all()
    return [
        {"hora": h, "total": float(t or 0), "transacciones": int(n or 0)}
        for h, t, n in filas
    ]


@router.get("/ventas-por-mes")
def ventas_por_mes(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
):
    _y = extract("year", Venta.created_at)
    _m = extract("month", Venta.created_at)
    q = db.query(_y.label("y"), _m.label("m"), func.sum(Venta.total).label("total"), func.count(Venta.id).label("n")).filter(Venta.estado == "completada")
    q = _filtro_ventas_fecha(Venta, q, desde, hasta)
    filas = q.group_by(_y, _m).order_by(_y, _m).all()
    return [
        {"mes": f"{int(y or 0):04d}-{int(m or 0):02d}", "total": float(t or 0), "transacciones": int(n or 0)}
        for y, m, t, n in filas
    ]


@router.get("/ventas-por-ano")
def ventas_por_ano(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
):
    anio = func.extract("year", Venta.created_at).label("anio")
    q = db.query(anio, func.sum(Venta.total).label("total"), func.count(Venta.id).label("n"))
    q = q.filter(Venta.estado == "completada")
    q = _filtro_ventas_fecha(Venta, q, desde, hasta)
    filas = q.group_by(anio).order_by(anio).all()
    return [
        {"anio": int(a), "total": float(t or 0), "transacciones": int(n or 0)}
        for a, t, n in filas
    ]


@router.get("/productos-agotados")
def productos_agotados(db: Session = Depends(get_db)):
    filas = (
        db.query(Producto.nombre, Stock.sucursal_id, Stock.existencias)
        .join(Stock, Stock.producto_id == Producto.id)
        .filter(Stock.existencias <= 0)
        .all()
    )
    return [
        {"producto": nombre, "sucursal_id": sucursal, "existencias": float(exist or 0)}
        for nombre, sucursal, exist in filas
    ]


@router.get("/dashboard")
def dashboard(
    sucursal_id: int | None = None,
    db: Session = Depends(get_db),
):
    hoy = datetime.now().date()

    ventas = db.query(Venta).filter(Venta.estado == "completada")
    ventas_hoy = ventas.filter(cast(Venta.created_at, Date) == hoy)
    total_hoy = sum(float(v.total) for v in ventas_hoy.all())
    utilidad_hoy = sum(
        float(v.total) - float(v.costo_total or 0) for v in ventas_hoy.all()
    )

    ventas_mes = ventas.filter(Venta.created_at >= hoy.replace(day=1))
    total_mes = sum(float(v.total) for v in ventas_mes.all())

    productos_vendidos = (
        db.query(func.sum(VentaDetalle.cantidad))
        .join(Venta, Venta.id == VentaDetalle.venta_id)
        .filter(Venta.estado == "completada", cast(Venta.created_at, Date) == hoy)
        .scalar()
        or 0
    )

    agotados = (
        db.query(Stock).filter(Stock.existencias <= 0).count()
    )
    inventario_valorizado = (
        db.query(func.sum(Stock.existencias * Producto.costo))
        .join(Producto, Producto.id == Stock.producto_id)
        .scalar()
        or 0
    )

    gastos_mes = (
        db.query(func.sum(Gasto.monto))
        .filter(Gasto.created_at >= hoy.replace(day=1))
        .scalar()
        or 0
    )

    clientes = db.query(Cliente).count()
    cuentas_cobrar = (
        db.query(func.sum(Cliente.creditos)).scalar() or 0
    )

    from datetime import timedelta
    from ..models import Lote

    bajo_inventario = (
        db.query(func.count())
        .select_from(Stock)
        .join(Producto, Stock.producto_id == Producto.id)
        .filter(Stock.existencias <= Producto.punto_reorden)
        .scalar()
        or 0
    )
    proximos_vencer = (
        db.query(func.count())
        .select_from(Stock)
        .join(Lote, Lote.producto_id == Stock.producto_id, isouter=True)
        .filter(Lote.vencimiento.isnot(None), Lote.vencimiento <= hoy + timedelta(days=30), Lote.vencimiento >= hoy, Lote.cantidad > 0)
        .scalar()
        or 0
    )
    productos_vencidos = (
        db.query(func.count())
        .select_from(Stock)
        .join(Lote, Lote.producto_id == Stock.producto_id, isouter=True)
        .filter(Lote.vencimiento.isnot(None), Lote.vencimiento < hoy, Lote.cantidad > 0)
        .scalar()
        or 0
    )

    return {
        "ventas_hoy": total_hoy,
        "utilidad_hoy": utilidad_hoy,
        "ventas_mes": total_mes,
        "productos_vendidos_hoy": float(productos_vendidos),
        "productos_agotados": agotados,
        "inventario_valorizado": float(inventario_valorizado),
        "gastos_mes": float(gastos_mes),
        "clientes": clientes,
        "cuentas_por_cobrar": float(cuentas_cobrar),
        "bajo_inventario": int(bajo_inventario),
        "productos_proximos_a_vencer": int(proximos_vencer),
        "productos_vencidos": int(productos_vencidos),
    }


@router.get("/compras")
def reporte_compras(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    proveedor_id: int | None = None,
    db: Session = Depends(get_db),
):
    from ..models import Compra, Proveedor

    q = db.query(Compra).filter(Compra.estado == "recibida")
    if proveedor_id:
        q = q.filter(Compra.proveedor_id == proveedor_id)
    if desde:
        q = q.filter(Compra.created_at >= desde)
    if hasta:
        q = q.filter(Compra.created_at <= hasta)
    compras = q.all()

    total = sum(float(c.total or 0) for c in compras)
    subtotal = sum(float(c.subtotal or 0) for c in compras)
    impuesto = sum(float(c.impuesto or 0) for c in compras)

    por_proveedor = {}
    for c in compras:
        prov = db.get(Proveedor, c.proveedor_id)
        nombre = prov.nombre if prov else f"proveedor_{c.proveedor_id}"
        por_proveedor[nombre] = por_proveedor.get(nombre, 0) + float(c.total or 0)

    return {
        "total_compras": total,
        "subtotal": subtotal,
        "impuesto": impuesto,
        "numero_compras": len(compras),
        "por_proveedor": por_proveedor,
    }


@router.get("/estado-resultados")
def estado_resultados(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
):
    from ..models import Compra, Gasto

    ventas = db.query(Venta).filter(Venta.estado == "completada")
    if desde:
        ventas = ventas.filter(Venta.created_at >= desde)
    if hasta:
        ventas = ventas.filter(Venta.created_at <= hasta)
    vs = ventas.all()

    ingresos = sum(float(v.total or 0) for v in vs)
    costo_ventas = sum(float(v.costo_total or 0) for v in vs)

    gastos_q = db.query(Gasto)
    if desde:
        gastos_q = gastos_q.filter(Gasto.created_at >= desde)
    if hasta:
        gastos_q = gastos_q.filter(Gasto.created_at <= hasta)
    total_gastos = sum(float(g.monto or 0) for g in gastos_q.all())

    return {
        "ingresos_ventas": ingresos,
        "costo_ventas": costo_ventas,
        "utilidad_bruta": ingresos - costo_ventas,
        "gastos": total_gastos,
        "utilidad_neta": ingresos - costo_ventas - total_gastos,
    }


@router.get("/cartera")
def reporte_cartera(db: Session = Depends(get_db)):
    from ..models import CuentaPagar

    cuentas_cobrar = db.query(func.sum(Cliente.creditos)).scalar() or 0
    cuentas_pagar = (
        db.query(func.sum(CuentaPagar.saldo))
        .filter(CuentaPagar.estado == "pendiente")
        .scalar()
        or 0
    )
    return {
        "cuentas_por_cobrar": float(cuentas_cobrar),
        "cuentas_por_pagar": float(cuentas_pagar),
        "flujo_estimado": float(cuentas_cobrar) - float(cuentas_pagar),
    }


@router.get("/compras-sugeridas")
def compras_sugeridas(
    sucursal_id: int | None = None,
    db: Session = Depends(get_db),
):
    """Productos cuyo stock está en o por debajo del punto de reorden."""
    f = Stock.existencias <= Producto.punto_reorden
    if sucursal_id:
        f = and_(f, Stock.sucursal_id == sucursal_id)
    filas = (
        db.query(
            Producto.id, Producto.nombre, Stock.existencias,
            Producto.punto_reorden, Producto.stock_maximo,
        )
        .join(Stock, Stock.producto_id == Producto.id)
        .filter(f)
        .all()
    )
    return [
        {
            "producto_id": pid,
            "producto": nombre,
            "existencias": float(exist),
            "punto_reorden": float(orden),
            "stock_maximo": float(maximo),
            "sugerido_comprar": max(0, float(maximo) - float(exist)),
        }
        for pid, nombre, exist, orden, maximo in filas
    ]


@router.get("/alertas")
def alertas(db: Session = Depends(get_db)):
    from datetime import timedelta

    from ..models import CuentaPagar, Gasto, Lote, AperturaCaja

    hoy = datetime.now().date()
    bajo_stock = (
        db.query(func.count())
        .select_from(Stock)
        .join(Producto, Stock.producto_id == Producto.id)
        .filter(Stock.existencias <= Producto.punto_reorden)
        .scalar()
        or 0
    )
    sobreinventario = (
        db.query(func.count())
        .select_from(Stock)
        .join(Producto, Stock.producto_id == Producto.id)
        .filter(Producto.stock_maximo.isnot(None), Producto.stock_maximo > 0, Stock.existencias >= Producto.stock_maximo)
        .scalar()
        or 0
    )
    proximos_vencer = (
        db.query(func.count())
        .filter(Lote.vencimiento.isnot(None), Lote.vencimiento <= hoy + timedelta(days=30), Lote.vencimiento >= hoy, Lote.cantidad > 0)
        .scalar()
        or 0
    )
    productos_vencidos = (
        db.query(func.count())
        .filter(Lote.vencimiento.isnot(None), Lote.vencimiento < hoy, Lote.cantidad > 0)
        .scalar()
        or 0
    )
    ventas_hoy = db.query(func.count()).filter(Venta.estado == "completada", cast(Venta.created_at, Date) == hoy).scalar() or 0
    cajas_abiertas = db.query(func.count()).filter(AperturaCaja.estado == "abierta").scalar() or 0
    cx_por_cobrar = db.query(func.sum(Cliente.creditos)).scalar() or 0
    cx_por_pagar = db.query(func.sum(CuentaPagar.saldo)).filter(CuentaPagar.estado == "pendiente").scalar() or 0
    cuentas_pagar_proximas = (
        db.query(func.sum(CuentaPagar.saldo))
        .filter(
            CuentaPagar.estado == "pendiente",
            CuentaPagar.fecha_vencimiento.isnot(None),
            CuentaPagar.fecha_vencimiento <= hoy + timedelta(days=30),
        )
        .scalar()
        or 0
    )
    gastos_mes = (
        db.query(func.sum(Gasto.monto))
        .filter(Gasto.created_at >= hoy.replace(day=1))
        .scalar()
        or 0
    )
    from ..models import DocumentoFiscal

    facturacion_pendiente = (
        db.query(func.count())
        .filter(
            DocumentoFiscal.anulado == False,
            DocumentoFiscal.estado_dian.in_(("pendiente", "enviado", "rechazado")),
        )
        .scalar()
        or 0
    )
    return {
        "bajo_inventario": int(bajo_stock),
        "sobreinventario": int(sobreinventario),
        "productos_proximos_a_vencer": int(proximos_vencer),
        "productos_vencidos": int(productos_vencidos),
        "sin_ventas_hoy": int(ventas_hoy) == 0,
        "cajas_abiertas": int(cajas_abiertas),
        "cuentas_por_cobrar": float(cx_por_cobrar),
        "cuentas_por_pagar": float(cx_por_pagar),
        "cuentas_pagar_proximas": float(cuentas_pagar_proximas),
        "gastos_mes": float(gastos_mes),
        "facturacion_pendiente": int(facturacion_pendiente),
    }


@router.get("/metas")
def reporte_metas(db: Session = Depends(get_db)):
    """Metas diarias/mensuales, comparativos contra ayer/semana y ranking de vendedores."""
    from ..models import Configuracion, MetaVendedor

    hoy = datetime.now().date()

    def _config(clave, default="0"):
        fila = db.query(Configuracion).filter(Configuracion.clave == clave).first()
        return float(fila.valor or default) if fila else float(default)

    meta_diaria = _config("pos.meta_diaria")
    meta_mensual = _config("pos.meta_mensual")

    ventas = db.query(Venta).filter(Venta.estado == "completada")
    ventas_hoy = sum(
        float(v.total) for v in ventas.filter(cast(Venta.created_at, Date) == hoy).all()
    )
    ventas_ayer = sum(
        float(v.total)
        for v in ventas.filter(cast(Venta.created_at, Date) == hoy - timedelta(days=1)).all()
    )
    ventas_mes = sum(
        float(v.total) for v in ventas.filter(Venta.created_at >= hoy.replace(day=1)).all()
    )
    ventas_semana = sum(
        float(v.total) for v in ventas.filter(Venta.created_at >= hoy - timedelta(days=7)).all()
    )
    promedio_7d = ventas_semana / 7

    def _pct(actual, meta):
        return round(actual / meta * 100, 1) if meta > 0 else None

    def _delta(actual, base):
        return round((actual - base) / base * 100, 1) if base > 0 else None

    ranking = []
    filas = (
        db.query(
            Venta.usuario_id,
            func.sum(Venta.total).label("total"),
            func.count(Venta.id).label("n"),
        )
        .filter(Venta.estado == "completada", cast(Venta.created_at, Date) == hoy)
        .group_by(Venta.usuario_id)
        .order_by(func.sum(Venta.total).desc())
        .limit(8)
        .all()
    )
    for usuario_id, total, n in filas:
        if usuario_id is None:
            continue
        u = db.get(Usuario, usuario_id)
        if not u:
            continue
        meta_v = (
            db.query(MetaVendedor)
            .filter_by(vendedor_id=u.id, periodo=hoy.strftime("%Y-%m"))
            .first()
        )
        meta_ventas = float(meta_v.meta_ventas or 0) if meta_v else 0
        ranking.append(
            {
                "usuario_id": u.id,
                "vendedor": u.nombre,
                "ventas_hoy": float(total or 0),
                "transacciones": int(n or 0),
                "meta_mensual": meta_ventas,
                "cumplimiento_meta": _pct(float(total or 0), meta_ventas),
            }
        )

    return {
        "meta_diaria": meta_diaria,
        "meta_mensual": meta_mensual,
        "ventas_hoy": round(ventas_hoy, 2),
        "ventas_ayer": round(ventas_ayer, 2),
        "ventas_mes": round(ventas_mes, 2),
        "ventas_semana": round(ventas_semana, 2),
        "promedio_7d": round(promedio_7d, 2),
        "avance_diario_pct": _pct(ventas_hoy, meta_diaria),
        "avance_mensual_pct": _pct(ventas_mes, meta_mensual),
        "faltante_diario": round(max(0, meta_diaria - ventas_hoy), 2),
        "faltante_mensual": round(max(0, meta_mensual - ventas_mes), 2),
        "vs_ayer_pct": _delta(ventas_hoy, ventas_ayer),
        "vs_promedio_7d_pct": _delta(ventas_hoy, promedio_7d),
        "ranking_vendedores": ranking,
    }


@router.get("/vendedores")
def reporte_vendedores(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Ranking de vendedores con ventas, comisiones y cumplimiento de metas."""
    from ..models import MetaVendedor, ReglaComision, Usuario

    vendedores = db.query(Usuario).filter(Usuario.vendedor == True).all()
    resultado = []
    for v in vendedores:
        q = db.query(Venta).filter(Venta.estado == "completada", Venta.usuario_id == v.id)
        if desde:
            q = q.filter(Venta.created_at >= desde)
        if hasta:
            q = q.filter(Venta.created_at <= hasta)
        ventas = q.all()
        total = sum(float(x.total or 0) for x in ventas)
        utilidad = sum(float(x.total or 0) - float(x.costo_total or 0) for x in ventas)
        reglas = db.query(ReglaComision).filter(
            or_(ReglaComision.vendedor_id == v.id, ReglaComision.vendedor_id.is_(None))
        ).all()
        porcentaje = sum(float(r.porcentaje or 0) for r in reglas if r.vendedor_id == v.id) or (
            sum(float(r.porcentaje or 0) for r in reglas if r.vendedor_id is None)
        )
        comision = total * porcentaje / 100 if porcentaje else 0
        meta = (
            db.query(MetaVendedor)
            .filter_by(vendedor_id=v.id, periodo=datetime.now().strftime("%Y-%m"))
            .first()
        )
        resultado.append(
            {
                "vendedor_id": v.id,
                "vendedor": v.nombre,
                "ventas": total,
                "utilidad": utilidad,
                "transacciones": len(ventas),
                "comision": comision,
                "meta_ventas": float(meta.meta_ventas or 0) if meta else 0,
                "meta_utilidad": float(meta.meta_utilidad or 0) if meta else 0,
                "cumplimiento_meta": round(total / max(1, float(meta.meta_ventas or 0)) * 100, 1) if meta else None,
            }
        )
    resultado.sort(key=lambda r: r["ventas"], reverse=True)
    return resultado


@router.get("/auditoria")
def reporte_auditoria(
    modulo: str | None = Query(None),
    limite: int = Query(200, le=1000),
    db: Session = Depends(get_db),
):
    from ..models import AuditoriaLog, Usuario

    q = db.query(AuditoriaLog)
    if modulo:
        q = q.filter(AuditoriaLog.modulo == modulo)
    logs = q.order_by(AuditoriaLog.id.desc()).limit(limite).all()
    nombres = {u.id: u.nombre for u in db.query(Usuario).all()}
    return [
        {
            "id": l.id,
            "usuario": nombres.get(l.usuario_id, f"usuario_{l.usuario_id}"),
            "modulo": l.modulo,
            "accion": l.accion,
            "entidad": l.entidad,
            "entidad_id": l.entidad_id,
            "detalle": l.detalle,
            "fecha": str(l.created_at),
        }
        for l in logs
    ]


# ---------- Exportaciones XLS (SpreadsheetML) y PDF ----------

def _spreadsheetml(titulo: str, encabezados: list[str], filas: list[list]) -> bytes:
    def celda(v):
        texto = "" if v is None else str(v)
        texto = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        try:
            f = float(texto)
            if any(ch in texto for ch in ".,"):
                return f'<Cell><Data ss:Type="Number">{f}</Data></Cell>'
            return f'<Cell><Data ss:Type="Number">{int(f)}</Data></Cell>'
        except (TypeError, ValueError):
            if texto == "True":
                return '<Cell><Data ss:Type="String">Si</Data></Cell>'
            if texto == "False":
                return '<Cell><Data ss:Type="String">No</Data></Cell>'
            return f'<Cell><Data ss:Type="String">{texto}</Data></Cell>'

    cab = "".join(f"<Cell><Data ss:Type='String'><B>{h}</B></Data></Cell>" for h in encabezados)
    cuerpo = "".join("<Row>" + "".join(celda(v) for v in fila) + "</Row>" for fila in filas)
    return (
        '<?xml version="1.0"?><?mso-application progid="Excel.Sheet"?>'
        '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" '
        'xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'
        f"<Worksheet ss:Name='{titulo[:28]}'>"
        f"<Table><Row>{cab}</Row>{cuerpo}</Table></Worksheet></Workbook>"
    ).encode("utf-8")


def _pdf_tabla(titulo: str, encabezados: list[str], filas: list[list]) -> bytes:
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), title=titulo)
    estilos = getSampleStyleSheet()
    parrafo_t = Paragraph(titulo, estilos["Title"])
    tabla_datos = [[Paragraph(str(h), estilos["BodyText"]) for h in encabezados]]
    for fila in filas:
        tabla_datos.append([Paragraph("" if v is None else str(v), estilos["BodyText"]) for v in fila])
    ancho = 780
    tabla = Table(tabla_datos, repeatRows=1)
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3f3f46")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f4f5")]),
            ]
        )
    )
    doc.build([parrafo_t, Spacer(1, 8), tabla])
    return buf.getvalue()


def _respuesta_exportar(titulo: str, encabezados: list[str], filas: list[list], formato: str):
    formato = (formato or "xls").lower()
    nombre = "".join(c for c in titulo.lower().replace(" ", "-") if c.isalnum() or c == "-")
    if formato == "pdf":
        return Response(
            _pdf_tabla(titulo, encabezados, filas),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{nombre}.pdf"'},
        )
    return Response(
        _spreadsheetml(titulo, encabezados, filas),
        media_type="application/vnd.ms-excel",
        headers={"Content-Disposition": f'attachment; filename="{nombre}.xls"'},
    )


@router.get("/exportar/ventas-por-producto")
def exportar_ventas_por_producto(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    formato: str = Query("xls"),
    db: Session = Depends(get_db),
):
    ini = _parse_fecha(desde)
    fin = _parse_fecha(hasta, fin_de_dia=True)
    dets = db.query(
        VentaDetalle.producto_id,
        Producto.nombre,
        func.sum(VentaDetalle.cantidad).label("cantidad"),
        func.sum(VentaDetalle.subtotal).label("subtotal"),
        func.count(func.distinct(VentaDetalle.venta_id)).label("ventas"),
    ).join(Venta, Venta.id == VentaDetalle.venta_id).join(
        Producto, Producto.id == VentaDetalle.producto_id
    )
    if ini:
        dets = dets.filter(Venta.created_at >= ini)
    if fin:
        dets = dets.filter(Venta.created_at < fin)
    dets = dets.group_by(VentaDetalle.producto_id, Producto.nombre).order_by(
        func.sum(VentaDetalle.subtotal).desc()
    )
    filas = [
        [fila.nombre, float(fila.cantidad or 0), fila.ventas, round(float(fila.subtotal or 0), 2)]
        for fila in dets.all()
    ]
    return _respuesta_exportar(
        "Ventas por producto",
        ["Producto", "Cantidad", "Numero de ventas", "Subtotal"],
        filas,
        formato,
    )


@router.get("/exportar/ventas")
def exportar_ventas(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    formato: str = Query("xls"),
    db: Session = Depends(get_db),
):
    ini = _parse_fecha(desde)
    fin = _parse_fecha(hasta, fin_de_dia=True)
    q = db.query(Venta)
    if ini:
        q = q.filter(Venta.created_at >= ini)
    if fin:
        q = q.filter(Venta.created_at < fin)
    filas = [
        [
            v.numero,
            str(v.created_at)[:16],
            v.estado,
            float(v.subtotal or 0),
            float(v.impuesto or 0),
            float(v.total or 0),
        ]
        for v in q.order_by(Venta.id.desc()).all()
    ]
    return _respuesta_exportar(
        "Ventas", ["Numero", "Fecha", "Estado", "Subtotal", "Impuesto", "Total"], filas, formato
    )


@router.get("/exportar/ventas-detallado")
def exportar_ventas_detallado(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    formato: str = Query("xls"),
    db: Session = Depends(get_db),
):
    """Ventas con cliente y cajero para conciliación contable."""
    ini = _parse_fecha(desde)
    fin = _parse_fecha(hasta, fin_de_dia=True)
    q = db.query(Venta)
    if ini:
        q = q.filter(Venta.created_at >= ini)
    if fin:
        q = q.filter(Venta.created_at < fin)
    clientes = {}
    cajeros = {}
    ids_cli = {v.cliente_id for v in q.all() if v.cliente_id}
    ids_caj = {v.usuario_id for v in q.all() if v.usuario_id}
    if ids_cli:
        for c in db.query(Cliente).filter(Cliente.id.in_(ids_cli)).all():
            clientes[c.id] = c.nombre
    if ids_caj:
        for u in db.query(Usuario).filter(Usuario.id.in_(ids_caj)).all():
            cajeros[u.id] = u.nombre
    filas = []
    total = 0.0
    for v in q.order_by(Venta.id.desc()).all():
        total += float(v.total or 0)
        filas.append(
            [
                v.numero,
                str(v.created_at)[:16],
                v.estado,
                clientes.get(v.cliente_id, ""),
                cajeros.get(v.usuario_id, ""),
                float(v.subtotal or 0),
                float(v.impuesto or 0),
                float(v.descuento or 0) if v.descuento else 0,
                float(v.total or 0),
            ]
        )
    filas.append(["TOTAL (COP)", "", "", "", "", "", "", "", round(total, 2)])
    return _respuesta_exportar(
        "Ventas detallado",
        ["Numero", "Fecha", "Estado", "Cliente", "Cajero", "Subtotal", "Impuesto", "Descuento", "Total"],
        filas,
        formato,
    )


@router.get("/exportar/cartera")
def exportar_cartera(
    formato: str = Query("xls"),
    db: Session = Depends(get_db),
):
    """Cuentas por cobrar (ventas a crédito no saldadas)."""
    filas = (
        db.query(Cliente, Venta)
        .join(Venta, Venta.cliente_id == Cliente.id)
        .filter(Venta.tipo == "credito", Venta.estado == "completada", Venta.saldo > 0)
        .order_by(Venta.id.desc())
        .all()
    )
    out = [
        [cliente.nombre, str(cliente.telefono or ""), v.numero, str(v.created_at)[:10], float(v.saldo or 0)]
        for cliente, v in filas
    ]
    total = round(sum(float(v.saldo or 0) for _, v in filas), 2)
    out.append(["TOTAL CARTERA (COP)", "", "", "", total])
    return _respuesta_exportar(
        "Cartera", ["Cliente", "Telefono", "Venta", "Fecha", "Saldo"], out, formato
    )


@router.get("/exportar/gastos")
def exportar_gastos(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    formato: str = Query("xls"),
    db: Session = Depends(get_db),
):
    ini = _parse_fecha(desde)
    fin = _parse_fecha(hasta, fin_de_dia=True)
    q = db.query(Gasto)
    if ini:
        q = q.filter(Gasto.created_at >= ini)
    if fin:
        q = q.filter(Gasto.created_at < fin)
    cajeros = {}
    ids = {g.usuario_id for g in q.all()}
    if ids:
        for u in db.query(Usuario).filter(Usuario.id.in_(ids)).all():
            cajeros[u.id] = u.nombre
    filas = [
        [
            g.id,
            str(g.created_at)[:16],
            g.categoria,
            str(g.concepto or ""),
            cajeros.get(g.usuario_id, ""),
            g.medio,
            float(g.monto or 0),
        ]
        for g in q.order_by(Gasto.id.desc()).all()
    ]
    total = round(sum(float(g.monto or 0) for g in q.all()), 2)
    filas.append(["TOTAL GASTOS (COP)", "", "", "", "", "", total])
    return _respuesta_exportar(
        "Gastos", ["Id", "Fecha", "Categoria", "Concepto", "Registrado por", "Medio", "Monto"], filas, formato
    )


@router.get("/exportar/compras")
def exportar_compras(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    formato: str = Query("xls"),
    db: Session = Depends(get_db),
):
    ini = _parse_fecha(desde)
    fin = _parse_fecha(hasta, fin_de_dia=True)
    q = db.query(Compra)
    if ini:
        q = q.filter(Compra.created_at >= ini)
    if fin:
        q = q.filter(Compra.created_at < fin)
    proveedores = {p.id: p.nombre for p in db.query(Proveedor).all()}
    filas = [
        [
            c.numero,
            str(c.created_at)[:16],
            proveedores.get(c.proveedor_id, ""),
            c.estado,
            float(c.total or 0),
        ]
        for c in q.order_by(Compra.id.desc()).all()
    ]
    total = round(sum(float(c.total or 0) for c in q.all()), 2)
    filas.append(["TOTAL COMPRAS (COP)", "", "", "", total])
    return _respuesta_exportar(
        "Compras", ["Numero", "Fecha", "Proveedor", "Estado", "Total"], filas, formato
    )


@router.get("/exportar/cierres")
def exportar_cierres(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    formato: str = Query("xls"),
    db: Session = Depends(get_db),
):
    """Cierres de caja (turnos cerrados)."""
    ini = _parse_fecha(desde)
    fin = _parse_fecha(hasta, fin_de_dia=True)
    q = (
        db.query(AperturaCaja)
        .join(Caja, Caja.id == AperturaCaja.caja_id)
        .filter(AperturaCaja.estado == "cerrada")
    )
    if ini:
        q = q.filter(AperturaCaja.created_at >= ini)
    if fin:
        q = q.filter(AperturaCaja.created_at < fin)
    cajas = {c.id: c.nombre for c in db.query(Caja).all()}
    cajeros = {}
    ids = {a.usuario_id for a in q.all()}
    if ids:
        for u in db.query(Usuario).filter(Usuario.id.in_(ids)).all():
            cajeros[u.id] = u.nombre
    filas = [
        [
            a.id,
            str(a.created_at)[:16],
            cajas.get(a.caja_id, f"Caja {a.caja_id}"),
            cajeros.get(a.usuario_id, ""),
            float(a.saldo_inicial or 0),
            float(a.saldo_cierre or 0),
        ]
        for a in q.order_by(AperturaCaja.id.desc()).all()
    ]
    total = round(sum(float(a.saldo_cierre or 0) for a in q.all()), 2)
    filas.append(["TOTAL CIERRES (COP)", "", "", "", "", total])
    return _respuesta_exportar(
        "Cierres de caja",
        ["Id", "Fecha", "Caja", "Cajero", "Saldo inicial", "Saldo de cierre"],
        filas,
        formato,
    )


# ---------- Reporte de proveedores ----------

@router.get("/proveedores")
def reporte_proveedores(db: Session = Depends(get_db)):
    proveedores = db.query(Proveedor).all()
    nombres = {p.id: p.nombre for p in proveedores}
    compras = (
        db.query(Compra.proveedor_id, func.sum(Compra.total), func.count(Compra.id))
        .group_by(Compra.proveedor_id)
        .all()
    )
    pagado = (
        db.query(AbonoProveedor.cuenta_id, func.sum(AbonoProveedor.monto))
        .group_by(AbonoProveedor.cuenta_id)
        .all()
    )
    pagado_por_proveedor = {}
    if pagado:
        cuenta_ids = [c for c, _ in pagado]
        cuentas = (
            db.query(CuentaPagar.id, CuentaPagar.proveedor_id)
            .filter(CuentaPagar.id.in_(cuenta_ids))
            .all()
        )
        prov_de_cuenta = {cid: pid for cid, pid in cuentas}
        for cid, monto in pagado:
            pid = prov_de_cuenta.get(cid)
            if pid:
                pagado_por_proveedor[pid] = pagado_por_proveedor.get(pid, 0) + float(monto or 0)
    deuda = (
        db.query(CuentaPagar.proveedor_id, func.sum(CuentaPagar.saldo))
        .filter(CuentaPagar.estado == "pendiente")
        .group_by(CuentaPagar.proveedor_id)
        .all()
    )
    deuda_por_proveedor = {pid: float(saldo or 0) for pid, saldo in deuda}
    mapa_compras = {pid: (float(total or 0), int(n or 0)) for pid, total, n in compras}
    resultado = []
    for p in proveedores:
        total, nc = mapa_compras.get(p.id, (0, 0))
        resultado.append(
            {
                "proveedor_id": p.id,
                "proveedor": p.nombre,
                "total_compras": total,
                "numero_compras": nc,
                "monto_pagado": round(pagado_por_proveedor.get(p.id, 0), 2),
                "deuda_pendiente": round(deuda_por_proveedor.get(p.id, 0), 2),
            }
        )
    resultado.sort(key=lambda r: r["total_compras"], reverse=True)
    return resultado


# ---------- Pronostico de ventas ----------

@router.get("/pronostico")
def reporte_pronostico(
    dias: int = Query(14, le=90),
    db: Session = Depends(get_db),
):
    hoy = datetime.now()
    inicio_ventana = hoy - timedelta(days=dias)
    inicio_anterior = inicio_ventana - timedelta(days=dias)
    datos = (
        db.query(
            VentaDetalle.producto_id,
            Producto.nombre,
            Producto.precio_venta,
            Producto.costo,
            func.sum(
                case(
                    (Venta.created_at >= inicio_anterior, VentaDetalle.cantidad),
                    else_=0,
                )
            ).label("previo"),
            func.sum(
                case(
                    (Venta.created_at >= inicio_ventana, VentaDetalle.cantidad),
                    else_=0,
                )
            ).label("reciente"),
        )
        .join(Venta, Venta.id == VentaDetalle.venta_id)
        .join(Producto, Producto.id == VentaDetalle.producto_id)
        .filter(Venta.created_at >= inicio_anterior, Venta.estado != "anulada")
        .group_by(VentaDetalle.producto_id, Producto.nombre, Producto.precio_venta, Producto.costo)
        .all()
    )
    resultado = []
    for pid, nombre, precio, costo, previo, reciente in datos:
        previo = float(previo or 0)
        reciente = float(reciente or 0)
        promedio = reciente / dias
        proyectado_14 = promedio * 14
        tendencia = round((reciente - previo) / previo * 100, 1) if previo > 0 else None
        stock_disp = (
            db.query(func.coalesce(func.sum(Stock.existencias), 0))
            .filter(Stock.producto_id == pid)
            .scalar()
        ) or 0
        venta_est = round(float(precio or 0) * proyectado_14, 2)
        resultado.append(
            {
                "producto_id": pid,
                "producto": nombre,
                "promedio_diario": round(promedio, 2),
                "proyeccion_14d": round(proyectado_14, 3),
                "venta_estimada": venta_est,
                "costo_estimado": round(float(costo or 0) * proyectado_14, 2),
                "stock_actual": float(stock_disp or 0),
                "tendencia_porcentaje": tendencia,
            }
        )
    resultado.sort(key=lambda r: r["venta_estimada"], reverse=True)
    return resultado


# ---------- Analitica de clientes y cartera ----------

@router.get("/clientes-analitica")
def clientes_analitica(db: Session = Depends(get_db)):
    from ..models import AbonoCliente

    ventas = db.query(Venta).filter(
        Venta.estado == "completada", Venta.cliente_id.isnot(None)
    ).all()

    nombres = {}
    tipos = {}
    docs = {}
    for c in db.query(Cliente).all():
        nombres[c.id] = c.nombre
        tipos[c.id] = c.tipo
        docs[c.id] = c.documento

    agg = {}
    for v in ventas:
        a = agg.setdefault(v.cliente_id, {"transacciones": 0, "total": 0.0})
        a["transacciones"] += 1
        a["total"] += float(v.total or 0)

    def lista(tipo_ord, key, asc=False):
        items = []
        for cid, a in agg.items():
            items.append(
                {
                    "cliente_id": cid,
                    "cliente": nombres.get(cid, f"cliente_{cid}"),
                    "tipo_cliente": tipos.get(cid, "ocasional"),
                    "transacciones": a["transacciones"],
                    "total": round(a["total"], 2),
                }
            )
        items.sort(key=lambda r: r[key], reverse=not asc)
        return items[:10]

    desde_30 = datetime.now().astimezone() - timedelta(days=30)
    desde_60 = datetime.now().astimezone() - timedelta(days=60)

    clientes = db.query(Cliente).filter(Cliente.activo == True).all()
    con_ventas_60 = {cid for (cid,) in db.query(Venta.cliente_id).filter(
        Venta.estado == "completada", Venta.created_at >= desde_60, Venta.cliente_id.isnot(None)
    ).all()}

    nuevos = [
        {
            "cliente_id": c.id,
            "cliente": c.nombre,
            "documento": c.documento,
            "telefono": c.telefono,
        }
        for c in sorted(
            [c for c in clientes if c.created_at and c.created_at >= desde_30],
            key=lambda x: x.created_at,
            reverse=True,
        )[:10]
    ]

    inactivos = [
        {
            "cliente_id": c.id,
            "cliente": c.nombre,
            "documento": c.documento,
            "telefono": c.telefono,
        }
        for c in clientes
        if c.id not in con_ventas_60
    ][:20]

    con_credito = [
        {
            "cliente_id": c.id,
            "cliente": c.nombre,
            "documento": c.documento,
            "tipo_cliente": c.tipo or "ocasional",
            "deuda": float(c.creditos or 0),
            "limite_credito": float(c.limite_credito or 0),
        }
        for c in clientes
        if float(c.creditos or 0) > 0
    ]
    con_credito.sort(key=lambda r: r["deuda"], reverse=True)

    dinero_vencido = {}
    corte = datetime.now().astimezone() - timedelta(days=30)
    for v in db.query(Venta).filter(
        Venta.estado == "completada",
        Venta.tipo == "credito",
        Venta.cliente_id.isnot(None),
        Venta.saldo.isnot(None),
        Venta.saldo > 0,
    ).all():
        if v.created_at and v.created_at < corte:
            dinero_vencido[v.cliente_id] = dinero_vencido.get(v.cliente_id, 0) + float(v.saldo or 0)
    cartera_vencida = [
        {
            "cliente_id": cid,
            "cliente": nombres.get(cid, f"cliente_{cid}"),
            "deuda_vencida": round(monto, 2),
        }
        for cid, monto in dinero_vencido.items()
    ]
    cartera_vencida.sort(key=lambda r: r["deuda_vencida"], reverse=True)

    abonos = db.query(AbonoCliente).order_by(AbonoCliente.id.desc()).limit(15).all()
    historial_abonos = [
        {
            "fecha": str(a.created_at)[:16],
            "cliente": nombres.get(a.cliente_id, f"cliente_{a.cliente_id}"),
            "monto": float(a.monto or 0),
            "medio": a.medio or "efectivo",
            "referencia": a.referencia,
        }
        for a in abonos
    ]

    return {
        "frecuentes": lista("frecuentes", "transacciones"),
        "mayor_consumo": lista("mayor_consumo", "total"),
        "nuevos": nuevos,
        "inactivos": inactivos,
        "con_credito": con_credito,
        "cartera_vencida": cartera_vencida,
        "historial_abonos": historial_abonos,
    }


# ---------- Flujo de caja (últimos 30 días) ----------

@router.get("/flujo-caja")
def flujo_caja(dias: int = Query(30, le=90), db: Session = Depends(get_db)):
    from ..models import AbonoCliente, AbonoProveedor

    inicio = datetime.now().astimezone() - timedelta(days=dias - 1)
    dias_totales = {}

    def fila(dia):
        if dia not in dias_totales:
            dias_totales[dia] = {"fecha": str(dia), "ingresos": 0.0, "egresos": 0.0}
        return dias_totales[dia]

    ventas = db.query(
        cast(Venta.created_at, Date).label("d"), func.sum(Venta.total).label("m")
    ).filter(Venta.estado == "completada", Venta.created_at >= inicio).group_by(cast(Venta.created_at, Date)).all()
    for d, m in ventas:
        fila(d)["ingresos"] += float(m or 0)

    abonos_cli = db.query(
        cast(AbonoCliente.created_at, Date).label("d"), func.sum(AbonoCliente.monto).label("m")
    ).filter(AbonoCliente.created_at >= inicio).group_by(cast(AbonoCliente.created_at, Date)).all()
    for d, m in abonos_cli:
        fila(d)["ingresos"] += float(m or 0)

    gastos = db.query(
        cast(Gasto.created_at, Date).label("d"), func.sum(Gasto.monto).label("m")
    ).filter(Gasto.created_at >= inicio).group_by(cast(Gasto.created_at, Date)).all()
    for d, m in gastos:
        fila(d)["egresos"] += float(m or 0)

    abonos_prov = db.query(
        cast(AbonoProveedor.created_at, Date).label("d"), func.sum(AbonoProveedor.monto).label("m")
    ).filter(AbonoProveedor.created_at >= inicio).group_by(cast(AbonoProveedor.created_at, Date)).all()
    for d, m in abonos_prov:
        fila(d)["egresos"] += float(m or 0)

    serie = sorted(dias_totales.values(), key=lambda r: r["fecha"])
    for r in serie:
        r["neto"] = round(r["ingresos"] - r["egresos"], 2)

    total_ingresos = sum(r["ingresos"] for r in serie)
    total_egresos = sum(r["egresos"] for r in serie)
    return {
        "serie": serie,
        "total_ingresos": round(total_ingresos, 2),
        "total_egresos": round(total_egresos, 2),
        "total_neto": round(total_ingresos - total_egresos, 2),
    }


# ============================================================
#  Reportes de inventario por bodega/ubicación y diferencias
# ============================================================

@router.get("/rotacion")
def rotacion_inventario(
    dias: int = Query(30, le=120),
    db: Session = Depends(get_db),
):
    from ..models import MovimientoInventario

    desde = datetime.now() - timedelta(days=dias)
    salidas = (
        db.query(
            VentaDetalle.producto_id,
            func.sum(VentaDetalle.cantidad).label("vendido"),
        )
        .join(Venta, Venta.id == VentaDetalle.venta_id)
        .filter(Venta.estado == "completada", Venta.created_at >= desde)
        .group_by(VentaDetalle.producto_id)
        .all()
    )
    nombres = {p.id: p.nombre for p in db.query(Producto).all()}
    stock_actual = {}
    for s in db.query(Stock).all():
        stock_actual[s.producto_id] = stock_actual.get(s.producto_id, 0) + float(s.existencias or 0)
    resultado = []
    for pid, vendido in salidas:
        cantidad = float(vendido or 0)
        actual = stock_actual.get(pid, 0)
        resultado.append(
            {
                "producto_id": pid,
                "producto": nombres.get(pid, f"producto_{pid}"),
                "vendido_periodo": round(cantidad, 2),
                "stock_promedio": round(actual, 2),
                "rotacion_periodo": round(cantidad / actual, 2) if actual > 0 else None,
                "dias_estimados_agotar": round(actual * dias / cantidad, 1) if cantidad > 0 else None,
            }
        )
    resultado.sort(key=lambda r: r["vendido_periodo"], reverse=True)
    return resultado


@router.get("/inventario-por-categoria")
def inventario_por_categoria(
    sucursal_id: int | None = None,
    db: Session = Depends(get_db),
):
    from ..models import Categoria, Stock

    q = db.query(Producto.categoria_id, func.sum(Stock.existencias).label("existencias"))
    q = q.join(Stock, Stock.producto_id == Producto.id)
    if sucursal_id:
        q = q.filter(Stock.sucursal_id == sucursal_id)
    q = q.group_by(Producto.categoria_id)
    nombres = {c.id: c.nombre for c in db.query(Categoria).all()}
    filas = q.all()
    resultado = [
        {
            "categoria": nombres.get(cid) or "Sin categoría",
            "categoria_id": cid,
            "existencias": float(exist or 0),
        }
        for cid, exist in filas
    ]
    resultado.sort(key=lambda r: r["existencias"], reverse=True)
    return resultado


@router.get("/inventario-por-sucursal")
def inventario_por_sucursal(
    producto_id: int | None = None,
    db: Session = Depends(get_db),
):
    from ..models import Categoria, Stock

    q = db.query(Stock.sucursal_id, func.sum(Stock.existencias).label("existencias"))
    if producto_id:
        q = q.filter(Stock.producto_id == producto_id)
    q = q.group_by(Stock.sucursal_id)
    nombres = {s.id: s.nombre for s in db.query(Sucursal).all()}
    return [
        {
            "sucursal_id": sid,
            "sucursal": nombres.get(sid, f"sucursal_{sid}"),
            "existencias": float(exist or 0),
        }
        for sid, exist in q.order_by(Stock.sucursal_id.asc()).all()
    ]


@router.get("/inventario-por-bodega")
def inventario_por_bodega(
    bodega_id: int | None = None,
    db: Session = Depends(get_db),
):
    from ..models import Bodega, StockBodega

    q = db.query(
        StockBodega.bodega_id,
        func.sum(StockBodega.existencias).label("existencias"),
    )
    if bodega_id:
        q = q.filter(StockBodega.bodega_id == bodega_id)
    q = q.group_by(StockBodega.bodega_id)
    nombres = {b.id: b.nombre for b in db.query(Bodega).all()}
    filas = q.all()
    resultado = [
        {
            "bodega_id": bid,
            "bodega": nombres.get(bid, f"bodega_{bid}"),
            "existencias": float(exist or 0),
        }
        for bid, exist in filas
    ]
    resultado.sort(key=lambda r: r["existencias"], reverse=True)
    return resultado


@router.get("/diferencias-inventario")
def diferencias_inventario(
    db: Session = Depends(get_db),
):
    """Diferencias entre lo esperado y lo contado en los conteos (físicos/cíclicos)."""
    from ..models import ConteoFisico, ConteoFisicoDetalle

    nombres = {p.id: p.nombre for p in db.query(Producto).all()}
    q = (
        db.query(
            ConteoFisicoDetalle.producto_id,
            ConteoFisicoDetalle.conteo_id,
            ConteoFisico.numero,
            ConteoFisico.estado,
            func.sum(ConteoFisicoDetalle.esperado).label("esperado"),
            func.sum(ConteoFisicoDetalle.contado).label("contado"),
            func.sum(ConteoFisicoDetalle.diferencia).label("diferencia"),
        )
        .join(ConteoFisico, ConteoFisico.id == ConteoFisicoDetalle.conteo_id)
        .group_by(
            ConteoFisicoDetalle.producto_id,
            ConteoFisicoDetalle.conteo_id,
            ConteoFisico.numero,
            ConteoFisico.estado,
        )
        .order_by(ConteoFisicoDetalle.conteo_id.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "conteo_id": cid,
            "numero": numero,
            "estado": estado,
            "producto_id": pid,
            "producto": nombres.get(pid, f"producto_{pid}"),
            "esperado": float(esperado or 0),
            "contado": float(contado or 0),
            "diferencia": float(diff or 0),
        }
        for pid, cid, numero, estado, esperado, contado, diff in q
    ]


# ============================================================
#  Reportes de compras y proveedores
# ============================================================

@router.get("/compras-periodo")
def compras_por_periodo(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
):
    from ..models import Compra

    _y = extract("year", Compra.created_at)
    _m = extract("month", Compra.created_at)
    q = db.query(_y.label("y"), _m.label("m"), func.sum(Compra.total).label("total"), func.count(Compra.id).label("n")).filter(Compra.estado != "anulada")
    if desde:
        q = q.filter(Compra.created_at >= desde)
    if hasta:
        q = q.filter(Compra.created_at <= hasta)
    filas = q.group_by(_y, _m).order_by(_y, _m).all()
    return [
        {"periodo": f"{int(y or 0):04d}-{int(m or 0):02d}", "total": float(t or 0), "numero_compras": int(n or 0)}
        for y, m, t, n in filas
    ]
    return [
        {"periodo": p, "total": float(t or 0), "numero_compras": int(n or 0)}
        for p, t, n in filas
    ]


@router.get("/compras-por-proveedor")
def compras_por_proveedor(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
):
    from ..models import Compra, Proveedor

    nombres = {p.id: p.nombre for p in db.query(Proveedor).all()}
    q = db.query(Compra.proveedor_id, func.sum(Compra.total), func.count(Compra.id))
    q = q.filter(Compra.estado != "anulada")
    if desde:
        q = q.filter(Compra.created_at >= desde)
    if hasta:
        q = q.filter(Compra.created_at <= hasta)
    q = q.group_by(Compra.proveedor_id)
    resultado = [
        {
            "proveedor_id": pid,
            "proveedor": nombres.get(pid, f"proveedor_{pid}"),
            "total_compras": round(float(t or 0), 2),
            "numero_compras": int(n or 0),
        }
        for pid, t, n in q.all()
    ]
    resultado.sort(key=lambda r: r["total_compras"], reverse=True)
    return resultado


@router.get("/compras-por-producto")
def compras_por_producto(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
):
    from ..models import Compra, CompraDetalle

    nombres = {p.id: p.nombre for p in db.query(Producto).all()}
    q = (
        db.query(CompraDetalle.producto_id, func.sum(CompraDetalle.cantidad), func.sum(CompraDetalle.subtotal))
        .join(Compra, Compra.id == CompraDetalle.compra_id)
        .filter(Compra.estado != "anulada")
    )
    if desde:
        q = q.filter(Compra.created_at >= desde)
    if hasta:
        q = q.filter(Compra.created_at <= hasta)
    q = q.group_by(CompraDetalle.producto_id)
    filas = q.order_by(func.sum(CompraDetalle.subtotal).desc()).all()
    return [
        {
            "producto_id": pid,
            "producto": nombres.get(pid, f"producto_{pid}"),
            "cantidad": float(cant or 0),
            "subtotal": round(float(sub or 0), 2),
        }
        for pid, cant, sub in filas
    ]


@router.get("/compras-por-sucursal")
def compras_por_sucursal(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
):
    from ..models import Compra

    nombres = {s.id: s.nombre for s in db.query(Sucursal).all()}
    q = db.query(Compra.sucursal_id, func.sum(Compra.total), func.count(Compra.id))
    q = q.filter(Compra.estado != "anulada")
    if desde:
        q = q.filter(Compra.created_at >= desde)
    if hasta:
        q = q.filter(Compra.created_at <= hasta)
    q = q.group_by(Compra.sucursal_id)
    resultado = [
        {
            "sucursal_id": sid,
            "sucursal": nombres.get(sid, f"sucursal_{sid}"),
            "total_compras": round(float(t or 0), 2),
            "numero_compras": int(n or 0),
        }
        for sid, t, n in q.all()
    ]
    resultado.sort(key=lambda r: r["total_compras"], reverse=True)
    return resultado


@router.get("/compras-pendientes")
def compras_pendientes(db: Session = Depends(get_db)):
    from ..models import Compra, Proveedor

    nombres = {p.id: p.nombre for p in db.query(Proveedor).all()}
    filas = (
        db.query(Compra)
        .filter(Compra.estado == "pendiente")
        .order_by(Compra.id.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "compra_id": c.id,
            "numero": c.numero,
            "proveedor_id": c.proveedor_id,
            "proveedor": nombres.get(c.proveedor_id),
            "fecha": str(c.created_at)[:16],
            "total": float(c.total or 0),
        }
        for c in filas
    ]


@router.get("/compras-recibidas")
def compras_recibidas(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
):
    from ..models import Compra, Proveedor

    nombres = {p.id: p.nombre for p in db.query(Proveedor).all()}
    q = db.query(Compra).filter(Compra.estado == "recibida")
    if desde:
        q = q.filter(Compra.created_at >= desde)
    if hasta:
        q = q.filter(Compra.created_at <= hasta)
    filas = q.order_by(Compra.id.desc()).limit(100).all()
    return [
        {
            "compra_id": c.id,
            "numero": c.numero,
            "proveedor_id": c.proveedor_id,
            "proveedor": nombres.get(c.proveedor_id),
            "fecha": str(c.created_at)[:16],
            "total": float(c.total or 0),
        }
        for c in filas
    ]


@router.get("/compras-anuladas")
def compras_anuladas(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
):
    from ..models import Compra, Proveedor

    nombres = {p.id: p.nombre for p in db.query(Proveedor).all()}
    q = db.query(Compra).filter(Compra.estado == "anulada")
    if desde:
        q = q.filter(Compra.created_at >= desde)
    if hasta:
        q = q.filter(Compra.created_at <= hasta)
    filas = q.order_by(Compra.id.desc()).limit(100).all()
    return [
        {
            "compra_id": c.id,
            "numero": c.numero,
            "proveedor_id": c.proveedor_id,
            "proveedor": nombres.get(c.proveedor_id),
            "fecha": str(c.created_at)[:16],
            "total": float(c.total or 0),
        }
        for c in filas
    ]


@router.get("/proveedores-principales")
def proveedores_principales(
    limite: int = Query(10, le=50),
    db: Session = Depends(get_db),
):
    from ..models import Compra

    nombres = {p.id: p.nombre for p in db.query(Proveedor).all()}
    filas = (
        db.query(
            Compra.proveedor_id,
            func.sum(Compra.total).label("total"),
            func.count(Compra.id).label("n"),
        )
        .filter(Compra.estado != "anulada")
        .group_by(Compra.proveedor_id)
        .order_by(func.sum(Compra.total).desc())
        .limit(limite)
        .all()
    )
    return [
        {
            "proveedor_id": pid,
            "proveedor": nombres.get(pid, f"proveedor_{pid}"),
            "total_compras": round(float(t or 0), 2),
            "numero_compras": int(n or 0),
        }
        for pid, t, n in filas
    ]


@router.get("/proveedores-historial/{proveedor_id}")
def historial_proveedor(
    proveedor_id: int,
    db: Session = Depends(get_db),
):
    from ..models import Compra, CuentaPagar

    proveedor = db.get(Proveedor, proveedor_id)
    if not proveedor:
        raise HTTPException(404, "Proveedor no existe")
    compras = (
        db.query(Compra)
        .filter(Compra.proveedor_id == proveedor_id)
        .order_by(Compra.id.desc())
        .limit(100)
        .all()
    )
    cuentas = db.query(CuentaPagar).filter(CuentaPagar.proveedor_id == proveedor_id).all()
    return {
        "proveedor_id": proveedor.id,
        "proveedor": proveedor.nombre,
        "total_compras": sum(float(c.total or 0) for c in compras),
        "numero_compras": len(compras),
        "deuda_pendiente": sum(float(c.saldo or 0) for c in cuentas if c.estado == "pendiente"),
        "historial": [
            {
                "compra_id": c.id,
                "numero": c.numero,
                "fecha": str(c.created_at)[:16],
                "estado": c.estado,
                "subtotal": float(c.subtotal or 0),
                "total": float(c.total or 0),
            }
            for c in compras
        ],
    }


@router.get("/productos-por-proveedor")
def productos_por_proveedor(
    proveedor_id: int | None = None,
    db: Session = Depends(get_db),
):
    """Último costo y totales por proveedor-producto."""
    from ..models import Compra, CompraDetalle

    q = (
        db.query(
            CompraDetalle.producto_id,
            Compra.proveedor_id,
            func.sum(CompraDetalle.cantidad).label("cantidad"),
            func.max(CompraDetalle.costo_unitario).label("ultimo_costo"),
        )
        .join(Compra, Compra.id == CompraDetalle.compra_id)
        .filter(Compra.estado != "anulada")
    )
    if proveedor_id:
        q = q.filter(Compra.proveedor_id == proveedor_id)
    q = q.group_by(CompraDetalle.producto_id, Compra.proveedor_id)
    nombres = {p.id: p.nombre for p in db.query(Producto).all()}
    prov_nombres = {p.id: p.nombre for p in db.query(Proveedor).all()}
    filas = q.order_by(Compra.proveedor_id.asc(), func.sum(CompraDetalle.cantidad).desc()).limit(200).all()
    return [
        {
            "producto_id": pid,
            "producto": nombres.get(pid, f"producto_{pid}"),
            "proveedor_id": prid,
            "proveedor": prov_nombres.get(prid, f"proveedor_{prid}"),
            "cantidad": float(cant or 0),
            "ultimo_costo": float(ultimo or 0),
        }
        for pid, prid, cant, ultimo in filas
    ]


@router.get("/precios-proveedor/{proveedor_id}")
def precios_proveedor(
    proveedor_id: int,
    db: Session = Depends(get_db),
):
    """Catálogo del proveedor: costo actual ofrecido por cada producto."""
    from ..models import Compra, CompraDetalle

    proveedor = db.get(Proveedor, proveedor_id)
    if not proveedor:
        raise HTTPException(404, "Proveedor no existe")
    filas = (
        db.query(
            CompraDetalle.producto_id,
            func.max(CompraDetalle.costo_unitario).label("ultimo_costo"),
            func.sum(CompraDetalle.cantidad).label("cantidad"),
        )
        .join(Compra, Compra.id == CompraDetalle.compra_id)
        .filter(Compra.proveedor_id == proveedor_id, Compra.estado != "anulada")
        .group_by(CompraDetalle.producto_id)
        .order_by(func.max(CompraDetalle.costo_unitario).desc())
        .all()
    )
    nombres = {p.id: p.nombre for p in db.query(Producto).all()}
    return [
        {
            "producto_id": pid,
            "producto": nombres.get(pid, f"producto_{pid}"),
            "ultimo_costo": round(float(costo or 0), 2),
            "cantidad_total": float(cant or 0),
        }
        for pid, costo, cant in filas
    ]


@router.get("/caja")
def reporte_caja(
    apertura_id: int | None = None,
    caja_id: int | None = None,
    limite: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """Resumen por apertura/turno: ventas, movimientos, arqueo y cierre."""
    q = db.query(AperturaCaja).order_by(AperturaCaja.id.desc())
    if apertura_id:
        q = q.filter(AperturaCaja.id == apertura_id)
    if caja_id:
        q = q.filter(AperturaCaja.caja_id == caja_id)
    nombres = {u.id: u.nombre for u in db.query(Usuario).all()}
    salida = []
    for a in q.limit(limite).all():
        fin_turno = datetime.now(timezone.utc) if a.estado == "abierta" else (a.updated_at or datetime.now(timezone.utc))
        ventas = (
            db.query(Venta)
            .filter(Venta.caja_id == a.caja_id, Venta.estado == "completada")
            .all()
        )
        ventas_turno = []
        for v in ventas:
            inicio = a.created_at
            if inicio <= (v.created_at or inicio) <= fin_turno:
                ventas_turno.append(v)
        total_ventas = sum(float(v.total or 0) for v in ventas_turno)
        ventas_efectivo = sum(
            float(p.monto or 0) for v in ventas_turno for p in v.pagos if p.medio == "efectivo"
        )
        movs = (
            db.query(MovimientoCaja)
            .filter(MovimientoCaja.apertura_caja_id == a.id)
            .all()
        )
        ingresos = sum(float(m.monto or 0) for m in movs if m.tipo == "ingreso")
        egresos = sum(float(m.monto or 0) for m in movs if m.tipo in ("egreso", "gasto", "retiro"))
        arqueo = (
            db.query(ArqueoCaja)
            .filter(ArqueoCaja.apertura_caja_id == a.id)
            .order_by(ArqueoCaja.id.desc())
            .first()
        )
        salida.append(
            {
                "apertura_id": a.id,
                "caja_id": a.caja_id,
                "cajero": nombres.get(a.usuario_id),
                "saldo_inicial": float(a.saldo_inicial or 0),
                "total_ventas": round(total_ventas, 2),
                "ventas_efectivo": round(ventas_efectivo, 2),
                "ingresos": round(ingresos, 2),
                "egresos": round(egresos, 2),
                "saldo_cierre": float(a.saldo_cierre or 0),
                "estado": a.estado,
                "created_at": a.created_at,
                "arqueo": (
                    {
                        "contado": round(float(arqueo.contado_efectivo or 0), 2),
                        "esperado": round(float(arqueo.contado_esperado or 0), 2),
                        "diferencia": round(float(arqueo.diferencia or 0), 2),
                        "observacion": arqueo.observacion,
                    }
                    if arqueo
                    else None
                ),
            }
        )
    return salida


@router.get("/ventas-por-cajero")
def reporte_ventas_por_cajero(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    sucursal_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Venta).filter(Venta.estado == "completada").limit(500)
    fdesde = _parse_fecha(desde)
    fhasta = _parse_fecha(hasta, fin_de_dia=True)
    if fdesde:
        query = query.filter(Venta.created_at >= fdesde)
    if fhasta:
        query = query.filter(Venta.created_at < fhasta)
    if sucursal_id:
        query = query.filter(Venta.sucursal_id == sucursal_id)
    ventas = query.all()
    nombres = {u.id: u.nombre for u in db.query(Usuario).all()}
    por = {}
    for v in ventas:
        d = por.setdefault(
            v.usuario_id,
            {
                "cajero": nombres.get(v.usuario_id, f"usuario_{v.usuario_id}"),
                "ventas": 0,
                "total": 0.0,
                "monto_pagado": 0.0,
            },
        )
        d["ventas"] += 1
        d["total"] += float(v.total or 0)
        d["monto_pagado"] += sum(float(p.monto or 0) for p in v.pagos)
    return sorted(por.values(), key=lambda x: -x["total"])


@router.get("/ventas-por-turno")
def reporte_ventas_por_turno(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Venta).filter(Venta.estado == "completada").limit(500)
    fdesde = _parse_fecha(desde)
    fhasta = _parse_fecha(hasta, fin_de_dia=True)
    if fdesde:
        query = query.filter(Venta.created_at >= fdesde)
    if fhasta:
        query = query.filter(Venta.created_at < fhasta)
    ventas = query.all()
    nombres = {u.id: u.nombre for u in db.query(Usuario).all()}
    turnos = {}
    for v in ventas:
        aperturas = (
            db.query(AperturaCaja)
            .filter(AperturaCaja.caja_id == v.caja_id)
            .order_by(AperturaCaja.id.desc())
            .all()
        )
        turno = None
        for a in aperturas:
            inicio = a.created_at
            fin = datetime.now(timezone.utc) if a.estado == "abierta" else (a.updated_at or datetime.now(timezone.utc))
            if inicio <= (v.created_at or inicio) <= fin:
                turno = a
                break
        if turno is None:
            continue
        d = turnos.setdefault(
            turno.id,
            {
                "apertura_id": turno.id,
                "caja_id": turno.caja_id,
                "cajero": nombres.get(turno.usuario_id),
                "inicio": turno.created_at,
                "cierre": turno.updated_at,
                "estado": turno.estado,
                "ventas": 0,
                "total": 0.0,
            },
        )
        d["ventas"] += 1
        d["total"] += float(v.total or 0)
    return sorted(turnos.values(), key=lambda x: x["inicio"], reverse=True)


@router.get("/por-vencer")
def por_vencer(dias: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    """Control de vencimientos: lotes próximos a vencer y vencidos."""
    from ..models import Lote

    hoy = datetime.now(timezone.utc).date()
    lotes = db.query(Lote).filter(Lote.activo == True, (Lote.cantidad or 0) > 0).all()
    resultado = []
    for lo in lotes:
        cantidad = float(lo.cantidad or 0)
        if cantidad <= 0:
            continue
        venc = lo.vencimiento
        if venc:
            dias_restantes = (venc - hoy).days
            estado = "vencido" if dias_restantes < 0 else ("por_vencer" if dias_restantes <= dias else "vigente")
        else:
            dias_restantes = None
            estado = "sin_vencimiento"
        if estado in ("vencido", "por_vencer"):
            producto = db.get(Producto, lo.producto_id)
            resultado.append(
                {
                    "lote_id": lo.id,
                    "codigo_lote": lo.codigo,
                    "producto_id": lo.producto_id,
                    "producto": producto.nombre if producto else None,
                    "cantidad": cantidad,
                    "vencimiento": str(venc) if venc else None,
                    "estado": estado,
                    "dias_restantes": dias_restantes,
                }
            )
    resultado.sort(key=lambda r: (r["estado"], r["dias_restantes"] or 0))
    return {"vencidos": sum(1 for r in resultado if r["estado"] == "vencido"), "lotes": resultado}


@router.get("/lotes-etiquetas")
def lotes_etiquetas(db: Session = Depends(get_db)):
    """Etiquetas por lote: datos listos para impresión de etiquetas."""
    from ..models import Lote

    lotes = db.query(Lote).filter(Lote.activo == True).all()
    etiquetas = []
    for lo in lotes:
        cantidad = float(lo.cantidad or 0)
        producto = db.get(Producto, lo.producto_id)
        etiquetas.append(
            {
                "lote_id": lo.id,
                "codigo_lote": lo.codigo,
                "producto_id": lo.producto_id,
                "codigo_producto": producto.sku if producto else None,
                "producto": producto.nombre if producto else None,
                "cantidad": cantidad,
                "vencimiento": str(lo.vencimiento) if lo.vencimiento else None,
                "activo": lo.activo,
            }
        )
    return {"total_lotes": len(etiquetas), "etiquetas": etiquetas}