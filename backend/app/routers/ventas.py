import json
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_permiso, tiene_permiso
from ..seguridad import solicitar_autorizacion
from ..promos import calcular_promociones
from ..models import (
    AuditoriaLog,
    AperturaCaja,
    ArqueoCaja,
    Caja,
    Cliente,
    Configuracion,
    DocumentoFiscal,
    Empresa,
    Gasto,
    MovimientoCaja,
    Producto,
    PuntoVenta,
    ResolucionFacturacion,
    Stock,
    Sucursal,
    Usuario,
    Venta,
    VentaDetalle,
    VentaPago,
)
from ..schemas.ventas import (
    AbonoVentaIn,
    AperturaCajaCreate,
    AperturaCajaOut,
    GastoCreate,
    GastoOut,
    MovimientoCajaCreate,
    MovimientoCajaOut,
    VentaCreate,
    VentaOut,
)

router = APIRouter(prefix="/ventas", tags=["ventas"])


@router.post("", response_model=VentaOut, status_code=201)
def crear_venta(
    data: VentaCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    if data.tipo not in ("contado", "credito"):
        raise HTTPException(400, "Tipo de venta inválido")

    # Restricciones por sucursal y caja (351/352)
    if data.caja_id:
        caja = db.get(Caja, data.caja_id)
        if not caja:
            raise HTTPException(400, "Caja no existe")
        pv = db.get(PuntoVenta, caja.punto_venta_id)
        if pv and pv.sucursal_id != data.sucursal_id:
            raise HTTPException(400, "La caja no pertenece a la sucursal indicada")
    if usuario.sucursal_id and usuario.sucursal_id != data.sucursal_id:
        raise HTTPException(403, f"El usuario solo puede operar en la sucursal {usuario.sucursal_id}")

    institucional = False
    if data.cliente_id:
        cliente_precio = db.get(Cliente, data.cliente_id)
        institucional = bool(cliente_precio and cliente_precio.tipo == "institucional")

    def _precio_efectivo(producto, precio_ingresado):
        if precio_ingresado is not None:
            return precio_ingresado
        if institucional:
            return float(producto.precio_institucional or 0) or float(producto.precio_venta or 0)
        return float(producto.precio_venta or 0)

    subtotal = 0.0
    impuesto_total = 0.0
    costo_total = 0.0
    lineas = []
    lineas_compuestas = []
    for item in data.detalle:
        producto = db.get(Producto, item.producto_id)
        if not producto or not producto.activo:
            raise HTTPException(400, f"Producto {item.producto_id} no existe o inactivo")
        precio = _precio_efectivo(producto, item.precio)
        if producto.bloquear_venta_bajo_costo and precio < float(producto.costo or 0):
            raise HTTPException(400, f"Precio bajo para venta de {producto.nombre}: bloquea venta bajo costo")
        if float(producto.margen_minimo or 0) > 0:
            minimo = float(producto.costo or 0) * (1 + float(producto.margen_minimo) / 100)
            if precio < minimo:
                raise HTTPException(400, f"{producto.nombre}: precio por debajo del margen mínimo ({producto.margen_minimo}%)")
        line_subtotal = precio * item.cantidad - item.descuento
        impuesto_total += line_subtotal * float(producto.impuesto or 0) / 100
        lineas.append({"producto_id": item.producto_id, "cantidad": item.cantidad, "precio": precio})
        if producto.es_compuesto:
            lineas_compuestas.append((producto, item.cantidad))

        stock = (
            db.query(Stock)
            .filter_by(producto_id=item.producto_id, sucursal_id=data.sucursal_id)
            .first()
        )
        if stock and not producto.es_servicio:
            permitir_negativo = (
                db.query(Configuracion)
                .filter(Configuracion.clave == "pos.inventario_negativo")
                .first()
            )
            if float(stock.existencias or 0) < item.cantidad:
                if not (
                    permitir_negativo
                    and str(permitir_negativo.valor or "").strip().lower() in ("1", "true", "si", "sí", "on")
                ):
                    raise HTTPException(400, f"Stock insuficiente para {producto.nombre}")
            stock.existencias = float(stock.existencias or 0) - item.cantidad
            stock.disponible = stock.existencias - float(stock.reservado or 0)

        subtotal += line_subtotal
        costo_total += float(producto.costo or 0) * item.cantidad

    promo_descuento = calcular_promociones(db, lineas, cliente_id=data.cliente_id)
    from ..fidelizacion import aplicar_cupon, consumir_pago_fidelidad

    cupon_descuento = aplicar_cupon(db, usuario, data.cupon_codigo, data.cliente_id, subtotal)
    descuento_global = min(data.descuento_global + promo_descuento + cupon_descuento, subtotal)



    umbral = db.query(Configuracion).filter(Configuracion.clave == "descuento_maximo_sin_autorizacion").first()
    if (
        umbral
        and umbral.valor
        and data.descuento_global > float(umbral.valor)
        and not tiene_permiso(db, usuario, "ventas", "descuento")
    ):
        solicitar_autorizacion(
            db, usuario, "ventas", "descuento",
            entidad="venta", datos={"descuento_global": data.descuento_global, "subtotal": subtotal},
        )
        raise HTTPException(403, f"Descuento requiere autorización (máx. {umbral.valor})")

    total = subtotal - descuento_global + impuesto_total + float(data.propina or 0)
    monto_pagado = sum(p.monto for p in data.pagos)

    if data.tipo == "credito":
        if not data.cliente_id:
            raise HTTPException(400, "Venta a crédito requiere cliente")
        cliente = db.get(Cliente, data.cliente_id)
        nuevo_credito = float(cliente.creditos or 0) + total
        if cliente.limite_credito and nuevo_credito > float(cliente.limite_credito):
            raise HTTPException(400, "Cliente excede límite de crédito")
        cliente.creditos = nuevo_credito
    elif data.tipo == "contado" and monto_pagado + 1e-9 < total:
        raise HTTPException(400, "El monto pagado es menor al total")

    for p in data.pagos:
        consumir_pago_fidelidad(db, data.cliente_id, p.medio, p.referencia, p.monto)

    venta = Venta(
        empresa_id=data.empresa_id,
        sucursal_id=data.sucursal_id,
        caja_id=data.caja_id,
        punto_venta_id=data.punto_venta_id,
        usuario_id=usuario.id,
        cliente_id=data.cliente_id,
        tipo=data.tipo,
        subtotal=subtotal,
        descuento=descuento_global,
        impuesto=impuesto_total,
        total=total,
        costo_total=costo_total,
        propina=data.propina,
        saldo=total if data.tipo == "credito" else 0,
        nota=(data.nota or "") + (f" [promo: {promo_descuento:.0f}]" if promo_descuento else ""),
    )
    db.add(venta)
    db.flush()
    venta.numero = f"V-{venta.id:06d}"

    # Consumo de materias primas al vender combos/kits (si está habilitado)
    if lineas_compuestas:
        flag = db.query(Configuracion).filter(Configuracion.clave == "pos.combos_consumen").first()
        if flag and flag.valor in ("1", "true", "True", "si", "si"):
            from ..routers.recetas import consumir_lineas_combo

            consumir_lineas_combo(db, lineas_compuestas, data.sucursal_id, venta.numero, usuario)

    for item in data.detalle:
        producto = db.get(Producto, item.producto_id)
        precio = _precio_efectivo(producto, item.precio)
        line_base = precio * item.cantidad - item.descuento
        line_imp = line_base * float(producto.impuesto or 0) / 100
        db.add(
            VentaDetalle(
                venta_id=venta.id,
                producto_id=item.producto_id,
                cantidad=item.cantidad,
                precio=precio,
                costo=float(producto.costo or 0),
                descuento=item.descuento,
                impuesto=line_imp,
                subtotal=line_base,
                lote=item.lote,
                vencimiento=item.vencimiento,
            )
        )

    for p in data.pagos:
        db.add(
            VentaPago(
                venta_id=venta.id,
                medio=p.medio,
                monto=p.monto,
                referencia=p.referencia,
            )
        )

    db.commit()
    db.refresh(venta)
    from ..routers.integraciones import enviar_webhook

    enviar_webhook(
        db,
        "venta.creada",
        {
            "venta_id": venta.id,
            "numero": venta.numero,
            "sucursal_id": venta.sucursal_id,
            "caja_id": venta.caja_id,
            "cliente_id": venta.cliente_id,
            "total": float(venta.total or 0),
            "created_at": str(venta.created_at),
        },
    )
    from ..fidelizacion import acumular_puntos

    acumular_puntos(db, data.cliente_id, total, usuario_id=usuario.id, motivo=f"Venta {venta.numero}")
    try:
        from ..dian import emitir_documento

        activa = db.query(ResolucionFacturacion).filter_by(
            empresa_id=data.empresa_id, tipo_documento="factura", activa=True
        ).first()
        if activa:
            documentofiscal = emitir_documento(db, venta, usuario, tipo_documento="factura")
            venta.nota = (venta.nota or "") + f" [FE: {documentofiscal.numero}]"
            db.commit()
    except Exception:
        db.rollback()
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="ventas",
            accion="crear",
            entidad="venta",
            entidad_id=venta.id,
            detalle=f"Venta {venta.numero} creada por {usuario.username} por {total}",
        )
    )
    db.commit()
    from ..wa import lanzar_recibo_si_configurado

    lanzar_recibo_si_configurado(db, venta)
    return venta


