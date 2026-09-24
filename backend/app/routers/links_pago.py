"""Links de pago: enlace pÃºblico de cobro que el comercio comparte por WhatsApp.

- CRUD autenticado bajo /links-pago (crear, listar, marcar-pagado, cancelar).
- PÃ¡gina pÃºblica /publico/pago/{token} con los QR de pago configurados
  (Nequi/Daviplata/Bre-B vÃ­a /publico/qr-pago/{tipo}) y botÃ³n de confirmaciÃ³n.
"""
import secrets
from datetime import date, datetime, time
from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Cliente, Empresa, LinkPago, Usuario
from ..schemas.links_pago import LinkPagoCreate, LinkPagoOut
from ..wa import obtener_config

router = APIRouter(prefix="/links-pago", tags=["links de pago"])
pub = APIRouter(prefix="/publico", tags=["publico"])

ESTADOS = ("activo", "pagado", "cancelado", "vencido")


def _token():
    return secrets.token_urlsafe(9)[:12].replace("-", "").replace("_", "")


def _empresa_origen(db):
    return db.query(Empresa).order_by(Empresa.id).first()


def _url_publica(db):
    return obtener_config(db, "pos.url_publica", "").strip().rstrip("/")


def _link_url(db, link):
    base = _url_publica(db)
    if not base:
        return ""
    return f"{base}/publico/pago/{link.token}"


def _estado_actual(link):
    if link.estado == "activo" and link.vence and link.vence < date.today():
        return "vencido"
    return link.estado


def _serializar(db, link, extra_url=True):
    cliente = db.get(Cliente, link.cliente_id) if link.cliente_id else None
    return {
        "id": link.id,
        "empresa_id": link.empresa_id,
        "usuario_id": link.usuario_id,
        "cliente_id": link.cliente_id,
        "cliente_nombre": cliente.nombre if cliente else None,
        "token": link.token,
        "descripcion": link.descripcion,
        "monto": float(link.monto or 0),
        "items": link.items or [],
        "medio": link.medio or "",
        "estado": _estado_actual(link),
        "vence": link.vence.isoformat() if link.vence else None,
        "confirmado_fecha": link.confirmado_fecha.isoformat() if link.confirmado_fecha else None,
        "venta_id": link.venta_id,
        "visitas": link.visitas or 0,
        "url": _link_url(db, link) if extra_url else None,
        "created_at": link.created_at.isoformat() if link.created_at else None,
    }


