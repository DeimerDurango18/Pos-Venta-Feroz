from datetime import datetime
from html import escape
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..dian import (
    TIPO_LABEL,
    _desglose_iva,
    consultar_estado_dian,
    estado_integracion_dian,
    emitir_documento,
    generar_pdf,
    generar_ubl_xml,
    transmitir_documento,
)
from ..models import (
    AuditoriaLog,
    Cliente,
    Configuracion,
    DocumentoFiscal,
    Empresa,
    Producto,
    ResolucionFacturacion,
    Sucursal,
    Usuario,
    Venta,
    VentaDetalle,
    VentaPago,
)
from ..schemas.facturacion import (
    DocumentoFiscalOut,
    GenerarDocumentoIn,
    ResolucionCreate,
    ResolucionOut,
)

router = APIRouter(prefix="/facturacion", tags=["facturacion"])


@router.get("/integracion/estado")
def obtener_estado_integracion(usuario: Usuario = Depends(get_current_user)):
    """Estado seguro de la integración; no revela certificados ni credenciales."""
    return estado_integracion_dian()


# ---------- Resoluciones de facturación (191-194) ----------

@router.get("/resoluciones", response_model=list[ResolucionOut])
def listar_resoluciones(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    return db.query(ResolucionFacturacion).filter_by(empresa_id=usuario.empresa_id).order_by(ResolucionFacturacion.id).all()


@router.post("/resoluciones", response_model=ResolucionOut, status_code=201)
def crear_resolucion(
    data: ResolucionCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    if data.rango_final < data.rango_inicial:
        raise HTTPException(400, "Rango final debe ser mayor o igual al inicial")
    existe = db.query(ResolucionFacturacion).filter_by(empresa_id=usuario.empresa_id, prefijo=data.prefijo.upper()).first()
    if existe:
        raise HTTPException(400, f"El prefijo '{data.prefijo}' ya existe")
    res = ResolucionFacturacion(
        empresa_id=usuario.empresa_id,
        resolucion=data.resolucion,
        prefijo=data.prefijo.upper(),
        tipo_documento=data.tipo_documento,
        rango_inicial=data.rango_inicial,
        rango_final=data.rango_final,
        numero_actual=data.rango_inicial - 1,
        fecha_inicio=data.fecha_inicio,
        fecha_vencimiento=data.fecha_vencimiento,
        tecnica=data.tecnica,
        activa=True,
    )
    try:
        db.add(res)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(400, "No se pudo crear la resolución (prefijo duplicado?)")
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="facturacion",
            accion="crear-resolucion",
            entidad="resolucion_facturacion",
            entidad_id=res.id,
            detalle=f"Resolución {data.resolucion} prefijo {data.prefijo} ({data.tipo_documento})",
        )
    )
    db.commit()
    return res


@router.post("/resoluciones/{resolucion_id}/toggle", response_model=ResolucionOut)
def toggle_resolucion(
    resolucion_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    res = db.get(ResolucionFacturacion, resolucion_id)
    if not res or res.empresa_id != usuario.empresa_id:
        raise HTTPException(404, "Resolución no encontrada")
    res.activa = not bool(res.activa)
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="facturacion",
            accion="toggle-resolucion",
            entidad="resolucion_facturacion",
            entidad_id=res.id,
            detalle=f"Resolución {res.resolucion} {'activada' if res.activa else 'desactivada'}",
        )
    )
    db.commit()
    return res


# ---------- Emisión de documentos (185-190) ----------