@router.post("/{venta_id}/anular")
def anular_venta(
    venta_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    from ..seguridad import requiere_autorizacion

    venta = db.get(Venta, venta_id)
    if not venta:
        raise HTTPException(404, "Venta no encontrada")
    if venta.estado not in ("completada", "suspendida"):
        raise HTTPException(400, "La venta no se puede anular")
    requiere_autorizacion(
        db, usuario, "ventas", "anular",
        entidad="venta", entidad_id=venta.id,
        datos={"venta": venta.numero, "total": float(venta.total or 0)},
    )
    venta.estado = "anulada"
    if venta.tipo == "credito" and venta.cliente_id:
        cliente = db.get(Cliente, venta.cliente_id)
        if cliente:
            cliente.creditos = max(0.0, float(cliente.creditos or 0) - float(venta.saldo or 0))
    venta.saldo = 0
    # Reversión completa: reponer inventario y anular documentos fiscales emitidos
    for linea in venta.detalle:
        stock = (
            db.query(Stock)
            .filter_by(producto_id=linea.producto_id, sucursal_id=venta.sucursal_id)
            .first()
        )
        if stock:
            stock.existencias = float(stock.existencias or 0) + float(linea.cantidad or 0)
            stock.disponible = stock.existencias - float(stock.reservado or 0)

    docs = (
        db.query(DocumentoFiscal)
        .filter(DocumentoFiscal.venta_id == venta.id, DocumentoFiscal.anulado == False)
        .all()
    )
    for d in docs:
        d.anulado = True
        d.motivo_anulacion = "Venta anulada"
        db.add(
            AuditoriaLog(
                usuario_id=usuario.id,
                modulo="facturacion",
                accion="anular",
                entidad="documento_fiscal",
                entidad_id=d.id,
                detalle=f"Documento {d.numero} anulado por anulación de la venta {venta.numero}",
            )
        )
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="ventas",
            accion="anular",
            entidad="venta",
            entidad_id=venta.id,
            detalle=f"Venta {venta.numero} anulada por {usuario.username}",
        )
    )
    db.commit()
    return {"ok": True, "estado": venta.estado}


