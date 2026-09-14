from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    AbonoProveedor,
    AuditoriaLog,
    Compra,
    CompraDetalle,
    CotizacionProveedor,
    CotizacionProveedorDetalle,
    CuentaPagar,
    DevolucionCompra,
    DevolucionCompraDetalle,
    MovimientoInventario,
    OrdenCompra,
    OrdenCompraDetalle,
    Producto,
    Proveedor,
    Stock,
    Usuario,
)
from ..schemas.avanzado import (
    CotizacionProveedorCreate,
    CotizacionProveedorOut,
    DevolucionCompraCreate,
    DevolucionCompraOut,
)
from ..schemas.compras import (
    AbonoProveedorCreate,
    AbonoProveedorOut,
    CompraCreate,
    CompraOut,
    CuentaPagarOut,
    OrdenCompraCreate,
    OrdenCompraOut,
)

router = APIRouter(prefix="/compras", tags=["compras"])


def _obtener_stock(db: Session, producto_id: int, sucursal_id: int) -> Stock:
    stock = (
        db.query(Stock)
        .filter_by(producto_id=producto_id, sucursal_id=sucursal_id)
        .first()
    )
    if not stock:
        stock = Stock(producto_id=producto_id, sucursal_id=sucursal_id)
        db.add(stock)
        db.flush()
    return stock


def _recibir_mercancia(db: Session, compra_id: int):
    """Genera entradas de inventario y actualiza costo promedio."""
    db.flush()  # garantiza que los detalles pendientes existan en la sesión
    compra = db.get(Compra, compra_id)
    for det in compra.detalle:
        producto = db.get(Producto, det.producto_id)
        stock = _obtener_stock(db, det.producto_id, compra.sucursal_id)
        previas = float(stock.existencias or 0)
        stock.existencias = previas + float(det.cantidad)
        stock.disponible = stock.existencias - float(stock.reservado or 0)

        # costo promedio
        entrada = float(det.costo_unitario)
        total_unidades = previas + float(det.cantidad)
        if total_unidades > 0:
            producto.costo = (
                float(producto.costo or 0) * previas + entrada * float(det.cantidad)
            ) / total_unidades
        else:
            producto.costo = entrada

        from ..models import MovimientoInventario
        db.add(
            MovimientoInventario(
                producto_id=det.producto_id,
                sucursal_id=compra.sucursal_id,
                tipo="entrada",
                cantidad=float(det.cantidad),
                motivo="Recepción de compra",
                referencia=compra.numero,
                saldo=float(stock.existencias),
            )
        )
    compra.estado = "recibida"


# ---------- Órdenes de compra ----------
@router.post("/ordenes", response_model=OrdenCompraOut, status_code=201)
def crear_orden(
    data: OrdenCompraCreate,
    db: Session = Depends(get_db),
):
    if not db.get(Proveedor, data.proveedor_id):
        raise HTTPException(400, "Proveedor no existe")
    orden = OrdenCompra(
        empresa_id=data.empresa_id,
        sucursal_id=data.sucursal_id,
        proveedor_id=data.proveedor_id,
        estado="solicitada",
        fecha_requerida=data.fecha_requerida,
        notas=data.notas,
        total_estimado=sum(d.cantidad * d.costo_unitario for d in data.detalle),
    )
    db.add(orden)
    db.flush()
    orden.numero = f"OC-{orden.id:06d}"
    for d in data.detalle:
        if not db.get(Producto, d.producto_id):
            raise HTTPException(400, f"Producto {d.producto_id} no existe")
        db.add(
            OrdenCompraDetalle(
                orden_id=orden.id,
                producto_id=d.producto_id,
                cantidad=d.cantidad,
                costo_unitario=d.costo_unitario,
            )
        )
    db.commit()
    db.refresh(orden)
    return orden