@router.post("/generar/{venta_id}", response_model=DocumentoFiscalOut, status_code=201)
def generar_documento(
    venta_id: int,
    data: GenerarDocumentoIn | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    data = data or GenerarDocumentoIn()
    if data.tipo_documento not in TIPO_LABEL:
        raise HTTPException(400, "Tipo de documento inválido")
    venta = db.get(Venta, venta_id)
    if not venta or venta.empresa_id != usuario.empresa_id:
        raise HTTPException(404, "Venta no encontrada")
    if venta.estado != "completada":
        raise HTTPException(400, "La venta debe estar completada para facturarse")
    duplicado = (
        db.query(DocumentoFiscal)
        .filter(DocumentoFiscal.venta_id == venta.id, DocumentoFiscal.tipo_documento == data.tipo_documento)
        .first()
    )
    if duplicado and data.tipo_documento == "factura":
        raise HTTPException(400, f"La venta ya tiene una factura ({duplicado.numero})")
    doc = emitir_documento(
        db, venta, usuario,
        tipo_documento=data.tipo_documento,
        monto=data.monto,
        concepto=data.concepto,
        resolucion_id=data.resolucion_id,
    )
    return doc


@router.get("/documentos", response_model=list[DocumentoFiscalOut])
def listar_documentos(
    tipo_documento: str | None = None,
    estado: str | None = None,
    anulado: bool | None = None,
    q: str | None = None,
    venta_id: int | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    query = db.query(DocumentoFiscal).filter(DocumentoFiscal.empresa_id == usuario.empresa_id)
    if tipo_documento:
        query = query.filter(DocumentoFiscal.tipo_documento == tipo_documento)
    if estado:
        query = query.filter(DocumentoFiscal.estado_dian == estado)
    if anulado is not None:
        query = query.filter(DocumentoFiscal.anulado == anulado)
    if venta_id:
        query = query.filter(DocumentoFiscal.venta_id == venta_id)
    if q:
        query = query.filter(DocumentoFiscal.numero.ilike(f"%{q}%"))
    docs = query.order_by(DocumentoFiscal.id.desc()).limit(200).all()
    resultado = []
    for d in docs:
        cliente = ""
        if d.venta_id:
            venta = db.get(Venta, d.venta_id)
            if venta and venta.cliente_id:
                c = db.get(Cliente, venta.cliente_id)
                if c:
                    cliente = c.nombre
        resultado.append(
            DocumentoFiscalOut(
                id=d.id,
                venta_id=d.venta_id,
                resolucion_id=d.resolucion_id,
                referencia=d.referencia,
                tipo_documento=d.tipo_documento,
                prefijo=d.prefijo,
                consecutivo=d.consecutivo,
                numero=d.numero,
                fecha_emision=d.fecha_emision,
                cufe=d.cufe,
                estado_dian="anulado" if d.anulado else d.estado_dian,
                fecha_envio=d.fecha_envio,
                motivo_rechazo=d.motivo_rechazo,
                anulado=d.anulado,
                motivo_anulacion=d.motivo_anulacion,
                monto=d.monto,
                concepto=d.concepto,
                created_at=d.created_at,
                cliente=cliente,
                respuesta_dian=d.respuesta_dian,
            )
        )
    return resultado


@router.get("/documentos/{doc_id}", response_model=DocumentoFiscalOut)
def obtener_documento(
    doc_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    d = db.get(DocumentoFiscal, doc_id)
    if not d or d.empresa_id != usuario.empresa_id:
        raise HTTPException(404, "Documento no encontrado")
    cliente = ""
    if d.venta_id:
        venta = db.get(Venta, d.venta_id)
        if venta and venta.cliente_id:
            c = db.get(Cliente, venta.cliente_id)
            if c:
                cliente = c.nombre
    return DocumentoFiscalOut(
        id=d.id,
        venta_id=d.venta_id,
        resolucion_id=d.resolucion_id,
        referencia=d.referencia,
        tipo_documento=d.tipo_documento,
        prefijo=d.prefijo,
        consecutivo=d.consecutivo,
        numero=d.numero,
        fecha_emision=d.fecha_emision,
        cufe=d.cufe,
        estado_dian="anulado" if d.anulado else d.estado_dian,
        fecha_envio=d.fecha_envio,
        motivo_rechazo=d.motivo_rechazo,
        anulado=d.anulado,
        motivo_anulacion=d.motivo_anulacion,
        monto=d.monto,
        concepto=d.concepto,
        created_at=d.created_at,
        cliente=cliente,
        respuesta_dian=d.respuesta_dian,
    )


def _obtener_doc(db, doc_id, empresa_id=None):
    d = db.get(DocumentoFiscal, doc_id)
    if not d or (empresa_id is not None and d.empresa_id != empresa_id):
        raise HTTPException(404, "Documento no encontrado")
    return d


# ---------- Ciclo de vida ante la DIAN (195-199) ----------

@router.post("/{doc_id}/enviar", response_model=DocumentoFiscalOut)
def enviar_documento(
    doc_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    d = _obtener_doc(db, doc_id, usuario.empresa_id)
    if d.anulado:
        raise HTTPException(400, "El documento está anulado")
    d = transmitir_documento(db, d, usuario)
    return obtener_documento(doc_id, db, usuario)


@router.post("/{doc_id}/consultar", response_model=DocumentoFiscalOut)
def consultar_documento(
    doc_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Consulta el estado del documento ante DIAN (simulado o conector real)."""
    d = _obtener_doc(db, doc_id, usuario.empresa_id)
    d = consultar_estado_dian(db, d, usuario)
    return obtener_documento(doc_id, db, usuario)


@router.post("/{doc_id}/rechazar", response_model=DocumentoFiscalOut)
def rechazar_documento(
    doc_id: int,
    motivo: str = "Validación fallida (simulación DIAN)",
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Simula un rechazo de la DIAN (para ejercitar el reintento)."""
    d = _obtener_doc(db, doc_id, usuario.empresa_id)
    if d.anulado:
        raise HTTPException(400, "El documento está anulado")
    d.estado_dian = "rechazado"
    d.motivo_rechazo = motivo
    d.respuesta_dian = f"Documento rechazado: {motivo}"
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="facturacion",
            accion="rechazar",
            entidad="documento_fiscal",
            entidad_id=d.id,
            detalle=f"Documento {d.numero} rechazado: {motivo}",
        )
    )
    db.commit()
    return obtener_documento(doc_id, db, usuario)


@router.post("/{doc_id}/reintentar", response_model=DocumentoFiscalOut)
def reintentar_documento(
    doc_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    d = _obtener_doc(db, doc_id, usuario.empresa_id)
    if d.estado_dian != "rechazado" or d.anulado:
        raise HTTPException(400, "Solo se pueden reintentar documentos rechazados")
    d.estado_dian = "enviado"
    d.fecha_envio = datetime.now()
    d.motivo_rechazo = None
    d.respuesta_dian = "Reintento de transmisión a la DIAN."
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="facturacion",
            accion="reintentar",
            entidad="documento_fiscal",
            entidad_id=d.id,
            detalle=f"Reintento de envío del documento {d.numero}",
        )
    )
    db.commit()
    return obtener_documento(doc_id, db, usuario)


@router.post("/{doc_id}/anular", response_model=DocumentoFiscalOut)
def anular_documento(
    doc_id: int,
    motivo: str = "Anulación por el emisor",
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    d = _obtener_doc(db, doc_id, usuario.empresa_id)
    if d.anulado:
        raise HTTPException(400, "El documento ya está anulado")
    d.anulado = True
    d.motivo_anulacion = motivo
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="facturacion",
            accion="anular",
            entidad="documento_fiscal",
            entidad_id=d.id,
            detalle=f"Documento {d.numero} anulado: {motivo}",
        )
    )
    db.commit()
    return obtener_documento(doc_id, db, usuario)


# ---------- Representación gráfica, PDF e impresión (200-205) ----------

@router.get("/{doc_id}/ticket", response_class=HTMLResponse)
def ticket_documento(
    doc_id: int,
    print: bool = True,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Ticket térmico (80mm) imprimible de la factura/nota de una venta."""
    doc = db.get(DocumentoFiscal, doc_id)
    if not doc or doc.empresa_id != usuario.empresa_id:
        raise HTTPException(404, "Documento no encontrado")
    venta = db.get(Venta, doc.venta_id) if doc.venta_id else None
    empresa = db.get(Empresa, doc.empresa_id)
    if not empresa and venta:
        empresa = db.get(Empresa, venta.empresa_id)
    sucursal = db.get(Sucursal, doc.sucursal_id) if doc.sucursal_id else None
    res_ticket = db.get(ResolucionFacturacion, doc.resolucion_id) if doc.resolucion_id else None
    cliente = None
    if venta and venta.cliente_id:
        cliente = db.get(Cliente, venta.cliente_id)
    detalle = []
    if venta:
        for line in db.query(VentaDetalle).filter(VentaDetalle.venta_id == venta.id).order_by(VentaDetalle.id).all():
            producto = db.get(Producto, line.producto_id)
            detalle.append({
                "nombre": producto.nombre if producto else f"Producto {line.producto_id}",
                "cant": float(line.cantidad),
                "precio": float(line.precio),
                "subtotal": float(line.subtotal or 0),
            })
    pagos = [
        {"medio": p.medio, "monto": float(p.monto), "referencia": p.referencia}
        for p in db.query(VentaPago).filter(VentaPago.venta_id == venta.id).all()
    ] if venta else []

    subtotal = float(venta.subtotal or 0) if venta else float(doc.monto or 0)
    descuento = float(venta.descuento or 0) if venta else 0.0
    impuesto = float(venta.impuesto or 0) if venta else 0.0
    propina = float(venta.propina or 0) if venta else 0.0
    total = float(doc.monto or venta.total) if (venta or doc) else 0.0

    items_html = "".join(
        f"<tr><td class='n'>{d['cant']:g}</td><td>{escape(str(d['nombre']))}</td>"
        f"<td class='r'>{d['precio']:,.0f}</td><td class='r'>{d['subtotal']:,.0f}</td></tr>"
        for d in detalle
    ) or "<tr><td colspan='4'>Sin detalle</td></tr>"

    pagos_html = "".join(
        f"<tr><td>{p['medio']}</td><td class='r'>{p['monto']:,.0f}</td>"
        f"<td class='r'>{escape(str(p['referencia'] or ''))}</td></tr>" for p in pagos
    ) or "<tr><td>—</td><td class='r'>—</td><td></td></tr>"

    qr = f"<img src='{doc.qr}' width='96' height='96' alt='QR'/>" if doc.qr else ""
    nombre_co = escape((empresa.razon_social or empresa.nombre or "Empresa") if empresa else "Empresa")
    nit_em = escape(f"NIT: {empresa.nit}") if empresa and getattr(empresa, "nit", None) else ""
    cliente_linea = escape((cliente.nombre or "") if cliente else "Consumidor final")
    if cliente and getattr(cliente, "documento", None):
        cliente_linea += escape(f"  ·  {cliente.tipo_documento or ''} {cliente.documento}")
    fec = str(doc.fecha_emision or "")
    fecha_short = escape((fec[:10]) if len(fec) >= 10 else fec)
    hora_short = escape((fec[11:19]) if len(fec) > 11 else "00:00:00")
    res_linea = ""
    if res_ticket:
        vig = f"{res_ticket.fecha_inicio} a {res_ticket.fecha_vencimiento}" if res_ticket.fecha_inicio else "vigente"
        res_linea = (
            f"<div class='pie'>RES: {res_ticket.resolucion} · VIGENCIA: {vig} · "
            f"RANGO: {res_ticket.rango_inicial}-{res_ticket.rango_final}</div>"
        )

    autoload = "window.print();" if print else ""

    try:
        _fb = json.loads((db.query(Configuracion).filter(Configuracion.clave == "pos.factura").first().valor or "{}"))
    except Exception:
        _fb = {}
    ancho_mm = int(_fb.get("ancho_mm") or 72)
    copias = max(1, int(_fb.get("copias") or 1))
    leyenda = escape((_fb.get("leyenda_pie") or "").strip())

    cuerpo_ticket = f"""
  <h2>{nombre_co.upper()}</h2>
  <div class="c">{nit_em}</div>
  {('<div class="c">' + (sucursal.nombre or '') + (' · ' + sucursal.direccion if sucursal and getattr(sucursal, 'direccion', None) else '') + '</div>') if sucursal else ''}
  <div class="sep"></div>
  <table>
    <tr><td>Documento</td><td class="r">{TIPO_LABEL.get(doc.tipo_documento, doc.tipo_documento)}</td></tr>
    <tr><td>Número</td><td class="r"><b>{doc.numero}</b></td></tr>
    <tr><td>Fecha</td><td class="r">{fecha_short}</td></tr>
    <tr><td>Hora</td><td class="r">{hora_short}</td></tr>
    <tr><td>Estado DIAN</td><td class="r">{'ANULADO' if doc.anulado else (doc.estado_dian or '').upper()}</td></tr>
  </table>
  {f'<table><tr><td>Resolución</td><td class="r">{escape(str(res_ticket.resolucion))}</td></tr><tr><td>Vigencia</td><td class="r">{escape(vig)}</td></tr><tr><td>Rango</td><td class="r">{res_ticket.rango_inicial}-{res_ticket.rango_final}</td></tr></table>' if res_ticket else ''}
  <table><tr><td>Cliente</td><td class="r">{cliente_linea}</td></tr></table>
  <div class="sep"></div>
  <table>
    <tr><th class="n">Cant</th><th>Producto</th><th class="r">P/U</th><th class="r">Sub</th></tr>
    {items_html}
  </table>
  <div class="sep"></div>
  <table>
    <tr><td>Subtotal</td><td class="r">{subtotal:,.0f}</td></tr>
    <tr><td>Descuento</td><td class="r">-{descuento:,.0f}</td></tr>
    <tr><td>Impuestos (IVA)</td><td class="r">{impuesto:,.0f}</td></tr>
    <tr><td>Propina</td><td class="r">{propina:,.0f}</td></tr>
    <tr class="tot"><td>Total</td><td class="r">{total:,.0f}</td></tr>
  </table>
  <div class="sep"></div>
  <table>
    <tr><th>Pago</th><th class="r">Monto</th><th class="r">Aprobación</th></tr>
    {pagos_html}
  </table>
  <div class="qr">{qr}</div>
  <div class="pie">{'CUDE' if doc.tipo_documento in ('nota_credito', 'nota_debito') else 'CUFE'}: {doc.cufe or ''}</div>
  {res_linea}
  {f'<div class="pie">{leyenda}</div>' if leyenda else ''}
  <div class="pie">La validez de este documento puede verificarse en el portal de la DIAN.</div>
"""
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Ticket {doc.numero}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Courier New', monospace; font-size: 12px; color: #000; }}
  .ticket {{ width: {ancho_mm}mm; margin: 0 auto; padding: 6mm; }}
  h2 {{ font-size: 13px; text-align: center; margin-bottom: 2px; }}
  .c {{ text-align: center; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td {{ padding: 1px 2px; }}
  .r {{ text-align: right; }} .n {{ text-align: center; }}
  .sep {{ border-top: 1px dashed #000; margin: 4px 0; }}
  .tot {{ font-weight: 700; font-size: 14px; }}
  .qr {{ text-align: center; margin: 4px 0; }}
  .pie {{ font-size: 9px; text-align: center; margin-top: 4px; }}
  .noprint {{ display: block; text-align: center; margin: 8px auto; padding: 8px 16px; font-size: 14px; }}
  @media print {{ .noprint {{ display: none; }} body {{ font-size: 11px; }} }}
</style></head><body>
<div class="ticket">
  {cuerpo_ticket * copias}
</div>
<button class="noprint" onclick="window.print()">Imprimir / Guardar PDF</button>
<script>{autoload}</script>
</body></html>"""


@router.get("/{doc_id}/pdf")
def pdf_documento(
    doc_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    _obtener_doc(db, doc_id, usuario.empresa_id)
    bytes_pdf = generar_pdf(db, doc_id)
    return Response(
        content=bytes_pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="fac_{doc_id}.pdf"'},
    )


@router.get("/{doc_id}/xml", response_class=Response)
def xml_documento(
    doc_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Descarga el XML UBL 2.1 del documento para la DIAN."""
    d = _obtener_doc(db, doc_id, usuario.empresa_id)
    if not d.xml_ubl:
        d.xml_ubl = generar_ubl_xml(db, d)
        db.commit()
    nombre = "".join((d.numero or f"doc{doc_id}").split())
    return Response(
        content=d.xml_ubl,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="fde_{nombre}.xml"'},
    )


@router.get("/{doc_id}/html", response_class=HTMLResponse)
def html_documento(
    doc_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    d = _obtener_doc(db, doc_id, usuario.empresa_id)
    venta = db.get(Venta, d.venta_id) if d.venta_id else None
    empresa = db.get(Empresa, d.empresa_id)
    sucursal = db.get(Sucursal, d.sucursal_id) if d.sucursal_id else None
    cliente = db.get(Cliente, venta.cliente_id) if venta and venta.cliente_id else None
    detalles = db.query(VentaDetalle).filter(VentaDetalle.venta_id == venta.id).all() if venta else []
    filas_partes = []
    for x in detalles:
        producto = db.get(Producto, x.producto_id)
        codigo = (producto.sku or producto.codigo_barras) if producto else "—"
        nombre = producto.nombre if producto else f"Producto {x.producto_id}"
        filas_partes.append(
            "<tr>"
            f"<td>{escape(str(codigo or '—'))}</td>"
            f"<td><strong>{escape(str(nombre))}</strong></td>"
            f"<td class='num'>{float(x.cantidad or 0):g}</td>"
            f"<td class='num'>$ {float(x.precio or 0):,.0f}</td>"
            f"<td class='num'>$ {float(x.descuento or 0):,.0f}</td>"
            f"<td class='num'><strong>$ {float(x.subtotal or 0):,.0f}</strong></td>"
            "</tr>"
        )
    filas = "".join(filas_partes) or "<tr><td colspan='6' class='empty'>Sin productos asociados al documento.</td></tr>"
    subtotal = float(venta.subtotal or 0) if venta else float(d.monto or 0)
    descuento = float(venta.descuento or 0) if venta else 0
    impuesto = float(venta.impuesto or 0) if venta else 0
    total = float(d.monto or (venta.total if venta else 0) or 0)
    estado = "ANULADO" if d.anulado else (d.estado_dian or "pendiente").upper()
    cliente_nombre = escape(str(cliente.nombre)) if cliente else "Consumidor final"
    cliente_doc = escape(f"{cliente.tipo_documento or ''} {cliente.documento or ''}".strip()) if cliente else "No informado"
    empresa_nombre = escape(str((empresa.razon_social or empresa.nombre) if empresa else "Empresa"))
    empresa_nit = escape(str(empresa.nit or "No informado")) if empresa else "No informado"
    sucursal_nombre = escape(str(sucursal.nombre)) if sucursal else "Principal"
    res_view = db.get(ResolucionFacturacion, d.resolucion_id) if d.resolucion_id else None
    codigo_unique = "CUDE" if d.tipo_documento in ("nota_credito", "nota_debito") else "CUFE"
    vig_view = f"{res_view.fecha_inicio} a {res_view.fecha_vencimiento}" if res_view and res_view.fecha_inicio else "vigente"
    res_html = f"<div>Resolución <strong>{escape(str(res_view.resolucion))}</strong></div><div class='muted'>Vigencia {vig_view} · Rango {res_view.rango_inicial}-{res_view.rango_final}</div>" if res_view else "<div class='muted'>Sin resolución autorizada</div>"
    fecha_full = escape(str(d.fecha_emision or "—"))
    hora_html = escape(fecha_full[11:19]) if len(fecha_full) > 11 else ""
    pagos_view = [
        {"medio": (p.medio or "otro").capitalize(), "monto": float(p.monto), "referencia": p.referencia}
        for p in (db.query(VentaPago).filter(VentaPago.venta_id == venta.id).all() if venta else [])
    ]
    if pagos_view:
        for r_p in pagos_view:
            if (r_p["medio"] or "").lower() == "efectivo":
                r_p["medio"] = "Efectivo"
    pagos_rows = "".join(
        f"<div class='totalrow'><span class='muted'>{escape(str(p['medio']))}</span>"
        f"<span>$ {p['monto']:,.0f}</span></div>"
        for p in pagos_view
    )
    _lin = []
    for x in detalles:
        _prod = db.get(Producto, x.producto_id)
        _lin.append({
            "subtotal": float(x.subtotal or 0),
            "descuento": float(x.descuento or 0),
            "impuesto": float((getattr(_prod, "impuesto", None) if _prod else 0) or 0),
            "impuesto_monto": float(x.impuesto if x.impuesto is not None else 0),
        })
    desglose_view = _desglose_iva(_lin)
    iva_rows = ""
    if desglose_view:
        iva_rows = "".join(
            (f"<div class='totalrow'><span class='muted'>IVA {g['tasa']:g}%</span><span>$ {g['impuesto']:,.0f}</span></div>"
             if g["tasa"] else
             "<div class='totalrow'><span class='muted'>Base excluida (exento)</span><span>$ %s</span></div>" % f"{g['base']:,.0f}")
            for g in desglose_view
        )
    else:
        iva_rows = f"<div class='totalrow'><span class='muted'>Impuestos</span><span>$ {impuesto:,.0f}</span></div>"
    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>{d.numero}</title>
<style>
  :root {{ --ink:#172033; --muted:#64748b; --line:#dbe3ee; --brand:#b91c1c; --soft:#fff5f5; }}
  * {{ box-sizing:border-box; }} body {{ margin:0; background:#eef2f7; color:var(--ink); font:14px Inter,Arial,sans-serif; }}
  .sheet {{ width:min(900px,calc(100% - 32px)); margin:28px auto; background:#fff; border:1px solid var(--line); box-shadow:0 12px 35px #0f172a18; }}
  .top {{ display:flex; justify-content:space-between; gap:24px; padding:30px 34px 24px; border-top:6px solid var(--brand); }}
  .brand h1 {{ margin:0 0 7px; font-size:22px; letter-spacing:-.4px; }} .muted {{ color:var(--muted); line-height:1.55; }}
  .type {{ min-width:250px; border:1px solid #fecaca; background:var(--soft); padding:15px 17px; border-radius:8px; }}
  .type b {{ display:block; color:var(--brand); font-size:14px; text-transform:uppercase; letter-spacing:.5px; }} .number {{ font-size:20px; font-weight:800; margin:7px 0; }}
  .status {{ display:inline-block; border-radius:999px; padding:4px 9px; background:#e2e8f0; font-size:11px; font-weight:800; letter-spacing:.3px; }}
  .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; padding:0 34px 24px; }} .box {{ border:1px solid var(--line); border-radius:8px; padding:14px 16px; }}
  .label {{ color:var(--muted); text-transform:uppercase; font-size:10px; letter-spacing:.7px; font-weight:800; margin-bottom:6px; }}
  table {{ width:calc(100% - 68px); margin:0 34px; border-collapse:collapse; }} th {{ background:#172033; color:white; padding:10px; font-size:11px; text-align:left; }}
  td {{ padding:11px 10px; border-bottom:1px solid var(--line); vertical-align:top; }} .num {{ text-align:right; white-space:nowrap; }} .empty {{ text-align:center; color:var(--muted); padding:22px; }}
  .bottom {{ display:flex; justify-content:space-between; gap:24px; padding:24px 34px 32px; }} .cufe {{ max-width:470px; word-break:break-all; font:10px ui-monospace,monospace; color:var(--muted); }}
  .totals {{ min-width:270px; }} .totalrow {{ display:flex; justify-content:space-between; padding:5px 0; }} .grand {{ border-top:2px solid var(--ink); margin-top:7px; padding-top:10px; font-size:18px; font-weight:800; }}
  .qr {{ width:105px; height:105px; margin-top:12px; }} .actions {{ width:min(900px,calc(100% - 32px)); margin:0 auto 25px; text-align:right; }} button {{ border:0; background:var(--brand); color:white; padding:10px 16px; border-radius:7px; font-weight:700; cursor:pointer; }}
  @media print {{ body{{background:#fff}} .sheet{{width:100%;margin:0;border:0;box-shadow:none}} .actions{{display:none}} }} @media(max-width:650px) {{ .top,.bottom{{display:block;padding:22px}} .type{{margin-top:18px}} .grid{{grid-template-columns:1fr;padding:0 22px 20px}} table{{width:calc(100% - 44px);margin:0 22px}} th:nth-child(1),td:nth-child(1),th:nth-child(5),td:nth-child(5){{display:none}} }}
</style></head><body>
<div class="sheet"><section class="top"><div class="brand"><h1>{empresa_nombre}</h1><div class="muted">NIT {empresa_nit}<br>{sucursal_nombre}</div></div><div class="type"><b>{TIPO_LABEL.get(d.tipo_documento, d.tipo_documento)}</b><div class="number">{escape(d.numero)}</div><div class="muted">Emitida: {fecha_full} {('· ' + hora_html) if hora_html else ''}</div><span class="status">DIAN: {estado}</span></div></section>
<section class="grid"><div class="box"><div class="label">Facturado a</div><strong>{cliente_nombre}</strong><div class="muted">{cliente_doc}</div></div><div class="box"><div class="label">Información del documento</div>{res_html}<div>Prefijo y consecutivo: <strong>{escape(d.prefijo or '')} {d.consecutivo or '—'}</strong></div>{f'<div class="muted">{escape(d.concepto)}</div>' if d.concepto else ''}</div></section>
<table><thead><tr><th>Código</th><th>Descripción</th><th class="num">Cant.</th><th class="num">Precio</th><th class="num">Descuento</th><th class="num">Total</th></tr></thead><tbody>{filas}</tbody></table>
<section class="bottom"><div><div class="label">Código único de factura electrónica</div><div class="cufe">{codigo_unique}: {escape(d.cufe or 'Pendiente de asignación')}</div>{f'<img class="qr" src="{d.qr}" alt="Código QR de validación">' if d.qr else ''}</div><div class="totals"><div class="totalrow"><span>Subtotal</span><span>$ {subtotal:,.0f}</span></div><div class="totalrow"><span>Descuentos</span><span>$ {descuento:,.0f}</span></div>{iva_rows}<div class="totalrow grand"><span>Total</span><span>$ {total:,.0f}</span></div><div class="label" style="margin-top:10px">Pagos</div>{pagos_rows or '<div class="totalrow"><span class="muted">Sin pagos registrados</span></div>'}</div></section></div><div class="actions"><button onclick="window.print()">Imprimir o guardar PDF</button></div></body></html>"""
    return html


@router.post("/{doc_id}/correo")
def enviar_correo(
    doc_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Envía la factura por correo (simulado: queda registrado en auditoría)."""
    d = _obtener_doc(db, doc_id, usuario.empresa_id)
    cliente = ""
    if d.venta_id:
        venta = db.get(Venta, d.venta_id)
        if venta and venta.cliente_id:
            c = db.get(Cliente, venta.cliente_id)
            if c:
                cliente = c.email or ""
    empresa = db.get(Empresa, d.empresa_id)
    destinatario = cliente or (empresa.email if empresa else "") or "(correo no registrado, simulado)"
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="facturacion",
            accion="correo",
            entidad="documento_fiscal",
            entidad_id=d.id,
            detalle=f"Factura {d.numero} enviada por correo a {destinatario}",
        )
    )
    db.commit()
    return {"ok": True, "destinatario": destinatario, "asunto": f"Factura {d.numero}"}


@router.post("/{doc_id}/whatsapp")
def enviar_whatsapp(
    doc_id: int,
    telefono: str | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Genera el vínculo de WhatsApp para compartir la factura (simulado)."""
    d = _obtener_doc(db, doc_id, usuario.empresa_id)
    cliente = ""
    if d.venta_id:
        venta = db.get(Venta, d.venta_id)
        if venta and venta.cliente_id:
            c = db.get(Cliente, venta.cliente_id)
            if c:
                cliente = c.telefono or ""
    destino = telefono or cliente or ""
    link = f"https://wa.me/{destino}?text=Su%20documento%20{d.numero}%20(cufe%20{d.cufe})"
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="facturacion",
            accion="whatsapp",
            entidad="documento_fiscal",
            entidad_id=d.id,
            detalle=f"Enlace WhatsApp generado para {d.numero}",
        )
    )
    db.commit()
    return {"ok": True, "enlace": link}


# ---------- Resumen e historial (206, 330) ----------

@router.get("/resumen")
def resumen_facturacion(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    q = db.query(DocumentoFiscal).filter(DocumentoFiscal.empresa_id == usuario.empresa_id)
    anulados = q.filter(DocumentoFiscal.anulado == True).count()
    por_estado = {
        "pendiente": q.filter(DocumentoFiscal.estado_dian == "pendiente", DocumentoFiscal.anulado == False).count(),
        "enviado": q.filter(DocumentoFiscal.estado_dian == "enviado", DocumentoFiscal.anulado == False).count(),
        "aprobado": q.filter(DocumentoFiscal.estado_dian == "aprobado", DocumentoFiscal.anulado == False).count(),
        "rechazado": q.filter(DocumentoFiscal.estado_dian == "rechazado", DocumentoFiscal.anulado == False).count(),
        "anulado": anulados,
    }
    por_tipo = {t: q.filter(DocumentoFiscal.tipo_documento == t).count() for t in TIPO_LABEL}
    monto = q.filter(DocumentoFiscal.anulado == False).with_entities(DocumentoFiscal.monto).all()
    return {
        "total": int(q.count()),
        "por_estado": por_estado,
        "por_tipo": por_tipo,
        "valor_facturado": round(sum(float(m[0] or 0) for m in monto), 2),
    }


@router.get("/ventas-sin-facturar")
def ventas_sin_facturar(
    sucursal_id: int | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    facturadas = db.query(DocumentoFiscal.venta_id).filter(
        DocumentoFiscal.tipo_documento == "factura",
        DocumentoFiscal.empresa_id == usuario.empresa_id,
    ).all()
    ids = {f[0] for f in facturadas if f[0]}
    q = db.query(Venta).filter(Venta.estado == "completada", Venta.empresa_id == usuario.empresa_id)
    if sucursal_id:
        q = q.filter(Venta.sucursal_id == sucursal_id)
    ventas = q.order_by(Venta.id.desc()).limit(50).all()
    return [
        {
            "id": v.id,
            "numero": v.numero,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "cliente": (db.get(Cliente, v.cliente_id).nombre if v.cliente_id and db.get(Cliente, v.cliente_id) else "Consumidor final"),
            "total": float(v.total or 0),
        }
        for v in ventas if v.id not in ids
    ]