@router.post("/{venta_id}/suspender")
def suspender_venta(
    venta_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    venta = db.get(Venta, venta_id)
    if not venta or venta.estado != "completada":
        raise HTTPException(400, "La venta no se puede suspender")
    venta.estado = "suspendida"
    db.commit()
    return {"ok": True, "estado": venta.estado}


@router.post("/{venta_id}/reanudar")
def reanudar_venta(
    venta_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    venta = db.get(Venta, venta_id)
    if not venta or venta.estado != "suspendida":
        raise HTTPException(400, "La venta no se puede reanudar")
    venta.estado = "completada"
    db.commit()
    return {"ok": True, "estado": venta.estado}


class NotaDebitoIn(BaseModel):
    monto: float
    concepto: str | None = None


@router.post("/{venta_id}/nota-debito")
def nota_debito(
    venta_id: int,
    data: NotaDebitoIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    venta = db.get(Venta, venta_id)
    if not venta or venta.estado != "completada":
        raise HTTPException(400, "Venta no válida")
    if data.monto <= 0:
        raise HTTPException(400, "Monto inválido")
    venta.total = float(venta.total or 0) + data.monto
    if venta.tipo == "credito":
        venta.saldo = float(venta.saldo or 0) + data.monto
        if venta.cliente_id:
            cliente = db.get(Cliente, venta.cliente_id)
            if cliente:
                cliente.creditos = float(cliente.creditos or 0) + data.monto
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="ventas",
            accion="nota-debito",
            entidad="venta",
            entidad_id=venta.id,
            detalle=f"Nota débito {data.monto} a {venta.numero} ({data.concepto or 'sin concepto'})",
        )
    )
    db.commit()
    return {"ok": True, "total": float(venta.total), "saldo": float(venta.saldo or 0)}


@router.post("/{venta_id}/pagos", status_code=201)
def registrar_pago_parcial(
    venta_id: int,
    data: AbonoVentaIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    venta = db.get(Venta, venta_id)
    if not venta or venta.estado != "completada":
        raise HTTPException(400, "Venta no válida para abonos")
    saldo = float(venta.saldo or 0)
    if saldo <= 0:
        raise HTTPException(400, "La venta no tiene saldo pendiente")
    if data.monto <= 0:
        raise HTTPException(400, "Monto de abono inválido")
    if data.monto - saldo > 1e-9:
        raise HTTPException(400, f"El abono supera el saldo pendiente ({saldo:.0f})")
    venta.saldo = saldo - data.monto
    db.add(
        VentaPago(
            venta_id=venta.id,
            medio=data.medio,
            monto=data.monto,
            referencia=data.referencia,
        )
    )
    if venta.cliente_id:
        cliente = db.get(Cliente, venta.cliente_id)
        if cliente:
            cliente.creditos = max(0.0, float(cliente.creditos or 0) - data.monto)
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="ventas",
            accion="pago-parcial",
            entidad="venta",
            entidad_id=venta.id,
            detalle=f"Abono {data.monto} a {venta.numero} ({data.medio})",
        )
    )
    db.commit()
    return {"ok": True, "venta_id": venta.id, "saldo": float(venta.saldo or 0)}


