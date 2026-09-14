from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from html import escape
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_permiso
from ..models import (
    AperturaCaja,
    ArqueoCaja,
    AuditoriaLog,
    Caja,
    Empresa,
    Gasto,
    MovimientoCaja,
    PuntoVenta,
    Sucursal,
    Usuario,
    Venta,
    VentaPago,
)
from ..schemas.ventas import (
    AperturaCajaCreate,
    AperturaCajaOut,
    CambioCajeroIn,
    GastoCreate,
    GastoOut,
    MovimientoCajaCreate,
    MovimientoCajaOut,
    TransferenciaCajaCreate,
    TurnoOut,
)

router = APIRouter(prefix="/caja", tags=["caja"])


@router.post("/apertura", response_model=AperturaCajaOut, status_code=201)
def abrir_caja(
    data: AperturaCajaCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    if not db.get(Caja, data.caja_id):
        raise HTTPException(400, "Caja no existe")
    abierta = (
        db.query(AperturaCaja)
        .filter_by(caja_id=data.caja_id, estado="abierta")
        .first()
    )
    if abierta:
        raise HTTPException(400, "La caja ya está abierta")
    apertura = AperturaCaja(
        caja_id=data.caja_id,
        usuario_id=usuario.id,
        saldo_inicial=data.saldo_inicial,
        estado="abierta",
    )
    db.add(apertura)
    db.commit()
    db.refresh(apertura)
    return apertura


@router.post("/{apertura_id}/cierre", response_model=AperturaCajaOut)
def cerrar_caja(apertura_id: int, db: Session = Depends(get_db)):
    apertura = db.get(AperturaCaja, apertura_id)
    if not apertura:
        raise HTTPException(404, "Apertura no encontrada")
    if apertura.estado != "abierta":
        raise HTTPException(400, "La caja ya está cerrada")

    ventas = (
        db.query(Venta).filter(Venta.caja_id == apertura.caja_id, Venta.estado == "completada").all()
    )
    ingreso_ventas = sum(float(v.total) for v in ventas)
    movimientos = (
        db.query(MovimientoCaja).filter(MovimientoCaja.apertura_caja_id == apertura.id).all()
    )
    saldo_movs = sum(float(m.monto) for m in movimientos if m.tipo in ("ingreso",))
    saldo_movs -= sum(float(m.monto) for m in movimientos if m.tipo in ("egreso", "gasto", "retiro"))

    saldo_cierre = float(apertura.saldo_inicial or 0) + ingreso_ventas + saldo_movs
    apertura.saldo_cierre = saldo_cierre
    apertura.estado = "cerrada"
    db.commit()
    db.refresh(apertura)
    return apertura


@router.post("/movimientos", response_model=MovimientoCajaOut, status_code=201)
def registrar_movimiento(
    data: MovimientoCajaCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    from ..seguridad import requiere_autorizacion

    apertura = db.get(AperturaCaja, data.apertura_caja_id)
    if not apertura or apertura.estado != "abierta":
        raise HTTPException(400, "Apertura de caja no válida o no abierta")
    requiere_autorizacion(
        db, usuario, "caja", "movimientos",
        entidad="apertura_caja", entidad_id=apertura.id,
        datos={"tipo": data.tipo, "monto": data.monto, "concepto": data.concepto},
    )
    mov = MovimientoCaja(
        apertura_caja_id=data.apertura_caja_id,
        usuario_id=usuario.id,
        tipo=data.tipo,
        concepto=data.concepto,
        monto=data.monto,
        medio=data.medio,
    )
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return mov


@router.post("/arqueo", status_code=201)
def registrar_arqueo(
    apertura_id: int,
    efectivo_contado: float,
    observacion: str | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    from ..seguridad import requiere_autorizacion

    apertura = db.get(AperturaCaja, apertura_id)
    if not apertura:
        raise HTTPException(404, "Apertura no encontrada")
    requiere_autorizacion(
        db, usuario, "caja", "movimientos",
        entidad="apertura_caja", entidad_id=apertura_id,
        datos={"efectivo_contado": efectivo_contado},
    )

    ventas = (
        db.query(Venta).filter(Venta.caja_id == apertura.caja_id).all()
    )
    ingresos_venta = sum(float(v.total) for v in ventas)
    pago_efectivo = sum(
        float(p.monto) for v in ventas for p in v.pagos if p.medio == "efectivo"
    )
    esperado = float(apertura.saldo_inicial or 0) + pago_efectivo
    diferencia = efectivo_contado - esperado
    arqueo = ArqueoCaja(
        apertura_caja_id=apertura.id,
        usuario_id=usuario.id,
        contado_efectivo=efectivo_contado,
        contado_esperado=esperado,
        diferencia=diferencia,
        observacion=observacion,
    )
    db.add(arqueo)
    db.commit()
    return {"ok": True, "esperado": esperado, "contado": efectivo_contado, "diferencia": diferencia}


@router.post("/gastos", response_model=GastoOut, status_code=201)
def crear_gasto(
    data: GastoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    from ..seguridad import requiere_autorizacion

    requiere_autorizacion(
        db, usuario, "caja", "gastos",
        entidad_id=data.sucursal_id,
        datos={"categoria": data.categoria, "monto": data.monto, "medio": data.medio},
    )
    gasto = Gasto(
        empresa_id=data.empresa_id,
        sucursal_id=data.sucursal_id,
        usuario_id=usuario.id,
        categoria=data.categoria,
        concepto=data.concepto,
        monto=data.monto,
        medio=data.medio,
    )
    db.add(gasto)
    db.commit()
    db.refresh(gasto)
    return gasto


@router.get("/gastos", response_model=list[GastoOut])
def listar_gastos(db: Session = Depends(get_db)):
    return db.query(Gasto).order_by(Gasto.id.desc()).limit(100).all()


@router.patch("/{apertura_id}/cajero")
def cambiar_cajero(
    apertura_id: int,
    data: CambioCajeroIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    from ..seguridad import requiere_autorizacion

    apertura = db.get(AperturaCaja, apertura_id)
    if not apertura:
        raise HTTPException(404, "Apertura no encontrada")
    if apertura.estado != "abierta":
        raise HTTPException(400, "Solo se puede cambiar el cajero con la caja abierta")
    if not db.get(Usuario, data.usuario_id):
        raise HTTPException(400, "Cajero no existe")
    requiere_autorizacion(
        db, usuario, "caja", "movimientos",
        entidad="apertura_caja", entidad_id=apertura.id,
        datos={"nuevo_cajero": data.usuario_id},
    )
    previo = apertura.usuario_id
    apertura.usuario_id = data.usuario_id
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="caja",
            accion="cambio-cajero",
            entidad="apertura_caja",
            entidad_id=apertura.id,
            detalle=f"Cambio de cajero {previo} -> {data.usuario_id}",
        )
    )
    db.commit()
    db.refresh(apertura)
    return {"ok": True, "apertura_id": apertura.id, "cajero_id": apertura.usuario_id}


@router.post("/transferir")
def transferir_efectivo(
    data: TransferenciaCajaCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    from ..seguridad import requiere_autorizacion

    if data.monto <= 0:
        raise HTTPException(400, "Monto inválido")
    origen = db.get(AperturaCaja, data.origen_apertura_id)
    destino = db.get(AperturaCaja, data.destino_apertura_id)
    if not origen or not destino or origen.estado != "abierta" or destino.estado != "abierta":
        raise HTTPException(400, "Origen y destino deben ser aperturas abiertas")
    requiere_autorizacion(
        db, usuario, "caja", "movimientos",
        entidad="apertura_caja", entidad_id=origen.id,
        datos={"tipo": "transferencia", "monto": data.monto, "destino": destino.id},
    )
    db.add(
        MovimientoCaja(
            apertura_caja_id=origen.id,
            usuario_id=usuario.id,
            tipo="egreso",
            concepto=data.concepto,
            monto=data.monto,
            medio="efectivo",
        )
    )
    db.add(
        MovimientoCaja(
            apertura_caja_id=destino.id,
            usuario_id=usuario.id,
            tipo="ingreso",
            concepto=f"Transferencia desde caja {origen.caja_id}",
            monto=data.monto,
            medio="efectivo",
        )
    )
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="caja",
            accion="transferencia-efectivo",
            entidad="apertura_caja",
            entidad_id=origen.id,
            detalle=f"Transferencia {data.monto} a apertura {destino.id}",
        )
    )
    db.commit()
    return {"ok": True, "monto": data.monto, "origen": origen.id, "destino": destino.id}


@router.get("/turnos", response_model=list[TurnoOut])
def listar_turnos(
    caja_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(AperturaCaja).order_by(AperturaCaja.id.desc())
    if caja_id:
        q = q.filter(AperturaCaja.caja_id == caja_id)
    por_usuario = {}
    salida = []
    for a in q.limit(100).all():
        if a.usuario_id not in por_usuario:
            u = db.get(Usuario, a.usuario_id)
            por_usuario[a.usuario_id] = u.nombre if u else None
        caja = db.get(Caja, a.caja_id)
        salida.append(
            TurnoOut(
                id=a.id,
                caja_id=a.caja_id,
                caja_nombre=caja.nombre if caja else None,
                cajero_id=a.usuario_id,
                cajero_nombre=por_usuario[a.usuario_id],
                saldo_inicial=a.saldo_inicial,
                saldo_cierre=a.saldo_cierre,
                estado=a.estado,
                created_at=a.created_at,
            )
        )
    return salida


@router.get("/{apertura_id}")
def detalle_apertura(apertura_id: int, db: Session = Depends(get_db)):
    a = db.get(AperturaCaja, apertura_id)
    if not a:
        raise HTTPException(404, "Apertura no encontrada")
    movimientos = (
        db.query(MovimientoCaja).filter(MovimientoCaja.apertura_caja_id == a.id).all()
    )
    arqueos = (
        db.query(ArqueoCaja).filter(ArqueoCaja.apertura_caja_id == a.id).all()
    )
    cajero = db.get(Usuario, a.usuario_id)
    return {
        "id": a.id,
        "caja_id": a.caja_id,
        "cajero": cajero.nombre if cajero else None,
        "saldo_inicial": float(a.saldo_inicial or 0),
        "saldo_cierre": float(a.saldo_cierre or 0),
        "estado": a.estado,
        "created_at": a.created_at,
        "movimientos": [
            {
                "id": m.id,
                "tipo": m.tipo,
                "concepto": m.concepto,
                "monto": float(m.monto or 0),
                "medio": m.medio,
                "created_at": m.created_at,
            }
            for m in movimientos
        ],
        "arqueos": [
            {
                "contado": float(x.contado_efectivo or 0),
                "esperado": float(x.contado_esperado or 0),
                "diferencia": float(x.diferencia or 0),
                "observacion": x.observacion,
            }
            for x in arqueos
        ],
    }


@router.get("/{apertura_id}/cierre/reporte", response_class=HTMLResponse)
def reporte_cierre(apertura_id: int, db: Session = Depends(get_db)):
    """Resumen de cierre de caja imprimible (ticket térmico 72mm)."""
    apertura = db.get(AperturaCaja, apertura_id)
    if not apertura:
        raise HTTPException(404, "Apertura no encontrada")
    caja = db.get(Caja, apertura.caja_id)
    cajero = db.get(Usuario, apertura.usuario_id)
    empresa = db.get(Empresa, cajero.empresa_id) if cajero else None
    sucursal = None
    if caja and caja.punto_venta_id:
        punto = db.get(PuntoVenta, caja.punto_venta_id)
        if punto and punto.sucursal_id:
            sucursal = db.get(Sucursal, punto.sucursal_id)

    ventas = db.query(Venta).filter(Venta.caja_id == apertura.caja_id, Venta.estado == "completada").all()
    ingreso_ventas = sum(float(v.total) for v in ventas)
    por_medio: dict[str, float] = {}
    for v in ventas:
        for p in db.query(VentaPago).filter(VentaPago.venta_id == v.id).all():
            med = (p.medio or "otro").capitalize()
            por_medio[med] = por_medio.get(med, 0) + float(p.monto or 0)

    movimientos = db.query(MovimientoCaja).filter(MovimientoCaja.apertura_caja_id == apertura.id).all()
    neto_movs = 0.0
    for m in movimientos:
        if m.tipo in ("ingreso",):
            neto_movs += float(m.monto or 0)
        elif m.tipo in ("egreso", "gasto", "retiro"):
            neto_movs -= float(m.monto or 0)
    saldo_cierre = float(apertura.saldo_inicial or 0) + ingreso_ventas + neto_movs

    arqueos = db.query(ArqueoCaja).filter(ArqueoCaja.apertura_caja_id == apertura.id).all()
    arqueo_cerrado = arqueos[-1] if arqueos else None

    razon = escape((empresa.razon_social or empresa.nombre or "Empresa") if empresa else "Empresa")
    nit = escape(str(empresa.nit or "")) if empresa else ""
    caja_nombre = escape(caja.nombre or f"Caja {apertura.caja_id}") if caja else f"Caja {apertura.caja_id}"
    cajero_nombre = escape(cajero.nombre or "") if cajero else "—"
    sucursal_nombre = escape(sucursal.nombre) if sucursal else ""
    fec = str(apertura.created_at or "")
    fecha_ab = fec[:10] if len(fec) >= 10 else fec

    medio_html = "".join(
        f"<tr><td>{escape(m)}</td><td class='r'>{v:,.0f}</td></tr>" for m, v in sorted(por_medio.items(), key=lambda kv: -kv[1])
    ) or "<tr><td colspan='2' class='c'>Sin ventas</td></tr>"
    mov_html = "".join(
        "<tr>"
        f"<td>{escape(str(m.tipo).capitalize())}</td>"
        f"<td>{escape(str(m.concepto or ''))}</td>"
        f"<td class='r'>{'+' if m.tipo == 'ingreso' else '-'}{m.monto:,.0f}</td>"
        "</tr>"
        for m in movimientos
    ) or "<tr><td colspan='3' class='c'>Sin movimientos</td></tr>"
    arqueo_html = ""
    if arqueo_cerrado:
        dif = float(arqueo_cerrado.diferencia or 0)
        arqueo_html = (
            "<div class='sep'></div><div class='c'><b>ARQUEO</b></div><table>"
            f"<tr><td>Esperado (efectivo)</td><td class='r'>{float(arqueo_cerrado.contado_esperado or 0):,.0f}</td></tr>"
            f"<tr><td>Contado</td><td class='r'>{float(arqueo_cerrado.contado_efectivo or 0):,.0f}</td></tr>"
            f"<tr><td><b>Diferencia</b></td><td class='r'><b>{dif:+,.0f}</b></td></tr>"
            f"{f'<tr><td>Observación</td><td class='r'>{escape(str(arqueo_cerrado.observacion or ''))}</td></tr>' if arqueo_cerrado.observacion else ''}"
            "</table>"
        )
    estado = "CERRADA" if apertura.estado == "cerrada" else "ABIERTA"

    cuerpo = f"""  <h2>{razon.upper()}</h2>
  {"<div class='c'>" + nit + "</div>" if nit else ""}
  <div class="c">Resumen de cierre · {estado}</div>
  {"<div class='c'>" + sucursal_nombre + "</div>" if sucursal_nombre else ""}
  <div class="sep"></div>
  <table>
    <tr><td>Caja</td><td class="r"><b>{caja_nombre}</b></td></tr>
    <tr><td>Cajero</td><td class="r">{cajero_nombre}</td></tr>
    <tr><td>Apertura #{apertura.id}</td><td class="r">{fecha_ab}</td></tr>
    <tr><td>Estado</td><td class="r">{estado}</td></tr>
  </table>
  <div class="sep"></div>
  <div class="c"><b>VENTAS DEL TURNO</b></div>
  <table>
    <tr><td>Número de ventas</td><td class="r">{len(ventas)}</td></tr>
    <tr><td>Total facturado</td><td class="r">{ingreso_ventas:,.0f}</td></tr>
    <tr><td colspan="2"><div class="sep"></div></td></tr>
    {medio_html}
  </table>
  <div class="sep"></div>
  <div class="c"><b>MOVIMIENTOS</b></div>
  <table>
    <tr><th>Tipo</th><th>Concepto</th><th class="r">Valor</th></tr>
    {mov_html}
  </table>
  <div class="sep"></div>
  <table>
    <tr><td>Saldo inicial</td><td class="r">{float(apertura.saldo_inicial or 0):,.0f}</td></tr>
    <tr><td>+ Ventas</td><td class="r">{ingreso_ventas:,.0f}</td></tr>
    <tr><td>{'+ Movimientos netos' if neto_movs >= 0 else '- Movimientos netos'}</td><td class="r">{abs(neto_movs):,.0f}</td></tr>
    <tr class="tot"><td>Saldo de cierre</td><td class="r">{saldo_cierre:,.0f}</td></tr>
  </table>
  {arqueo_html}
  <div class="sep"></div>
  <div class="c" style="font-size:9px">Documento generado por el POS · Cierre de caja diario</div>
  <div style="height:18mm"></div>
  <table>
    <tr><td class="c">_______________________</td><td class="c">_______________________</td></tr>
    <tr><td class="c" style="font-size:9px">Cajero</td><td class="c" style="font-size:9px">Administrador</td></tr>
  </table>
"""
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Resumen de cierre #{apertura.id}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'Courier New',monospace; font-size:12px; color:#000; }}
  .ticket {{ width:72mm; margin:0 auto; padding:4mm; }}
  h2 {{ font-size:13px; text-align:center; margin-bottom:2px; }}
  .c {{ text-align:center; }} .r {{ text-align:right; }}
  table {{ width:100%; border-collapse:collapse; }} td,th {{ padding:1px 2px; }}
  .sep {{ border-top:1px dashed #000; margin:4px 0; }}
  .tot {{ font-weight:700; font-size:14px; }}
  .noprint {{ display:block; text-align:center; margin:8px auto; padding:8px 16px; font-size:14px; }}
  @media print {{ .noprint {{ display:none; }} body {{ font-size:11px; }} }}
</style></head><body>
<div class="ticket">{cuerpo}</div>
<button class="noprint" onclick="window.print()">Imprimir / Guardar PDF</button>
<script>window.print();</script>
</body></html>"""