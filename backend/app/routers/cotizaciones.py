from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..deps import get_current_user
from ..models import AuditoriaLog
from ..schemas.cotizaciones import CotizacionIn, CotizacionClienteOut
from .ventas import crear_venta

router = APIRouter(prefix="/cotizaciones", tags=["cotizaciones"])


def _serie_cotizacion(c, usuario):
    detalle = []
    for d in c.detalle:
        detalle.append(
            {
                "id": d.id,
                "producto_id": d.producto_id,
                "producto": d.nombre,
                "cantidad": float(d.cantidad or 0),
                "precio_unitario": float(d.precio_unitario or 0),
                "descuento": float(d.descuento or 0),
                "impuesto_pct": float(d.impuesto_pct or 0),
                "subtotal": float(d.subtotal or 0),
            }
        )
    return {
        "id": c.id,
        "numero": c.numero,
        "cliente_nombre": c.cliente_nombre,
        "cliente_documento": c.cliente_documento,
        "cliente_telefono": c.cliente_telefono,
        "vence": c.vence.isoformat() if c.vence else None,
        "estado": c.estado,
        "subtotal": float(c.subtotal or 0),
        "descuento_global": float(c.descuento_global or 0),
        "impuesto": float(c.impuesto or 0),
        "total": float(c.total or 0),
        "venta_id": c.venta_id,
        "observaciones": c.observaciones,
        "creado_por": usuario.nombre if usuario else c.usuario_id,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "detalle": detalle,
    }


def _estado_real(c):
    if c.estado == "vigente" and c.vence and c.vence < date.today():
        return "vencida"
    return c.estado


@router.post("", response_model=CotizacionClienteOut, status_code=201)
def crear_cotizacion(
    data: CotizacionIn,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    from ..models import CotizacionCliente, CotizacionClienteDetalle, Producto

    if not data.detalle:
        raise HTTPException(400, "La cotización debe tener al menos un producto")

    subtotal = 0.0
    impuesto_total = 0.0
    lineas = []
    for item in data.detalle:
        if item.cantidad <= 0:
            raise HTTPException(400, "Las cantidades deben ser mayores a cero")
        producto = db.get(Producto, item.producto_id)
        if not producto:
            raise HTTPException(404, f"Producto {item.producto_id} no existe")
        precio = item.precio if item.precio is not None else float(producto.precio_venta or 0)
        if precio < 0:
            raise HTTPException(400, "El precio no puede ser negativo")
        line_subtotal = round(round(float(item.cantidad), 3) * float(precio), 2)
        pct_imp = float(producto.impuesto or 0)
        line_subtotal = round(line_subtotal - round(line_subtotal * float(item.descuento or 0) / 100, 2), 2)
        impuesto_total += round(line_subtotal * pct_imp / 100, 2)
        subtotal += line_subtotal
        lineas.append((producto, item, line_subtotal, pct_imp))

    descuento_global = round(subtotal * float(data.descuento_global or 0) / 100, 2)
    total = round(subtotal - descuento_global + impuesto_total, 2)

    vence = None
    if data.vence:
        try:
            vence = date.fromisoformat(str(data.vence)[:10])
        except ValueError:
            raise HTTPException(400, "Fecha de vencimiento inválida")

    cotizacion = CotizacionCliente(
        empresa_id=data.empresa_id,
        sucursal_id=data.sucursal_id,
        usuario_id=usuario.id,
        cliente_id=data.cliente_id,
        cliente_nombre=data.cliente_nombre,
        cliente_documento=data.cliente_documento,
        cliente_telefono=data.cliente_telefono,
        vence=vence,
        estado="vigente",
        observaciones=data.observaciones,
        subtotal=round(subtotal, 2),
        descuento_global=descuento_global,
        impuesto=round(impuesto_total, 2),
        total=total,
    )
    db.add(cotizacion)
    db.flush()
    cotizacion.numero = f"COT-{cotizacion.id:06d}"
    for producto, item, line_subtotal, pct_imp in lineas:
        db.add(
            CotizacionClienteDetalle(
                cotizacion_id=cotizacion.id,
                producto_id=producto.id,
                nombre=producto.nombre,
                precio_unitario=float(item.precio if item.precio is not None else (producto.precio_venta or 0)),
                cantidad=float(item.cantidad),
                descuento=float(item.descuento or 0),
                impuesto_pct=float(pct_imp),
                subtotal=line_subtotal,
            )
        )
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="ventas",
            accion="crear-cotizacion",
            entidad="cotizaciones",
            detalle=f"Cotización {cotizacion.numero} por {total:,.2f}",
        )
    )
    db.commit()
    db.refresh(cotizacion)
    return _serie_cotizacion(cotizacion, usuario)


