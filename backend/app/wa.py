"""Servicios de WhatsApp y notificaciones automáticas.

El envío es simulado: se registra cada mensaje en `mensajes_whatsapp`
(que ya alimenta la bandeja de Integraciones) y los comprobantes llevan
enlaces `wa.me`. Pensado para conectar después un proveedor real
(Twilio / Meta Cloud API / WASSER) sin cambiar los callers.
"""
import threading
from datetime import date, datetime

from .database import get_session
from .models import (
    Cliente,
    Configuracion,
    DocumentoFiscal,
    Empresa,
    MensajeWhatsapp,
    Producto,
    Stock,
    Venta,
    VentaDetalle,
    VentaPago,
)


# ---------- Configuración clave/valor ----------
def obtener_config(db, clave, default=""):
    c = db.query(Configuracion).filter(Configuracion.clave == clave).first()
    if c and c.valor not in (None, ""):
        return c.valor
    return default


def guardar_config(db, clave, valor):
    c = db.query(Configuracion).filter(Configuracion.clave == clave).first()
    if c:
        c.valor = str(valor)
    else:
        db.add(Configuracion(clave=clave, valor=str(valor), descripcion="WhatsApp y notificaciones"))
    db.commit()


def config_bool(db, clave, default=False):
    v = str(obtener_config(db, clave, "1" if default else "0")).strip().lower()
    return v in ("1", "true", "si", "sí", "on", "yes")


def _empresa(db):
    return db.query(Empresa).order_by(Empresa.id).first()


def _telefono_limpio(tel: str) -> str:
    tel = (tel or "").strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not tel:
        return ""
    if tel.startswith("+"):
        tel = tel[1:]
    if tel.startswith("00"):
        tel = tel[2:]
    if tel.startswith("0"):
        tel = "57" + tel[1:]
    if tel.isdigit() and len(tel) == 10 and tel.startswith("3"):
        tel = "57" + tel
    if tel.isdigit() and len(tel) >= 10:
        return tel
    return ""