@router.get("", response_model=list[VentaOut])
def listar_ventas(
    sucursal_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Venta)
    if sucursal_id:
        query = query.filter(Venta.sucursal_id == sucursal_id)
    return query.order_by(Venta.id.desc()).limit(100).all()


@router.get("/{venta_id}/tirilla", response_class=HTMLResponse)
def tirilla_venta(
    venta_id: int,
    print: bool = True,
    recibido: float | None = Query(default=None),
    cambio: float | None = Query(default=None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Tirilla de venta al consumidor (estilo D1/Frisby, 72-80mm).

    Funciona siempre, haya o no factura electrónica. Si la venta fue
    facturada, incluye el bloque fiscal (QR + CUFE). Permite mostrar el
    efectivo recibido y la vuelta mediante los parámetros opcionales.
    """
    venta = obtener_venta_publica(db, venta_id)
    if venta.empresa_id != usuario.empresa_id:
        raise HTTPException(404, "Venta no encontrada")
    return tirilla_html(db, venta, print=print, recibido=recibido, cambio=cambio)


def obtener_venta_publica(db: Session, venta_id: int) -> Venta:
    venta = db.get(Venta, venta_id)
    if not venta:
        raise HTTPException(404, "Venta no encontrada")
    if venta.estado == "anulada":
        raise HTTPException(400, "La venta está anulada")
    return venta


def tirilla_html(
    db: Session,
    venta: Venta,
    print: bool = True,
    recibido: float | None = None,
    cambio: float | None = None,
):
    """HTML de la tirilla (72-80mm) que también usan el kiosko y la red pública."""
    import datetime

    empresa = db.get(Empresa, venta.empresa_id) if venta.empresa_id else None
    sucursal = db.get(Sucursal, venta.sucursal_id) if venta.sucursal_id else None
    caja = db.get(Caja, venta.caja_id) if venta.caja_id else None
    pv = db.get(PuntoVenta, caja.punto_venta_id) if caja and caja.punto_venta_id else None
    cajero = db.get(Usuario, venta.usuario_id) if venta.usuario_id else None
    cliente = db.get(Cliente, venta.cliente_id) if venta.cliente_id else None

    docs = (
        db.query(DocumentoFiscal)
        .filter(DocumentoFiscal.venta_id == venta.id, DocumentoFiscal.anulado == False)
        .order_by(DocumentoFiscal.id)
        .all()
    )
    doc = next((d for d in docs if d.tipo_documento == "factura"), docs[0] if docs else None)
    resinfo = db.get(ResolucionFacturacion, doc.resolucion_id) if doc and doc.resolucion_id else None

    total = float(venta.total or 0)
    subtotal = float(venta.subtotal or 0)
    descuento = float(venta.descuento or 0)
    impuesto = float(venta.impuesto or 0)
    propina = float(venta.propina or 0)
    saldo = float(venta.saldo or 0)

    try:
        _fb = json.loads(
            (db.query(Configuracion).filter(Configuracion.clave == "pos.factura").first().valor or "{}")
        )
    except Exception:
        _fb = {}
    ancho_mm = int(_fb.get("ancho_mm") or 72)
    copias = max(1, int(_fb.get("copias") or 1))
    leyenda = escape((_fb.get("leyenda_pie") or "").strip())

    nombre = escape((empresa.razon_social or empresa.nombre or "Empresa") if empresa else "Empresa").upper()
    nit = escape(f"NIT {empresa.nit}") if empresa and getattr(empresa, "nit", None) else ""
    dir_tel = " · ".join(
        x
        for x in [
            (sucursal.direccion or (empresa.direccion if empresa else None) or ""),
            (sucursal.telefono or (empresa.telefono if empresa else None) or ""),
        ]
        if x
    )
    ubica = " · ".join(x for x in [(sucursal.nombre if sucursal else None), dir_tel] if x)

    fec_s = str(venta.created_at or datetime.datetime.now())
    fecha_s = escape(fec_s[:10]) if len(fec_s) >= 10 else ""
    hora_s = escape(fec_s[11:19]) if len(fec_s) > 11 else ""

    cliente_linea = "Consumidor final"
    if cliente:
        cliente_linea = escape(cliente.nombre or "Cliente")
        if getattr(cliente, "documento", None):
            cliente_linea += f" · {escape(str(cliente.tipo_documento or ''))} {escape(str(cliente.documento))}"

    suc_line = " · ".join(
        x for x in [
            (cajero.username if cajero else None),
            (pv.nombre if pv else None),
            (caja.nombre if caja else None),
        ] if x
    )

    items = []
    for d in db.query(VentaDetalle).filter(VentaDetalle.venta_id == venta.id).order_by(VentaDetalle.id).all():
        prod = db.get(Producto, d.producto_id)
        nm = escape(prod.nombre if prod else f"Producto {d.producto_id}").upper()
        items.append(
            f"<tr><td class='n'>{float(d.cantidad or 1):g}</td><td class='prod'>{nm}</td>"
            f"<td class='r'>{float(d.subtotal or 0):,.0f}</td></tr>"
        )
    items_html = "".join(items) or "<tr><td colspan='3'>—</td></tr>"

    pagos_html = ""
    for p in db.query(VentaPago).filter(VentaPago.venta_id == venta.id).order_by(VentaPago.id).all():
        pagos_html += (
            f"<tr class='pago'><td>{escape(str(p.medio)).upper()}</td>"
            f"<td class='r'>{float(p.monto or 0):,.0f}</td></tr>"
        )
        if p.referencia:
            pagos_html += (
                f"<tr class='ref'><td colspan='2' class='c'>REF: {escape(str(p.referencia))}</td></tr>"
            )
    if not pagos_html:
        pagos_html = "<tr><td colspan='2'>—</td></tr>"

    recibido_html = ""
    cambio_html = ""
    if (recibido or 0) > 0:
        recibido_html = (
            f"<tr class='pago'><td>RECIBIDO</td><td class='r'>{float(recibido):,.0f}</td></tr>"
        )
        if (cambio or 0) > 0:
            cambio_html = (
                f"<tr class='cambio'><td>CAMBIÓ</td><td class='r'>{float(cambio):,.0f}</td></tr>"
            )
    else:
        eff = sum(
            float(p.monto or 0)
            for p in db.query(VentaPago).filter_by(venta_id=venta.id, medio="efectivo").all()
        )
        cc = max(0.0, eff - total)
        if cc > 0:
            cambio_html = f"<tr class='cambio'><td>CAMBIÓ</td><td class='r'>{cc:,.0f}</td></tr>"

    totales_html = (
        f"<tr><td>SUBTOTAL</td><td class='r'>{subtotal:,.0f}</td></tr>"
        + (f"<tr><td>DESCUENTO</td><td class='r'>-{descuento:,.0f}</td></tr>" if descuento else "")
        + (f"<tr><td>IVA</td><td class='r'>{impuesto:,.0f}</td></tr>" if impuesto else "")
        + (f"<tr><td>PROPINA</td><td class='r'>{propina:,.0f}</td></tr>" if propina else "")
        + (
            f"<tr><td>SALDO PENDIENTE</td><td class='r'>{saldo:,.0f}</td></tr>"
            if venta.tipo == "credito" and saldo > 0
            else ""
        )
        + f"<tr class='total'><td>TOTAL</td><td class='r'>${total:,.0f}</td></tr>"
    )

    doc_line = ""
    if doc:
        doc_line = f"<div class='doc'>{escape(str(doc.numero))}</div>"

    dian_html = ""
    if doc:
        vig = (
            f"{resinfo.fecha_inicio} a {resinfo.fecha_vencimiento}"
            if resinfo and resinfo.fecha_inicio
            else "vigente"
        )
        dian_html = (
            "<div class='rule-d'></div>"
            + (f"<div class='qr'><img src='{doc.qr}' width='88' height='88' alt='QR'/></div>" if doc.qr else "")
            + f"<div class='small c'>CUFE: {escape(doc.cufe or '')}</div>"
            + (
                f"<div class='small c'>RES: {escape(str(resinfo.resolucion))} · VIG: {escape(vig)}"
                f" · RANGO: {resinfo.rango_inicial}-{resinfo.rango_final}</div>"
                if resinfo
                else ""
            )
            + f"<div class='small c'>DOCUMENTO: {escape(str(doc.numero))} · {escape(doc.tipo_documento.replace('_', ' ').upper())}</div>"
        )
    footer_pie = (
        "Comprobante de facturación electrónica de venta · Valide en el portal de la DIAN."
        if doc
        else "RECIBO DE VENTA · NO ES FACTURA ELECTRÓNICA"
    )

    cuerpo = f"""
<h1>{nombre}</h1>
{f'<div class="c">{nit}</div>' if nit else ''}
{f'<div class="c">{escape(ubica)}</div>' if ubica else ''}
<div class="rule"></div>
<div class="v">{escape(venta.numero)}</div>
{doc_line}
{f'<div class="c small">{fecha_s}   {hora_s}   {escape(suc_line)}</div>' if suc_line else f'<div class="c small">{fecha_s}   {hora_s}</div>'}
<div class="c">CLIENTE: {cliente_linea}</div>
{f'<div class="c small">VENTA A CRÉDITO · SALDO {saldo:,.0f}</div>' if venta.tipo == 'credito' and saldo > 0 else ''}
<div class="rule"></div>
<table class="items">
  <tr><th class="n">CANT</th><th>PRODUCTO</th><th class="r">VALOR</th></tr>
  {items_html}
</table>
<div class="rule-d"></div>
<table class="totales">
  {totales_html}
</table>
<div class="rule"></div>
<table class="pagos">
  {pagos_html}
  {recibido_html}
  {cambio_html}
</table>
{dian_html}
<div class="sep"></div>
<div class="pie thanks">¡GRACIAS POR SU COMPRA!</div>
<div class="pie small">{footer_pie}</div>
{f'<div class="pie small">{leyenda}</div>' if leyenda else ''}
"""
    autoload = "window.print();" if print else ""
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Venta {escape(venta.numero)}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Courier New', monospace; font-size: 12px; color: #000; }}
  .ticket {{ width: {ancho_mm}mm; margin: 0 auto; padding: 6mm 4mm; }}
  h1 {{ font-size: 14px; text-align: center; text-transform: uppercase; }}
  .c {{ text-align: center; }}
  .small {{ font-size: 8.5px; }}
  .v {{ text-align: center; font-weight: 700; font-size: 16px; margin: 1px 0; }}
  .doc {{ text-align: center; font-weight: 700; font-size: 12px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ font-size: 10px; text-align: left; }}
  td {{ padding: 1px 1px; vertical-align: top; }}
  .r {{ text-align: right; white-space: nowrap; }}
  .n {{ text-align: center; font-weight: 700; width: 1%; white-space: nowrap; }}
  .prod {{ padding-left: 2px; }}
  .rule {{ border-top: 1px solid #000; margin: 3px 0; }}
  .rule-d {{ border-top: 1px dashed #000; margin: 3px 0; }}
  .sep {{ border-top: 1px dashed #000; margin: 4px 0; }}
  .items tr {{ border-bottom: 1px dotted #000; }}
  .total td {{ font-size: 15px; font-weight: 700; border-top: 2px double #000; border-bottom: 2px double #000; padding: 3px 1px; }}
  .pago td {{ border-bottom: 1px dashed #000; }}
  .cambio td {{ font-weight: 700; }}
  .ref {{ font-size: 8.5px; }}
  .qr {{ text-align: center; margin: 3px 0; }}
  .pie {{ font-size: 9px; text-align: center; margin-top: 3px; }}
  .thanks {{ font-size: 11px; font-weight: 700; }}
  .noprint {{ display: block; text-align: center; margin: 8px auto; padding: 8px 16px; font-size: 14px; }}
  @media print {{ .noprint {{ display: none; }} body {{ font-size: 11px; }} }}
</style></head><body>
<div class="ticket">
{cuerpo * copias}
</div>
<button class="noprint" onclick="window.print()">Imprimir / Guardar PDF</button>
<script>{autoload}</script>
</body></html>"""


@router.post("/{venta_id}/whatsapp")
def enviar_whatsapp_venta(
    venta_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Reenvía el recibo de la venta por WhatsApp al teléfono del cliente."""
    from ..wa import enviar_whatsapp, texto_recibo_venta

    venta = obtener_venta_publica(db, venta_id)
    if venta.empresa_id != usuario.empresa_id:
        raise HTTPException(404, "Venta no encontrada")
    cliente = db.get(Cliente, venta.cliente_id) if venta.cliente_id else None
    tel = (cliente.telefono or "").strip() if cliente else ""
    if not tel:
        raise HTTPException(400, "La venta no tiene un cliente con teléfono registrado")
    msg = enviar_whatsapp(
        db,
        tel,
        texto_recibo_venta(db, venta),
        plantilla="recibo_venta",
        referencia=f"venta-{venta.id}",
        empresa_id=venta.empresa_id,
    )
    return {"ok": True, "id": msg.id, "telefono": msg.telefono, "plantilla": msg.plantilla}


@router.get("/{venta_id}")
def obtener_venta(venta_id: int, db: Session = Depends(get_db)):
    venta = db.get(Venta, venta_id)
    if not venta:
        raise HTTPException(404, "Venta no encontrada")
    return venta


class ParteDivision(BaseModel):
    cliente_id: int
    monto: float


class DivisionCuentaBody(BaseModel):
    partes: list[ParteDivision]


@router.post("/{venta_id}/dividir")
def dividir_cuenta(
    venta_id: int,
    data: DivisionCuentaBody,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Divide el saldo por cobrar de una venta entre varios clientes/a comensales.

    Cada parte genera un pago 'division' sobre la venta y se carga al crédito del cliente
    asignado. Devuelve el desglose por cliente.
    """
    venta = db.get(Venta, venta_id)
    if not venta:
        raise HTTPException(404, "Venta no encontrada")
    if not data.partes:
        raise HTTPException(400, "Debe indicar al menos una parte")
    saldo = float(venta.saldo or 0)
    if saldo <= 0:
        raise HTTPException(400, "La venta no tiene saldo pendiente por dividir")
    total_partes = round(sum(p.monto for p in data.partes), 2)
    if abs(total_partes - saldo) > 1:
        raise HTTPException(400, f"Las partes ({total_partes}) no suman el saldo ({saldo})")

    desglose = []
    for parte in data.partes:
        if parte.monto <= 0:
            raise HTTPException(400, "Los montos deben ser mayores que 0")
        cliente = db.get(Cliente, parte.cliente_id)
        if not cliente:
            raise HTTPException(404, f"Cliente {parte.cliente_id} no encontrado")
        cliente.creditos = float(cliente.creditos or 0) + parte.monto
        db.add(
            VentaPago(
                venta_id=venta.id,
                medio="division",
                monto=parte.monto,
                referencia=f"cliente-{parte.cliente_id}",
            )
        )
        desglose.append(
            {"cliente_id": parte.cliente_id, "cliente": cliente.nombre, "monto": parte.monto}
        )

    venta.saldo = 0
    venta.nota = (venta.nota or "") + f" [dividida en {len(data.partes)} cuentas]"
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="ventas",
            accion="dividir_cuenta",
            entidad="venta",
            entidad_id=venta.id,
            detalle=f"Dividida en {len(data.partes)} cuentas por {total_partes}",
        )
    )
    db.commit()
    return {"venta_id": venta.id, "numero": venta.numero, "partes": desglose}