@router.get("", response_model=list[CotizacionClienteOut])
def listar_cotizaciones(
    estado: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    from ..models import CotizacionCliente

    query = db.query(CotizacionCliente).options(joinedload(CotizacionCliente.detalle))
    if usuario.empresa_id:
        query = query.filter(CotizacionCliente.empresa_id == usuario.empresa_id)
    if estado:
        if estado == "vencida":
            query = query.filter(
                or_(
                    CotizacionCliente.estado == "vencida",
                    and_(
                        CotizacionCliente.estado == "vigente",
                        CotizacionCliente.vence < date.today(),
                    ),
                )
            )
        else:
            query = query.filter(CotizacionCliente.estado == estado)
    rows = query.order_by(CotizacionCliente.id.desc()).limit(200).all()
    out = []
    for c in rows:
        real = _estado_real(c)
        if real != c.estado:
            c.estado = real
            db.add(c)
            db.commit()
        if q:
            texto = f"{c.numero} {c.cliente_nombre or ''} {c.cliente_documento or ''}"
            if q.lower() not in texto.lower():
                continue
        out.append(_serie_cotizacion(c, None))
    return out


@router.get("/{cotizacion_id}", response_model=CotizacionClienteOut)
def obtener_cotizacion(
    cotizacion_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    from ..models import CotizacionCliente

    c = db.query(CotizacionCliente).options(joinedload(CotizacionCliente.detalle)).get(cotizacion_id)
    if not c:
        raise HTTPException(404, "Cotización no encontrada")
    return _serie_cotizacion(c, None)


@router.post("/{cotizacion_id}/anular")
def anular_cotizacion(
    cotizacion_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    from ..models import CotizacionCliente

    c = db.get(CotizacionCliente, cotizacion_id)
    if not c:
        raise HTTPException(404, "Cotización no encontrada")
    if c.estado == "convertida":
        raise HTTPException(400, "Una cotización convertida en venta no puede anularse")
    if c.estado == "anulada":
        raise HTTPException(400, "La cotización ya está anulada")
    c.estado = "anulada"
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="ventas",
            accion="anular-cotizacion",
            entidad="cotizaciones",
            detalle=f"Cotización {c.numero} anulada",
        )
    )
    db.commit()
    return {"ok": True, "estado": c.estado}


@router.post("/{cotizacion_id}/convertir")
def convertir_cotizacion(
    cotizacion_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    """Convierte la cotización en una venta real (descuenta inventario)."""
    from ..schemas.ventas import VentaCreate, VentaDetalleCreate, VentaPagoCreate
    from ..models import CotizacionCliente

    c = db.get(CotizacionCliente, cotizacion_id)
    if not c:
        raise HTTPException(404, "Cotización no encontrada")
    if c.estado == "anulada":
        raise HTTPException(400, "La cotización está anulada")
    if c.estado == "convertida":
        raise HTTPException(400, "La cotización ya fue convertida")

    items = []
    for d in c.detalle:
        items.append(
            VentaDetalleCreate(
                producto_id=d.producto_id,
                cantidad=d.cantidad,
                precio=d.precio_unitario,
                descuento=d.descuento,
            )
        )
    data_cot = (
        VentaCreate(
            empresa_id=c.empresa_id,
            sucursal_id=c.sucursal_id,
            cliente_id=c.cliente_id,
            tipo="contado",
            descuento_global=0,
            nota=f"Cotización {c.numero}",
            detalle=items,
            pagos=[VentaPagoCreate(medio="efectivo", monto=c.total)],
        )
        if items
        else None
    )
    if not data_cot:
        raise HTTPException(400, "La cotización no tiene productos")

    venta = crear_venta(data=data_cot, db=db, usuario=usuario)
    c.estado = "convertida"
    c.venta_id = venta.id
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="ventas",
            accion="convertir-cotizacion",
            entidad="cotizaciones",
            detalle=f"Cotización {c.numero} convertida en {venta.numero}",
        )
    )
    db.commit()
    return {
        "ok": True,
        "cotizacion_id": c.id,
        "venta_id": venta.id,
        "numero_venta": venta.numero,
        "total": float(venta.total or 0),
    }