def enviar_whatsapp(db, telefono, contenido, plantilla="aviso", referencia="", empresa_id=None):
    """Registra un mensaje saliente (envío simulado) y devuelve el registro."""
    tel = _telefono_limpio(telefono)
    if not tel or not contenido:
        return None
    emp = db.get(Empresa, empresa_id) if empresa_id else _empresa(db)
    if not emp:
        return None
    msg = MensajeWhatsapp(
        empresa_id=emp.id,
        telefono=tel,
        plantilla=plantilla,
        contenido=str(contenido)[:4000],
        estado="enviado",
        referencia=referencia or "",
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


# ---------- Textos ----------
def texto_recibo_venta(db, venta):
    emp = _empresa(db)
    nombre = (emp.razon_social or emp.nombre or "Negocio").strip().upper() if emp else "NEGOCIO"
    total = float(venta.total or 0)
    fec = venta.created_at or datetime.now()
    lineas = []
    for d in db.query(VentaDetalle).filter(VentaDetalle.venta_id == venta.id).order_by(VentaDetalle.id).all():
        p = db.get(Producto, d.producto_id) if d.producto_id else None
        nm = (p.nombre if p else f"Producto {d.producto_id}").capitalize()
        lineas.append(f"• {float(d.cantidad or 1):g} × {nm}  = ${float(d.subtotal or 0):,.0f}")
    medios = ", ".join(sorted({str(p.medio or "—").upper() for p in db.query(VentaPago).filter(VentaPago.venta_id == venta.id).all()}))
    credito = ""
    saldo = float(venta.saldo or 0)
    if venta.tipo == "credito" and saldo > 0:
        credito = f"\n🧾 A crédito · saldo pendiente ${saldo:,.0f}"
    fe = (
        db.query(DocumentoFiscal)
        .filter(DocumentoFiscal.venta_id == venta.id, DocumentoFiscal.anulado == False)
        .order_by(DocumentoFiscal.id)
        .first()
    )
    fe_linea = f"\n📑 Factura electrónica: {fe.numero}" if fe else ""
    url = obtener_config(db, "pos.url_publica", "").strip().rstrip("/")
    llave = obtener_config(db, "publico.llave", "publico")
    link = ""
    if url:
        link = f"\n🔗 Tirilla: {url}/publico/tirilla/{venta.id}?llave={llave}"
    return (
        f"🧾 *{nombre}*\nComprobante {venta.numero}\n"
        f"{fec.strftime('%d/%m/%Y %H:%M')}\n"
        f"{'-' * 28}\n" + "\n".join(lineas) +
        f"\n{'-' * 28}\n✅ *TOTAL: ${total:,.0f}*\n"
        f"Medio(s): {medios}\n" if medios else ""
    ) + credito + fe_linea + link + "\n\n_¡Gracias por su compra!_"


def _ventas_hoy(db):
    inicio = datetime.combine(date.today(), datetime.min.time())
    return (
        db.query(Venta)
        .filter(Venta.created_at >= inicio, Venta.estado != "anulada")
        .all()
    )


def texto_resumen_diario(db):
    emp = _empresa(db)
    nombre = (emp.razon_social or emp.nombre or "Negocio").strip().upper() if emp else "NEGOCIO"
    ventas = _ventas_hoy(db)
    total = sum(float(v.total or 0) for v in ventas)
    docs = (
        db.query(DocumentoFiscal)
        .filter(DocumentoFiscal.created_at >= datetime.combine(date.today(), datetime.min.time()))
        .count()
    )
    por_medio = {}
    for v in ventas:
        for p in db.query(VentaPago).filter(VentaPago.venta_id == v.id).all():
            m = str(p.medio or "—").upper().replace("_", " ")
            por_medio[m] = round(por_medio.get(m, 0) + float(p.monto or 0))
    medios = "\n".join(f"   💳 {m}: ${val:,.0f}" for m, val in sorted(por_medio.items(), key=lambda x: -x[1])) or "   —"
    bajos = _bajo_stock(db, limite=8)
    hoy = date.today().strftime("%d/%m/%Y")
    enlace = f"\n✅ Facturas: {docs}" if config_bool(db, "facturacion.habilitar", True) else ""
    return (
        f"📊 *RESUMEN DEL DÍA — {nombre}*\n"
        f"📅 {hoy}\n"
        f"{'-' * 28}\n"
        f"🛒 Ventas: {len(ventas)}\n"
        f"💰 Total: ${total:,.0f}\n{enlace}\n"
        f"{'-' * 28}\n"
        f"*Por medio de pago:*\n{medios}\n"
        f"{'-' * 28}\n"
        f"⚠️ *Bajo inventario:*\n{' '.join(bajos) if bajos else '—Ninguno ⭐'}"
    )


def _bajo_stock(db, limite=8):
    prods = (
        db.query(Producto)
        .filter(Producto.activo == True, Producto.es_servicio == False)
        .all()
    )
    stocks = {s.producto_id: s for s in db.query(Stock).all()}
    bajos = []
    for p in prods:
        min_stock = float(p.punto_reorden or p.stock_minimo or 0)
        s = stocks.get(p.id)
        exist = float(s.existencias or 0) if s else 0.0
        if min_stock > 0 and exist <= min_stock:
            bajos.append(f"   • {p.nombre}: {exist:g} (mín {min_stock:g})")
    return bajos[:limite]


def texto_alertas(db):
    emp = _empresa(db)
    nombre = (emp.razon_social or emp.nombre or "Negocio").strip().upper() if emp else "NEGOCIO"
    bajos = _bajo_stock(db, limite=10)
    negativos = []
    stocks = db.query(Stock).all()
    for s in stocks:
        if float(s.existencias or 0) < 0:
            p = db.get(Producto, s.producto_id)
            negativos.append(f"   • {p.nombre if p else s.producto_id}: {float(s.existencias):g} (suc {s.sucursal_id})")
    ventas = _ventas_hoy(db)
    total_hoy = sum(float(v.total or 0) for v in ventas)
    mensaje = (
        f"🚨 *ALERTAS — {nombre}*\n"
        f"📅 {date.today().strftime('%d/%m/%Y %H:%M')}\n"
        f"{'-' * 28}\n"
        f"🛒 Hoy: {len(ventas)} ventas / ${total_hoy:,.0f}\n"
    )
    if negativos:
        mensaje += f"\n⚠️ *Inventario negativo:*\n" + "\n".join(negativos[:6]) + "\n"
    if bajos:
        mensaje += f"\n📉 *Bajo inventario:*\n" + "\n".join(bajos) + "\n"
    pendiente = (
        db.query(DocumentoFiscal)
        .filter(DocumentoFiscal.anulado == False, DocumentoFiscal.cufe == None)
        .count()
    )
    if pendiente:
        mensaje += f"\n🧾 Facturas pendientes de validar: {pendiente}\n"
    if not (negativos or bajos or pendiente):
        mensaje += "\nTodo en orden ✅\n"
    return mensaje


def _productos_con_stock(db):
    return db.query(Producto).filter(Producto.activo == True, Producto.es_servicio == False).all()


# ---------- Programador ----------
_bg_thread = None


def _loop():
    import time as _time

    while True:
        try:
            db = get_session()
            try:
                ahora = datetime.now()
                # Reporte diario a la hora configurada (por defecto 21:00)
                if config_bool(db, "pos.reporte_diario"):
                    hora = obtener_config(db, "pos.hora_resumen", "21:00").strip()
                    tel = obtener_config(db, "pos.telefono_notificaciones", "").strip()
                    if tel and hora and ahora.strftime("%H:%M") == hora[:5]:
                        ultimo = obtener_config(db, "pos.ultimo_reporte", "")
                        if ultimo != str(date.today()):
                            enviar_whatsapp(
                                db, tel, texto_resumen_diario(db),
                                plantilla="resumen_diario",
                                referencia=f"resumen-{date.today()}",
                            )
                            guardar_config(db, "pos.ultimo_reporte", str(date.today()))
                # Alertas automáticas una vez por hora (minuto 0)
                if config_bool(db, "pos.alertas_whatsapp") and ahora.minute == 0:
                    tel = obtener_config(db, "pos.telefono_notificaciones", "").strip()
                    if tel:
                        clave_hora = ahora.strftime("%Y-%m-%d %H")
                        ultimo = obtener_config(db, "pos.ultima_alerta", "")
                        if ultimo != clave_hora:
                            enviar_whatsapp(
                                db, tel, texto_alertas(db),
                                plantilla="alertas",
                                referencia=f"alerta-{clave_hora}",
                            )
                            guardar_config(db, "pos.ultima_alerta", clave_hora)
            finally:
                db.close()
        except Exception:
            pass
        _time.sleep(60)


def iniciar_scheduler():
    global _bg_thread
    if _bg_thread and _bg_thread.is_alive():
        return
    _bg_thread = threading.Thread(target=_loop, daemon=True, name="wa-scheduler")
    _bg_thread.start()


# ---------- Recibo automático de venta ----------
def _dispatch_recibo(venta_id: int):
    try:
        db = get_session()
        try:
            venta = db.get(Venta, venta_id)
            if not venta:
                return
            if not config_bool(db, "pos.recibo_whatsapp"):
                return
            if not venta.cliente_id:
                return
            cliente = db.get(Cliente, venta.cliente_id)
            tel = _telefono_limpio(cliente.telefono) if cliente else ""
            if not tel:
                return
            enviar_whatsapp(
                db,
                tel,
                texto_recibo_venta(db, venta),
                plantilla="recibo_venta",
                referencia=f"venta-{venta.id}",
                empresa_id=venta.empresa_id,
            )
        finally:
            db.close()
    except Exception:
        pass


def enviar_recibo_venta_async(venta_id: int):
    threading.Thread(target=_dispatch_recibo, args=(venta_id,), daemon=True).start()


def lanzar_recibo_si_configurado(db, venta):
    """Llamado desde crear_venta tras el commit. Lanza en segundo plano."""
    if venta.cliente_id and config_bool(db, "pos.recibo_whatsapp"):
        enviar_recibo_venta_async(venta.id)