@router.post("/", response_model=LinkPagoOut)
def crear_link(data: LinkPagoCreate, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    empresa = _empresa_origen(db)
    if not empresa:
        raise HTTPException(400, "No hay negocio configurado")
    if data.monto <= 0 and not data.items:
        raise HTTPException(400, "Indique un monto mayor a cero")
    if data.cliente_id and not db.get(Cliente, data.cliente_id):
        raise HTTPException(404, "Cliente no encontrado")
    token = _token()
    while db.query(LinkPago).filter(LinkPago.token == token).first():
        token = _token()
    vence = None
    if data.vence_dias:
        vence = date.today() + __import__("datetime").timedelta(days=max(1, data.vence_dias))
    link = LinkPago(
        empresa_id=empresa.id,
        usuario_id=usuario.id,
        cliente_id=data.cliente_id,
        token=token,
        descripcion=data.descripcion,
        monto=data.monto,
        items=[i.model_dump() if hasattr(i, "model_dump") else dict(i) for i in (data.items or [])],
        medio=data.medio,
        estado="activo",
        vence=vence,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return _serializar(db, link)


@router.get("/", response_model=list[LinkPagoOut])
def listar_links(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    empresa = _empresa_origen(db)
    if not empresa:
        raise HTTPException(400, "No hay negocio configurado")
    links = (
        db.query(LinkPago)
        .filter(LinkPago.empresa_id == empresa.id)
        .order_by(LinkPago.id.desc())
        .all()
    )
    return [_serializar(db, l) for l in links]


@router.post("/{link_id}/pagar", response_model=LinkPagoOut)
def marcar_pagado(link_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    link = db.get(LinkPago, link_id)
    if not link:
        raise HTTPException(404, "Link no encontrado")
    if link.estado != "activo":
        raise HTTPException(400, f"El link ya estÃ¡ en estado '{link.estado}'")
    venta_id = _generar_venta(db, link, usuario)
    link.estado = "pagado"
    link.confirmado_fecha = datetime.now()
    link.venta_id = venta_id
    db.commit()
    db.refresh(link)
    return _serializar(db, link)


def _generar_venta(db, link, usuario):
    """Si el link trae productos, crea la venta de contado y descuenta inventario."""
    items_con_producto = [i for i in (link.items or []) if (i or {}).get("producto_id")]
    if not items_con_producto:
        return None
    from ..models import Sucursal
    from ..schemas.ventas import VentaCreate, VentaDetalleCreate, VentaPagoCreate

    sucursal_id = usuario.sucursal_id
    if not sucursal_id:
        suc = db.query(Sucursal).order_by(Sucursal.id).first()
        sucursal_id = suc.id if suc else None
    if not sucursal_id:
        raise HTTPException(400, "No hay sucursal configurada para generar la venta")

    detalle = []
    total_items = 0.0
    for i in items_con_producto:
        prec = float(i.get("precio") or 0) or None
        cant = float(i.get("cantidad") or 1) or 1
        if prec is None:
            prod = db.get(_producto_cls(), int(i["producto_id"]))
            prec = float(getattr(prod, "precio_venta", 0) or 0) if prod else 0
        total_items += prec * cant
        detalle.append(VentaDetalleCreate(producto_id=int(i["producto_id"]), cantidad=cant, precio=prec))

    monto = float(link.monto or 0) or round(total_items, 2)
    data = VentaCreate(
        empresa_id=link.empresa_id,
        sucursal_id=sucursal_id,
        cliente_id=link.cliente_id,
        tipo="contado",
        nota=f"Link de pago {link.token}: {link.descripcion or 'cobro por link'}".strip(),
        detalle=detalle,
        pagos=[VentaPagoCreate(medio=(link.medio or "efectivo"), monto=monto)],
    )
    from ..routers.ventas import crear_venta_interna

    venta = crear_venta_interna(db, data, usuario)
    db.commit()
    return venta.id


def _producto_cls():
    from ..models import Producto

    return Producto


@router.post("/{link_id}/cancelar", response_model=LinkPagoOut)
def cancelar_link(link_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    link = db.get(LinkPago, link_id)
    if not link:
        raise HTTPException(404, "Link no encontrado")
    if link.estado not in ("activo", "vencido"):
        raise HTTPException(400, f"No se puede cancelar un link en estado '{link.estado}'")
    link.estado = "cancelado"
    db.commit()
    db.refresh(link)
    return _serializar(db, link)


# ---------- PÃ¡gina pÃºblica ----------
_MEDIOS_QR = (("nequi", "ðŸ’š", "Nequi"), ("daviplata", "ðŸ”µ", "Daviplata"), ("breb", "ðŸŸ©", "Bre-B"))


def _html(negocio, cuerpo):
    logo = ""
    if negocio and getattr(negocio, "logo", None):
        logo = f'<img class="logo" src="{escape(negocio.logo)}" alt="logo" onerror="this.style.display=\'none\'" />'
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#059669">
<meta name="robots" content="noindex">
<title>{escape((negocio.razon_social or negocio.nombre) if negocio else "Pago")}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; font-family: system-ui, -apple-system, sans-serif; }}
body {{ background:#f3f6f4; min-height:100vh; display:flex; flex-direction:column; align-items:center; padding:20px 14px calc(24px + env(safe-area-inset-bottom)); color:#10231b; }}
.card {{ background:#fff; border-radius:18px; width:100%; max-width:420px; overflow:hidden; box-shadow:0 14px 38px -18px rgba(6,78,59,.25); }}
.top {{ background:linear-gradient(135deg,#047857,#059669); color:#fff; padding:20px 18px; }}
.top .neg {{ font-size:13px; opacity:.9; }}
.top h1 {{ font-size:20px; margin-top:4px; }}
.logo {{ width:44px; height:44px; border-radius:10px; object-fit:cover; float:right; }}
.body {{ padding:18px; }}
.estado-badge {{ display:inline-block; padding:4px 12px; border-radius:999px; font-size:12px; font-weight:700; }}
.estado-activo {{ background:#d1fae5; color:#065f46; }}
.estado-pagado {{ background:#e0e7ff; color:#3730a3; }}
.estado-cancelado, .estado-vencido {{ background:#fee2e2; color:#991b1b; }}
.desc {{ color:#33443c; font-size:15px; margin:10px 0 14px; }}
.items {{ border-top:1px dashed #d7e3dc; margin:12px 0; padding-top:10px; }}
.item {{ display:flex; justify-content:space-between; font-size:13px; color:#33443c; padding:4px 0; }}
.total {{ display:flex; justify-content:space-between; align-items:baseline; border-top:2px solid #059669; margin-top:14px; padding-top:12px; }}
.total b {{ font-size:24px; color:#047857; }}
.pay-opt {{ display:flex; gap:8px; margin:16px 0 10px; flex-wrap:wrap; }}
.pay-opt button {{ flex:1 1 90px; padding:11px 6px; border-radius:12px; border:1px solid #cfe0d6; background:#f7faf8; color:#10231b; font-weight:700; cursor:pointer; font-size:13px; }}
.pay-opt button.on {{ background:#059669; color:#fff; border-color:#059669; }}
.qr-box {{ display:none; justify-content:center; background:#fff; border:1px solid #cfe0d6; border-radius:14px; padding:14px; margin:10px 0; }}
.qr-box.on {{ display:flex; }}
.qr-box img {{ width:240px; height:240px; }}
.nota {{ font-size:12.5px; color:#5b6b63; line-height:1.5; }}
.btn-wa {{ display:block; margin-top:14px; background:#25d366; color:#fff; text-align:center; text-decoration:none; font-weight:800; border-radius:12px; padding:13px; font-size:15px; }}
.btn-ghost {{ width:100%; margin-top:8px; background:#eef4f0; color:#065f46; border:0; border-radius:12px; padding:11px; font-weight:700; cursor:pointer; }}
.mensaje {{ text-align:center; padding:44px 10px; }}
.mensaje .big {{ font-size:22px; font-weight:800; }}
.mensaje .ico {{ font-size:44px; }}
</style></head><body>{cuerpo}</body></html>"""


@pub.get("/pago/{token}", response_class=HTMLResponse)
def pagina_pago(token: str, db: Session = Depends(get_db)):
    negocio = _empresa_origen(db)
    link = db.query(LinkPago).filter(LinkPago.token == token).first()
    if not link:
        return HTMLResponse(
            _html(negocio, '<div class="card"><div class="body"><div class="mensaje"><div class="ico">ðŸ”</div><div class="big">Link no encontrado</div><p class="nota" style="margin-top:8px">Verifica el enlace o solicÃ­talo de nuevo.</p></div></div></div>'),
            status_code=404,
        )
    link.visitas = (link.visitas or 0) + 1
    db.commit()

    estado = _estado_actual(link)
    if estado == "vencido":
        link.estado = "vencido"
        db.commit()

    nombre_negocio = escape((negocio.razon_social or negocio.nombre) if negocio else "Mi negocio")
    monto = float(link.monto or 0)
    monto_txt = f"${monto:,.0f}".replace(",", ".")

    if estado == "pagado":
        cuerpo = f"""<div class="card"><div class="top"><span class="estado-badge estado-pagado">PAGADO</span><br><div class="neg">{nombre_negocio}</div><h1>Pago confirmado</h1></div>
<div class="body"><div class="mensaje"><div class="ico">âœ…</div>
<div class="big">{monto_txt}</div>
<p class="nota" style="margin-top:8px">{escape(link.descripcion or "")}</p></div></div></div>"""
        return HTMLResponse(_html(negocio, cuerpo))

    if estado in ("cancelado", "vencido"):
        etq = "CANCELADO" if estado == "cancelado" else "VENCIDO"
        cls = "estado-cancelado" if estado == "cancelado" else "estado-vencido"
        cuerpo = f"""<div class="card"><div class="top"><span class="estado-badge {cls}">{etq}</span><br><div class="neg">{nombre_negocio}</div><h1>Link no disponible</h1></div>
<div class="body"><div class="mensaje"><div class="ico">â›”</div><div class="big">{monto_txt}</div>
<p class="nota" style="margin-top:8px">{escape(link.descripcion or "")}</p>
<p class="nota" style="margin-top:10px">Este enlace ya no estÃ¡ activo. Contacta al negocio para gestionar tu pago.</p></div></div></div>"""
        return HTMLResponse(_html(negocio, cuerpo))

    # Activo â†’ panel de pago
    items_html = ""
    if link.items:
        lineas = []
        for it in link.items:
            it = it or {}
            cant = it.get("cantidad", 1) or 1
            prec = it.get("precio") or 0
            nom = it.get("nombre") or (f"Producto {it.get('producto_id')}" if it.get("producto_id") else "")
            sub = float(cant or 1) * float(prec or 0)
            lineas.append(f'<div class="item"><span>{float(cant):g} Ã— {escape(str(nom))}</span><b>${sub:,.0f}</b></div>'.replace(",", "."))
        items_html = '<div class="items">' + "".join(lineas) + "</div>"

    medios_html = ""
    for tipo, ico, etq in _MEDIOS_QR:
        if obtener_config(db, f"pagos.qr_{tipo}", "").strip():
            medios_html += f'<button data-tipo="{tipo}" onclick="qr(\'{tipo}\')">{ico} {etq}</button>'

    wa_tel = ""
    tel = (getattr(negocio, "telefono", "") or obtener_config(db, "wa.numero", "")).strip()
    if tel.startswith("+"):
        wa_tel = tel[1:].replace(" ", "").replace("-", "")
    else:
        wa_tel = tel.replace(" ", "").replace("-", "")
    wa_tel = "57" + wa_tel.lstrip("0") if not wa_tel.startswith("57") else wa_tel
    wa_msg = f"Hola {nombre_negocio}, acabo de realizar el pago del enlace ({token}) por {monto_txt}. {escape(link.descripcion or '')}".replace(" ", "%20")
    btn_wa = f'<a class="btn-wa" href="https://wa.me/{wa_tel}?text={wa_msg}">Enviar comprobante por WhatsApp</a>' if wa_tel else ""

    cuerpo = f"""<div class="card"><div class="top"><div class="neg">{nombre_negocio}</div><h1>Pagar ahora</h1></div>
<div class="body">
<span class="estado-badge estado-activo">ACTIVO</span>
<div class="desc">{escape(link.descripcion or "") or "Cobro por enlace"}</div>
{items_html}
<div class="total"><span>Total a pagar</span><b>{monto_txt}</b></div>
<div class="pay-opt">{medios_html}</div>
<div class="qr-box" id="qr"><img id="qrimg" src="" alt="QR de pago" /><button class="btn-ghost" onclick="document.getElementById('qr').classList.remove('on')">Cerrar</button></div>
<p class="nota">1ï¸âƒ£ Elige tu medio de pago y escanea el cÃ³digo QR.<br>2ï¸âƒ£ Haz la transferencia desde tu app.<br>3ï¸âƒ£ EnvÃ­a el comprobante para confirmar el pago.</p>
{btn_wa}
</div></div>
<script>
var SEL = null;
function qr(t) {{
  SEL = t;
  document.querySelectorAll('.pay-opt button').forEach(b => b.classList.toggle('on', b.dataset.tipo === t));
  document.getElementById('qrimg').src = '/publico/qr-pago/' + t + '?ts=' + Date.now();
  document.getElementById('qr').classList.add('on');
}}
var init = document.querySelector('.pay-opt button');
if (init) init.click();
</script>"""
    return HTMLResponse(_html(negocio, cuerpo))