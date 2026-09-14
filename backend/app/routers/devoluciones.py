from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_permiso
from ..models import (
    Cliente,
    DevolucionVenta,
    DevolucionVentaDetalle,
    Producto,
    Stock,
    Usuario,
    Venta,
    VentaDetalle,
    VentaPago,
)
from ..schemas.devoluciones import DevolucionCreate, DevolucionOut

router = APIRouter(prefix="/devoluciones", tags=["devoluciones"])


class CambioCreate(DevolucionCreate):
    reemplazo: list[dict] = []


@router.post("/cambio", status_code=201)
def cambio_productos(
    data: CambioCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Devolución + venta inmediata de los productos de reemplazo."""
    from ..seguridad import requiere_autorizacion

    requiere_autorizacion(
        db, usuario, "ventas", "devolucion",
        entidad="venta", datos={"motivo": data.motivo, "tipo": data.tipo},
    )

    dev = crear_devolucion(DevolucionCreate(**data.model_dump(exclude={"reemplazo"})), db, usuario)

    if not data.reemplazo:
        return {"devolucion": dev.numero_nota, "venta_nueva": None}

    # Venta de reemplazo pagada con el valor de la devolución
    from ..routers.ventas import crear_venta
    from ..schemas.ventas import VentaCreate, VentaDetalleCreate, VentaPagoCreate

    detalle = [VentaDetalleCreate(producto_id=d["producto_id"], cantidad=d["cantidad"]) for d in data.reemplazo]
    venta_origen = db.get(Venta, dev.venta_id)
    venta_nueva = crear_venta(
        VentaCreate(
            empresa_id=dev.empresa_id,
            sucursal_id=dev.sucursal_id,
            cliente_id=venta_origen.cliente_id if venta_origen else None,
            tipo="contado",
            detalle=detalle,
            pagos=[VentaPagoCreate(medio="nota_credito", monto=float(dev.total_devolucion or 0))],
            nota=f"Cambio por {dev.numero_nota}",
        ),
        db,
        usuario,
    )
    return {"devolucion": dev.numero_nota, "venta_nueva": venta_nueva.numero}


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


@router.post("", response_model=DevolucionOut, status_code=201)
def crear_devolucion(
    data: DevolucionCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    from ..seguridad import requiere_autorizacion

    venta = db.get(Venta, data.venta_id)
    if not venta:
        raise HTTPException(404, "Venta no encontrada")
    if venta.estado != "completada":
        raise HTTPException(400, "La venta no está completada")
    if data.tipo not in ("total", "parcial"):
        raise HTTPException(400, "Tipo de devolución inválido")
    requiere_autorizacion(
        db, usuario, "ventas", "devolucion",
        entidad="venta", entidad_id=venta.id,
        datos={"venta": venta.numero, "tipo": data.tipo, "motivo": data.motivo},
    )

    # Determinar líneas a devolver
    lineas = data.detalle if data.detalle else venta.detalle

    devolucion = DevolucionVenta(
        empresa_id=venta.empresa_id,
        sucursal_id=venta.sucursal_id,
        venta_id=venta.id,
        usuario_id=usuario.id,
        tipo=data.tipo,
        motivo=data.motivo,
        reembolso_medio=data.reembolso_medio,
        estado="aplicada",
    )
    db.add(devolucion)
    db.flush()
    devolucion.numero_nota = f"NC-{devolucion.id:06d}"

    total_dev = 0.0
    for linea in lineas:
        venta_linea = (
            db.query(VentaDetalle)
            .filter_by(venta_id=venta.id, producto_id=linea.producto_id)
            .first()
        )
        if not venta_linea:
            raise HTTPException(400, f"Producto {linea.producto_id} no está en la venta")
        if linea.cantidad > float(venta_linea.cantidad or 0):
            raise HTTPException(400, f"Cantidad mayor a la vendida para el producto {linea.producto_id}")

        precio = float(venta_linea.precio or 0)
        impuesto_unidad = float(venta_linea.impuesto or 0) / max(1, float(venta_linea.cantidad or 1))
        subtotal = (precio + impuesto_unidad) * float(linea.cantidad)
        total_dev += subtotal

        # Reintegrar inventario
        stock = _obtener_stock(db, linea.producto_id, venta.sucursal_id)
        stock.existencias = float(stock.existencias or 0) + float(linea.cantidad)
        stock.disponible = stock.existencias - float(stock.reservado or 0)

        from ..models import MovimientoInventario
        db.add(
            MovimientoInventario(
                producto_id=linea.producto_id,
                sucursal_id=venta.sucursal_id,
                tipo="entrada",
                cantidad=float(linea.cantidad),
                motivo=f"Devolución de venta {venta.numero}",
                referencia=devolucion.numero_nota,
                saldo=float(stock.existencias),
            )
        )
        db.add(
            DevolucionVentaDetalle(
                devolucion_id=devolucion.id,
                producto_id=linea.producto_id,
                cantidad=linea.cantidad,
                precio=precio,
                subtotal=subtotal,
            )
        )

    devolucion.total_devolucion = total_dev

    # Ajustar crédito si aplica
    if venta.tipo == "credito" and venta.cliente_id:
        reembolso = min(total_dev, float(venta.saldo or 0))
        venta.saldo = float(venta.saldo or 0) - reembolso
        cliente = db.get(Cliente, venta.cliente_id)
        if cliente:
            cliente.creditos = max(0.0, float(cliente.creditos or 0) - reembolso)

    if data.tipo == "total":
        venta.estado = "anulada"
        for pago in venta.pagos:
            pago.monto = float(pago.monto or 0) - total_dev

    db.commit()
    db.refresh(devolucion)
    return devolucion


@router.get("", response_model=list[DevolucionOut])
def listar_devoluciones(db: Session = Depends(get_db)):
    return db.query(DevolucionVenta).order_by(DevolucionVenta.id.desc()).all()


@router.get("/{devolucion_id}", response_model=DevolucionOut)
def obtener_devolucion(devolucion_id: int, db: Session = Depends(get_db)):
    dev = db.get(DevolucionVenta, devolucion_id)
    if not dev:
        raise HTTPException(404, "Devolución no encontrada")
    return dev