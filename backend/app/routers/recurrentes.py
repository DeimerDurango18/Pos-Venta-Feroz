import calendar
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    AuditoriaLog,
    Cliente,
    Empresa,
    FacturaRecurrente,
    Producto,
    Sucursal,
    Usuario,
    Venta,
)
from ..schemas.recurrentes import (
    FacturaRecurrenteCreate,
    FacturaRecurrenteOut,
    FacturaRecurrenteUpdate,
    RecordatorioEnviar,
    RecordatorioOut,
)
from ..schemas.ventas import VentaCreate, VentaDetalleCreate, VentaPagoCreate
from ..wa import config_bool, enviar_whatsapp, guardar_config, obtener_config

router = APIRouter(prefix="/recurrentes", tags=["facturas recurrentes"])

PERIODICIDADES = ("diaria", "semanal", "quincenal", "mensual")


def _mes_siguiente(d: date, dia: int) -> date:
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    ultimo = calendar.monthrange(y, m)[1]
    return date(y, m, min(dia, ultimo))


def _siguiente_fecha(periodicidad: str, dia: int, desde: date) -> date:
    if periodicidad == "diaria":
        return desde + timedelta(days=1)
    if periodicidad == "quincenal":
        return desde + timedelta(days=15)
    if periodicidad == "semanal":
        py = (dia + 6) % 7  # model usa 0=domingo..6=sábado -> weekday() 0=lun
        delta = (py - desde.weekday()) % 7 or 7
        return desde + timedelta(days=delta)
    return _mes_siguiente(desde, dia)


def _validar_items(db: Session, items: list) -> list:
    limpio = []
    for it in (items or []):
        pid = int(it.producto_id if not isinstance(it, dict) else it["producto_id"])
        producto = db.get(Producto, pid)
        if not producto or not producto.activo:
            raise HTTPException(400, f"Producto {pid} no existe o inactivo")
        limpio.append({
            "producto_id": pid,
            "cantidad": float(it.cantidad if not isinstance(it, dict) else it["cantidad"]),
            "precio": (float(it.precio) if not isinstance(it, dict) else float(it["precio"] or 0)) or None,
        })
    return limpio


def _serializar(db: Session, fr: FacturaRecurrente) -> dict:
    cliente = db.get(Cliente, fr.cliente_id) if fr.cliente_id else None
    est = 0.0
    for it in (fr.items or []):
        cant = float(it.get("cantidad", 1))
        precio = float(it.get("precio") or 0)
        if not precio:
            p = db.get(Producto, int(it.get("producto_id", 0)))
            precio = float(p.precio_venta or 0) if p else 0
        est += precio * cant
    est = round(est - float(fr.descuento_global or 0), 2)
    return {
        "id": fr.id,
        "empresa_id": fr.empresa_id,
        "cliente_id": fr.cliente_id,
        "cliente_nombre": cliente.nombre if cliente else None,
        "sucursal_id": fr.sucursal_id,
        "periodicidad": fr.periodicidad,
        "dia": fr.dia,
        "descripcion": fr.descripcion,
        "items": fr.items or [],
        "descuento_global": float(fr.descuento_global or 0),
        "tipo": fr.tipo,
        "medio_pago": fr.medio_pago,
        "activo": bool(fr.activo),
        "proxima_fecha": fr.proxima_fecha,
        "ultima_fecha": fr.ultima_fecha,
        "ultima_venta_id": fr.ultima_venta_id,
        "total_estimado": est,
    }


def _ejecutar(db: Session, fr: FacturaRecurrente) -> Venta:
    """Genera la venta de la factura recurrente y actualiza la plantilla."""
    from ..routers.ventas import crear_venta_interna

    usuario = db.get(Usuario, fr.usuario_id) or db.query(Usuario).filter(
        Usuario.activo == True  # noqa: E712
    ).order_by(Usuario.id).first()
    if not usuario:
        raise HTTPException(500, "Sin usuario para ejecutar la factura recurrente")
    sucursal_id = fr.sucursal_id
    if not sucursal_id:
        suc = db.query(Sucursal).order_by(Sucursal.id).first()
        sucursal_id = suc.id if suc else None
    if not sucursal_id:
        raise HTTPException(400, "No hay sucursal configurada para la factura recurrente")

    subtotal = 0.0
    detalle = []
    for it in (fr.items or []):
        precio = float(it.get("precio") or 0) or None
        cant = float(it.get("cantidad", 1))
        pid = int(it.get("producto_id", 0))
        prod = db.get(Producto, pid)
        if precio is None:
            precio = float(prod.precio_venta or 0) if prod else 0
        subtotal += precio * cant
        detalle.append(VentaDetalleCreate(producto_id=pid, cantidad=cant, precio=precio))

    pagos = []
    if fr.tipo == "contado":
        monto_total = round(subtotal - float(fr.descuento_global or 0), 2)
        pagos = [VentaPagoCreate(medio=fr.medio_pago or "efectivo", monto=monto_total)]

    venta = crear_venta_interna(
        db,
        VentaCreate(
            empresa_id=fr.empresa_id,
            sucursal_id=sucursal_id,
            cliente_id=fr.cliente_id,
            tipo=fr.tipo,
            descuento_global=float(fr.descuento_global or 0),
            nota=f"Factura recurrente #{fr.id}: {fr.descripcion or fr.periodicidad}",
            detalle=detalle,
            pagos=pagos,
        ),
        usuario,
    )
    db.refresh(venta)
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="recurrentes",
            accion="ejecutar",
            entidad="factura_recurrente",
            entidad_id=fr.id,
            detalle=f"Factura recurrente {fr.id} generó {venta.numero} por {float(venta.total or 0):,.0f}",
        )
    )
    hoy = date.today()
    fr.ultima_fecha = hoy
    fr.ultima_venta_id = venta.id
    fr.proxima_fecha = _siguiente_fecha(fr.periodicidad, fr.dia or 1, hoy)
    db.commit()
    return venta