@router.get("/ordenes", response_model=list[OrdenCompraOut])
def listar_ordenes(
    estado: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(OrdenCompra)
    if estado:
        q = q.filter(OrdenCompra.estado == estado)
    return q.order_by(OrdenCompra.id.desc()).all()


@router.post("/ordenes/{orden_id}/aprobar")
def aprobar_orden(orden_id: int, db: Session = Depends(get_db)):
    orden = db.get(OrdenCompra, orden_id)
    if not orden:
        raise HTTPException(404, "Orden no encontrada")
    orden.estado = "aprobada"
    db.commit()
    return {"ok": True, "estado": orden.estado}


@router.post("/ordenes/{orden_id}/cancelar")
def cancelar_orden(orden_id: int, db: Session = Depends(get_db)):
    orden = db.get(OrdenCompra, orden_id)
    if not orden:
        raise HTTPException(404, "Orden no encontrada")
    orden.estado = "cancelada"
    db.commit()
    return {"ok": True, "estado": orden.estado}


@router.post("/ordenes/{orden_id}/recibir", response_model=CompraOut)
def recibir_orden(
    orden_id: int,
    db: Session = Depends(get_db),
):
    orden = db.get(OrdenCompra, orden_id)
    if not orden:
        raise HTTPException(404, "Orden no encontrada")
    if orden.estado == "cancelada":
        raise HTTPException(400, "La orden está cancelada")
    compra = Compra(
        empresa_id=orden.empresa_id,
        sucursal_id=orden.sucursal_id,
        proveedor_id=orden.proveedor_id,
        orden_compra_id=orden.id,
        tipo="contado",
        estado="pendiente",
    )
    db.add(compra)
    db.flush()
    compra.numero = f"C-{compra.id:06d}"
    subtotal = 0.0
    for det in orden.detalle:
        costo_unit = float(det.costo_unitario or 0)
        line_sub = float(det.cantidad) * costo_unit
        subtotal += line_sub
        db.add(
            CompraDetalle(
                compra_id=compra.id,
                producto_id=det.producto_id,
                cantidad=det.cantidad,
                costo_unitario=costo_unit,
                subtotal=line_sub,
            )
        )
    compra.subtotal = subtotal
    compra.total = subtotal
    _recibir_mercancia(db, compra.id)
    orden.estado = "recibida"
    db.commit()
    db.refresh(compra)
    return compra


# ---------- Compras directas ----------
@router.post("", response_model=CompraOut, status_code=201)
def crear_compra(
    data: CompraCreate,
    db: Session = Depends(get_db),
):
    if not db.get(Proveedor, data.proveedor_id):
        raise HTTPException(400, "Proveedor no existe")
    if data.tipo not in ("contado", "credito"):
        raise HTTPException(400, "Tipo de compra inválido")
    compra = Compra(
        empresa_id=data.empresa_id,
        sucursal_id=data.sucursal_id,
        proveedor_id=data.proveedor_id,
        orden_compra_id=data.orden_compra_id,
        tipo=data.tipo,
        estado="pendiente",
        impuesto=0,
        otros_costos=data.otros_costos,
        nota=data.nota,
    )
    db.add(compra)
    db.flush()
    compra.numero = f"C-{compra.id:06d}"
    subtotal = 0.0
    impuesto_total = 0.0
    for det in data.detalle:
        producto = db.get(Producto, det.producto_id)
        if not producto:
            raise HTTPException(400, f"Producto {det.producto_id} no existe")
        costo_unit = float(det.costo_unitario)
        line_sub = float(det.cantidad) * costo_unit
        subtotal += line_sub
        impuesto_total += line_sub * float(producto.impuesto or 0) / 100
        db.add(
            CompraDetalle(
                compra_id=compra.id,
                producto_id=det.producto_id,
                cantidad=det.cantidad,
                costo_unitario=costo_unit,
                subtotal=line_sub,
            )
        )
    compra.subtotal = subtotal
    compra.impuesto = impuesto_total
    compra.total = subtotal + impuesto_total + float(data.otros_costos or 0)
    _recibir_mercancia(db, compra.id)
    if data.tipo == "credito":
        db.add(
            CuentaPagar(
                empresa_id=data.empresa_id,
                proveedor_id=data.proveedor_id,
                compra_id=compra.id,
                monto_total=compra.total,
                saldo=compra.total,
                estado="pendiente",
            )
        )
    db.commit()
    db.refresh(compra)
    return compra


@router.get("", response_model=list[CompraOut])
def listar_compras(
    proveedor_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Compra)
    if proveedor_id:
        q = q.filter(Compra.proveedor_id == proveedor_id)
    return q.order_by(Compra.id.desc()).all()


# ---------- Cuentas por pagar / abonos ----------
@router.get("/cuentas-pagar", response_model=list[CuentaPagarOut])
def listar_cuentas_pagar(
    proveedor_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(CuentaPagar)
    if proveedor_id:
        q = q.filter(CuentaPagar.proveedor_id == proveedor_id)
    return q.order_by(CuentaPagar.id.desc()).all()


@router.post("/cuentas-pagar/{cuenta_id}/abonos", response_model=AbonoProveedorOut, status_code=201)
def abonar_proveedor(
    cuenta_id: int,
    data: AbonoProveedorCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    cuenta = db.get(CuentaPagar, cuenta_id)
    if not cuenta:
        raise HTTPException(404, "Cuenta por pagar no encontrada")
    if data.monto <= 0:
        raise HTTPException(400, "Monto inválido")
    abono = AbonoProveedor(
        cuenta_id=cuenta.id,
        usuario_id=usuario.id,
        monto=data.monto,
        medio=data.medio,
        referencia=data.referencia,
        observacion=data.observacion,
    )
    cuenta.saldo = float(cuenta.saldo or 0) - data.monto
    if float(cuenta.saldo) <= 0:
        cuenta.saldo = 0
        cuenta.estado = "pagada"
    db.add(abono)
    db.commit()
    db.refresh(abono)
    return abono


# ---------- Estado de cuenta del proveedor ----------
@router.get("/estado-cuenta/{proveedor_id}")
def estado_cuenta_proveedor(
    proveedor_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    if not db.get(Proveedor, proveedor_id):
        raise HTTPException(404, "Proveedor no encontrado")
    compras = (
        db.query(Compra)
        .filter(Compra.proveedor_id == proveedor_id)
        .order_by(Compra.id.desc())
        .all()
    )
    cuentas = (
        db.query(CuentaPagar)
        .filter(CuentaPagar.proveedor_id == proveedor_id)
        .order_by(CuentaPagar.id.desc())
        .all()
    )
    abonos = (
        db.query(AbonoProveedor)
        .join(CuentaPagar, CuentaPagar.id == AbonoProveedor.cuenta_id)
        .filter(CuentaPagar.proveedor_id == proveedor_id)
        .all()
    )
    return {
        "proveedor_id": proveedor_id,
        "compras": [
            {"id": c.id, "numero": c.numero, "total": float(c.total or 0), "estado": c.estado, "fecha": str(c.created_at)}
            for c in compras
        ],
        "cuentas": [
            {"id": c.id, "compra_id": c.compra_id, "monto_total": float(c.monto_total or 0), "saldo": float(c.saldo or 0), "estado": c.estado}
            for c in cuentas
        ],
        "abonos": [
            {"id": a.id, "cuenta_id": a.cuenta_id, "monto": float(a.monto or 0), "medio": a.medio, "fecha": str(a.created_at)}
            for a in abonos
        ],
    }


# ---------- Devoluciones a proveedor ----------
@router.post("/devoluciones", response_model=DevolucionCompraOut, status_code=201)
def devolver_a_proveedor(
    data: DevolucionCompraCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    dev = DevolucionCompra(
        empresa_id=data.empresa_id,
        sucursal_id=data.sucursal_id,
        proveedor_id=data.proveedor_id,
        compra_id=data.compra_id,
        usuario_id=usuario.id,
        tipo=data.tipo,
        motivo=data.motivo,
        estado="aplicada",
    )
    db.add(dev)
    db.flush()
    dev.numero = f"DCP-{dev.id:06d}"

    total = 0.0
    for linea in data.detalle:
        stock = _obtener_stock(db, linea.producto_id, data.sucursal_id)
        if float(stock.existencias or 0) < linea.cantidad:
            raise HTTPException(400, f"Stock insuficiente para devolver el producto {linea.producto_id}")
        stock.existencias = float(stock.existencias or 0) - linea.cantidad
        stock.disponible = stock.existencias - float(stock.reservado or 0)

        costo = linea.costo_unitario if linea.costo_unitario is not None else float(db.get(Producto, linea.producto_id).costo or 0)
        line_total = costo * float(linea.cantidad)
        total += line_total

        db.add(
            MovimientoInventario(
                producto_id=linea.producto_id,
                sucursal_id=data.sucursal_id,
                tipo="salida",
                cantidad=-float(linea.cantidad),
                motivo=f"Devolución a proveedor {dev.numero}",
                referencia=dev.numero,
                lote=linea.lote,
                vencimiento=linea.vencimiento,
                saldo=float(stock.existencias),
                usuario_id=usuario.id,
            )
        )
        db.add(
            DevolucionCompraDetalle(
                devolucion_id=dev.id,
                producto_id=linea.producto_id,
                cantidad=linea.cantidad,
                costo_unitario=costo,
                lote=linea.lote,
                vencimiento=linea.vencimiento,
            )
        )

    dev.total_devolucion = total

    # Si hay cuenta por pagar, reducirla
    if data.compra_id:
        cuenta = (
            db.query(CuentaPagar)
            .filter_by(compra_id=data.compra_id)
            .first()
        )
        if cuenta:
            cuenta.saldo = max(0.0, float(cuenta.saldo or 0) - total)
            if float(cuenta.saldo) <= 0:
                cuenta.saldo = 0
                cuenta.estado = "pagada"

    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="compras",
            accion="devolucion",
            entidad="proveedor",
            entidad_id=data.proveedor_id,
            detalle=f"Devolución a proveedor {dev.numero} por {total}",
        )
    )
    db.commit()
    db.refresh(dev)
    return dev


@router.get("/devoluciones", response_model=list[DevolucionCompraOut])
def listar_devoluciones_proveedor(
    proveedor_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(DevolucionCompra)
    if proveedor_id:
        q = q.filter(DevolucionCompra.proveedor_id == proveedor_id)
    return q.order_by(DevolucionCompra.id.desc()).all()


# ---------- Cotizaciones de proveedor ----------
@router.post("/cotizaciones", response_model=CotizacionProveedorOut, status_code=201)
def crear_cotizacion(
    data: CotizacionProveedorCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    if not db.get(Proveedor, data.proveedor_id):
        raise HTTPException(400, "Proveedor no existe")
    cot = CotizacionProveedor(
        empresa_id=data.empresa_id,
        proveedor_id=data.proveedor_id,
        usuario_id=usuario.id,
        estado="solicitada",
        fecha_validez=data.fecha_validez,
        notas=data.notas,
    )
    db.add(cot)
    db.flush()
    cot.numero = f"CT-{cot.id:06d}"
    total = 0.0
    for linea in data.detalle:
        costo = linea.costo_unitario if linea.costo_unitario is not None else float(db.get(Producto, linea.producto_id).precio_compra or 0)
        total += costo * float(linea.cantidad)
        db.add(
            CotizacionProveedorDetalle(
                cotizacion_id=cot.id,
                producto_id=linea.producto_id,
                cantidad=linea.cantidad,
                costo_unitario=costo,
            )
        )
    cot.total_estimado = total
    db.commit()
    db.refresh(cot)
    return cot


@router.get("/cotizaciones", response_model=list[CotizacionProveedorOut])
def listar_cotizaciones(
    proveedor_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(CotizacionProveedor)
    if proveedor_id:
        q = q.filter(CotizacionProveedor.proveedor_id == proveedor_id)
    return q.order_by(CotizacionProveedor.id.desc()).all()


@router.post("/cotizaciones/{cotizacion_id}/aprobar")
def aprobar_cotizacion(
    cotizacion_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    cot = db.get(CotizacionProveedor, cotizacion_id)
    if not cot:
        raise HTTPException(404, "Cotización no encontrada")
    cot.estado = "aprobada"
    db.commit()
    return {"ok": True, "estado": cot.estado}


# ---------- Consulta de compra (debe ir después de rutas fijas) ----------
@router.get("/{compra_id}", response_model=CompraOut)
def obtener_compra(compra_id: int, db: Session = Depends(get_db)):
    compra = db.get(Compra, compra_id)
    if not compra:
        raise HTTPException(404, "Compra no encontrada")
    return compra