def procesar_facturas_recurrentes(db: Session) -> dict:
    """Scheduler: genera todas las plantillas vencidas. Devuelve resumen."""
    hoy = date.today()
    frs = (
        db.query(FacturaRecurrente)
        .filter(FacturaRecurrente.activo == True)  # noqa: E712
        .all()
    )
    generadas, errores = [], []
    for fr in frs:
        if fr.proxima_fecha is None or fr.proxima_fecha > hoy:
            continue
        try:
            venta = _ejecutar(db, fr)
            generadas.append({"id": fr.id, "venta_id": venta.id, "numero": venta.numero})
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            fr = db.get(FacturaRecurrente, fr.id)
            if fr:
                fr.proxima_fecha = hoy + timedelta(days=1)
                try:
                    db.commit()
                except Exception:  # noqa: BLE001
                    db.rollback()
            errores.append({"id": fr.id if fr else None, "error": str(exc)[:200]})
    return {"procesadas": len(frs), "generadas": generadas, "errores": errores}


@router.get("", response_model=list[FacturaRecurrenteOut])
def listar_recurrentes(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    frs = db.query(FacturaRecurrente).order_by(FacturaRecurrente.activo.desc(), FacturaRecurrente.id.desc()).all()
    return [_serializar(db, fr) for fr in frs]


@router.get("/proximas")
def proximas_recurrentes(
    dias: int = 30,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    hoy = date.today()
    limite = hoy + timedelta(days=dias)
    frs = db.query(FacturaRecurrente).filter(FacturaRecurrente.activo == True).all()  # noqa: E712
    return [
        {
            "id": fr.id,
            "cliente": (db.get(Cliente, fr.cliente_id).nombre if fr.cliente_id else None),
            "descripcion": fr.descripcion,
            "periodicidad": fr.periodicidad,
            "proxima_fecha": fr.proxima_fecha,
            "total_estimado": _serializar(db, fr)["total_estimado"],
        }
        for fr in frs
        if fr.proxima_fecha and fr.proxima_fecha <= limite
    ]


@router.post("", response_model=FacturaRecurrenteOut, status_code=201)
def crear_recurrente(
    data: FacturaRecurrenteCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    if data.periodicidad not in PERIODICIDADES:
        raise HTTPException(400, f"Periodicidad inválida ({', '.join(PERIODICIDADES)})")
    if data.periodicidad == "semanal" and not (0 <= data.dia <= 6):
        raise HTTPException(400, "Para semanal el día debe ser 0 (domingo) a 6 (sábado)")
    if data.periodicidad in ("mensual", "quincenal") and not (1 <= data.dia <= 28):
        raise HTTPException(400, "Para mensual/quincenal el día debe ser 1 a 28")
    items = _validar_items(db, data.items)
    fr = FacturaRecurrente(
        empresa_id=data.empresa_id,
        cliente_id=data.cliente_id,
        sucursal_id=data.sucursal_id,
        usuario_id=usuario.id,
        periodicidad=data.periodicidad,
        dia=data.dia,
        descripcion=data.descripcion,
        items=items,
        descuento_global=data.descuento_global,
        tipo=data.tipo,
        medio_pago=data.medio_pago,
        proxima_fecha=data.proxima_fecha or date.today(),
        observaciones=data.observaciones,
    )
    db.add(fr)
    db.commit()
    db.refresh(fr)
    return _serializar(db, fr)


@router.put("/{fr_id}", response_model=FacturaRecurrenteOut)
def actualizar_recurrente(
    fr_id: int,
    data: FacturaRecurrenteUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    fr = db.get(FacturaRecurrente, fr_id)
    if not fr:
        raise HTTPException(404, "Factura recurrente no encontrada")
    campos = data.model_dump(exclude_unset=True)
    if "periodicidad" in campos and campos["periodicidad"] not in PERIODICIDADES:
        raise HTTPException(400, "Periodicidad inválida")
    if "items" in campos and campos["items"] is not None:
        campos["items"] = _validar_items(db, campos["items"])
    for k, v in campos.items():
        setattr(fr, k, v)
    db.commit()
    db.refresh(fr)
    return _serializar(db, fr)


@router.delete("/{fr_id}")
def eliminar_recurrente(
    fr_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    fr = db.get(FacturaRecurrente, fr_id)
    if not fr:
        raise HTTPException(404, "Factura recurrente no encontrada")
    fr.activo = False  # baja lógica: conserva historial
    db.commit()
    return {"ok": True, "id": fr_id}


@router.post("/{fr_id}/ejecutar")
def ejecutar_recurrente_ahora(
    fr_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    fr = db.get(FacturaRecurrente, fr_id)
    if not fr:
        raise HTTPException(404, "Factura recurrente no encontrada")
    if not fr.activo:
        raise HTTPException(400, "La factura recurrente está inactiva")
    venta = _ejecutar(db, fr)
    return {"ok": True, "venta_id": venta.id, "numero": venta.numero, "total": float(venta.total or 0)}


# ---------------- Recordatorios de cobro ----------------


def _texto_recordatorio(db: Session, cliente, saldo: float, ventas: list) -> str:
    emp = db.query(Empresa).order_by(Empresa.id).first()
    nombre = (emp.razon_social or emp.nombre or "Negocio").strip().upper() if emp else "NEGOCIO"
    lineas = "\n".join(f"• {v['numero']}: ${v['saldo']:,.0f}" for v in ventas[:6])
    url = obtener_config(db, "pos.url_publica", "").strip().rstrip("/")
    vinculo = f"\n🔗 Pague aquí: {url}/publico/tirilla/?saldo={saldo:,.0f}" if url else ""
    return (
        f"⏰ *{nombre}*\nRecordatorio de pago\n"
        f"{'-' * 28}\nEstimado/a {cliente.nombre}:\n"
        f"tiene un saldo pendiente de *${saldo:,.0f}* en las siguientes facturas:\n\n"
        f"{lineas}\n\nAgradecemos su pronto pago. 🙏{vinculo}"
    )


def _enviar_recordatorios(db: Session, dias_mora: int, medio: str = "whatsapp") -> dict:
    corte = datetime.combine(date.today() - timedelta(days=max(0, int(dias_mora))), datetime.min.time())
    ventas = (
        db.query(Venta)
        .filter(
            Venta.tipo == "credito",
            Venta.estado == "completada",
            Venta.saldo > 0,
            Venta.created_at < corte,
        )
        .all()
    )
    por_cliente: dict[int, dict] = {}
    for v in ventas:
        if not v.cliente_id:
            continue
        c = db.get(Cliente, v.cliente_id)
        if not c:
            continue
        if c.id not in por_cliente:
            por_cliente[c.id] = {"cliente": c.nombre, "telefono": c.telefono, "saldo": 0.0, "ventas": []}
        saldo = float(v.saldo or 0)
        por_cliente[c.id]["saldo"] += saldo
        por_cliente[c.id]["ventas"].append({"numero": v.numero, "saldo": round(saldo, 2)})

    enviados = 0
    resultado = []
    for cid, info in por_cliente.items():
        cliente = db.get(Cliente, cid)
        if medio == "whatsapp" and info["telefono"]:
            enviar_whatsapp(
                db,
                info["telefono"],
                _texto_recordatorio(db, cliente, info["saldo"], info["ventas"]),
                plantilla="recordatorio_cobro",
                referencia=f"cobro-{cid}-{date.today()}",
            )
            enviados += 1
        resultado.append(info)
    return {"enviados": enviados, "clientes": resultado}


@router.post("/recordatorios/enviar", response_model=RecordatorioOut)
def enviar_recordatorios_manual(
    data: RecordatorioEnviar,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    return _enviar_recordatorios(db, data.dias_mora, data.medio)


def procesar_recordatorios(db: Session) -> dict:
    """Scheduler diario de recordatorios de cobro por WhatsApp."""
    if not config_bool(db, "cartera.recordatorio_activo"):
        return {"activo": False}
    dias = int(obtener_config(db, "cartera.recordatorio_dias", "5") or 5)
    hora = obtener_config(db, "cartera.recordatorio_hora", "09:00").strip()[:5]
    ahora = datetime.now()
    if ahora.strftime("%H:%M") != hora:
        return {"activo": True, "hora": hora}
    ultimo = obtener_config(db, "cartera.ultimo_recordatorio", "")
    if ultimo == str(date.today()):
        return {"ya_enviado": True}
    resumen = _enviar_recordatorios(db, dias, "whatsapp")
    guardar_config(db, "cartera.ultimo_recordatorio", str(date.today()))
    return {"activo": True, **resumen}