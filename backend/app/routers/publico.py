"""Endpoint públicos para atención sin login:

- Menú digital por mesa (código QR) y pedidos directos a cocina.
- Kiosko de autoservicio (autopago): catálogo, carrito y venta al contado.
- Tirilla pública de comprobante (enlace para WhatsApp/línea de banco).
- Generador de códigos QR y pantalla de pagos (Nequi/Daviplata/Bre-B).

Las operaciones de escritura ("pedido", "venta") exigen la llave pública
(config `publico.llave`), que viaja incrustada en la URL/HTML del QR.
"""
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..dian import NIT_CONSUMIDOR_FINAL
from ..wa import obtener_config

router = APIRouter(prefix="/publico", tags=["publico"])

try:
    import qrcode as _qrcode
except Exception:  # pragma: no cover
    _qrcode = None


# ---------- Auxiliares ----------
_MODELO_A_TIPO = {
    1: "restaurante",
    2: "ferreteria",
    3: "minimarket",
    4: "bar",
    5: "distribuidora",
    6: "general",
}
_TIPOS_COMIDA = {"restaurante", "bar", "general"}
_TIPOS_RETAIL = {"ferreteria", "minimarket", "distribuidora"}


def _llave_ok(db, llave):
    if not llave:
        return False
    conf = obtener_config(db, "publico.llave", "publico")
    return llave in {conf, "publico", "mesa", "carta"}


def _tipo_publico(db):
    """Tipo de menú público según el modelo de negocio del establecimiento."""
    from ..plan import modelo_negocio_de_empresa

    emp = _empresa(db)
    if emp:
        m = modelo_negocio_de_empresa(emp, db)
        if m and m.id in _MODELO_A_TIPO:
            return _MODELO_A_TIPO[m.id]
        t = (emp.tipo_negocio or "").lower()
        if t in _TIPOS_COMIDA or t in _TIPOS_RETAIL:
            return t
    return "general"


def _empresa(db):
    from ..models import Empresa

    return db.query(Empresa).order_by(Empresa.id).first()


def _usuario_servicio(db):
    from ..models import Usuario

    u = (
        db.query(Usuario).filter(Usuario.es_admin == True).order_by(Usuario.id).first()
        or db.query(Usuario).order_by(Usuario.id).first()
    )
    if not u:
        raise HTTPException(503, "No hay usuarios configurados para el servicio público")
    return u


def _sucursal_default(db):
    from ..models import Sucursal

    return db.query(Sucursal).order_by(Sucursal.id).first()


def _catalogo(db):
    """Productos activos agrupados por categoría."""
    from ..models import Categoria, Producto

    emp = _empresa(db)
    prod_cats = {}
    for p in (
        db.query(Producto)
        .filter(Producto.activo == True)
        .order_by(Producto.nombre)
        .all()
    ):
        if emp and p.empresa_id and p.empresa_id != emp.id:
            continue
        cat_id = p.categoria_id if p.categoria_id else -1
        prod_cats.setdefault(cat_id, []).append(p)
    categorias = []
    if -1 in prod_cats:
        categorias.append(
            {
                "id": -1,
                "nombre": "Otros",
                "productos": [_p(d) for d in prod_cats.pop(-1)],
            }
        )
    for c in db.query(Categoria).filter(Categoria.activa == True).order_by(Categoria.nombre).all():
        if c.id in prod_cats:
            categorias.append(
                {"id": c.id, "nombre": c.nombre, "productos": [_p(p) for p in prod_cats.pop(c.id)]}
            )
    for rest in prod_cats.values():
        categorias.append(
            {"id": -1, "nombre": "Otros", "productos": [_p(p) for p in rest]}
        )
    return categorias


def _p(prod):
    imagen = ""
    if prod.imagen and isinstance(prod.imagen, str):
        if prod.imagen.startswith(("http://", "https://")):
            imagen = prod.imagen
    return {
        "id": prod.id,
        "nombre": prod.nombre,
        "descripcion": (prod.descripcion or "")[:180],
        "precio": round(float(prod.precio_venta or 0) * (1 + float(getattr(prod, "impuesto", 0) or 0) / 100), 2),
        "precio_final": round(float(prod.precio_venta or 0) * (1 + float(getattr(prod, "impuesto", 0) or 0) / 100), 2),
        "impuesto": float(getattr(prod, "impuesto", 0) or 0),
        "es_servicio": bool(getattr(prod, "es_servicio", False)),
        "imagen": imagen,
    }


def _negocio(db, mesa=None):
    emp = _empresa(db)
    from ..models import Salon

    salon = None
    if mesa is not None:
        salon = db.get(Salon, mesa.salon_id)
    return {
        "nombre": (emp.razon_social or emp.nombre) if emp else "Mi Negocio",
        "direccion": (emp.direccion if emp and emp.direccion else ""),
        "telefono": (emp.telefono if emp and emp.telefono else ""),
        "salon": salon.nombre if salon else "",
        "tipo": _tipo_publico(db),
    }


def _qr_png_bytes(texto, tam=320, box=None):
    if not _qrcode:
        raise HTTPException(503, "QR no disponible")
    import io

    qr = _qrcode.QRCode(
        box_size=box or max(4, int(tam / 40)),
        border=2,
        error_correction=_qrcode.constants.ERROR_CORRECT_M,
    )
    qr.add_data(texto)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def montar_qr_pago(db, tipo):
    """PNG del QR de pago (Nequi/Daviplata/Bre-B) según config `pagos.qr_{tipo}`.

    El valor puede ser: un texto (se convierte en QR), una URL de imagen
    (HTTP → se sirve como redirección) o un data-uri base64 (se decodifica).
    """
    import base64

    valor = obtener_config(db, f"pagos.qr_{tipo}", "").strip()
    if not valor:
        raise HTTPException(404, f"No hay QR configurado para {tipo}")
    if valor.startswith("data:image"):
        try:
            b64 = valor.split(",", 1)[1]
            return ("image/png", base64.b64decode(b64))
        except Exception:
            raise HTTPException(400, "Imagen QR inválida")
    if valor.lower().startswith("http://") or valor.lower().startswith("https://"):
        return ("text/url", valor)
    return ("image/png", _qr_png_bytes(valor, tam=480, box=10))


def _html_pagina(titulo, cuerpo):
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{escape(titulo)}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; font-family: system-ui, -apple-system, sans-serif; }}
body {{ background:#0f172a; color:#f1f5f9; min-height:100vh; padding-bottom: 86px; }}
header {{ position:sticky; top:0; z-index:20; background:#0f172a; border-bottom:1px solid #1e293b; padding:14px 16px; }}
h1 {{ font-size:19px; color:#34d399; }}
.sub {{ color:#94a3b8; font-size:13px; margin-top:2px; }}
.cat-wrap {{ position:sticky; top:64px; z-index:15; background:#0f172a; display:flex; gap:8px; overflow-x:auto; padding:10px 12px; border-bottom:1px solid #1e293b; }}
.chip {{ flex:0 0 auto; padding:8px 14px; border-radius:999px; background:#1e293b; color:#cbd5e1; font-size:13px; cursor:pointer; border:0; }}
.chip.on {{ background:#34d399; color:#062e1f; font-weight:700; }}
.sec {{ padding:14px 16px 0; }}
.sec h2 {{ color:#34d399; font-size:16px; margin-bottom:10px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:10px; }}
.card {{ background:#1e293b; border-radius:14px; padding:12px; display:flex; flex-direction:column; gap:6px; cursor:pointer; border:1px solid #242f3f; }}
.card b {{ font-size:14px; }}
.card .desc {{ color:#94a3b8; font-size:12px; height:30px; overflow:hidden; }}
.card .precio {{ color:#34d399; font-weight:800; font-size:14px; margin-top:auto; }}
.card .add {{ margin-top:8px; background:#34d399; color:#062e1f; border:0; border-radius:10px; padding:8px; font-weight:700; }}
.bar {{ position:fixed; bottom:0; left:0; right:0; z-index:30; padding:12px 14px calc(12px + env(safe-area-inset-bottom)); background:#0f172a; border-top:1px solid #1e293b; }}
.bar button {{ width:100%; background:#34d399; color:#062e1f; border:0; border-radius:12px; padding:14px; font-size:16px; font-weight:800; }}
.btn2 {{ background:#1e293b; color:#e2e8f0; border:1px solid #334155; border-radius:12px; padding:12px; font-size:15px; font-weight:700; cursor:pointer; }}
input, select {{ width:100%; background:#0b1220; border:1px solid #334155; color:#f1f5f9; border-radius:10px; padding:12px; font-size:15px; }}
label {{ display:block; font-size:12px; color:#94a3b8; margin:10px 0 4px; }}
.overlay {{ position:fixed; inset:0; background:rgba(2,6,23,.8); z-index:40; display:none; align-items:flex-end; }}
.overlay.on {{ display:flex; }}
.panel {{ width:100%; background:#111c33; border-radius:20px 20px 0 0; padding:18px 16px calc(18px + env(safe-area-inset-bottom)); max-height:86vh; overflow:auto; }}
.row {{ display:flex; align-items:center; gap:10px; justify-content:space-between; padding:10px 0; border-bottom:1px solid #1e293b; }}
.qty {{ display:flex; align-items:center; gap:10px; }}
.qty button {{ width:32px; height:32px; border-radius:9px; border:0; background:#1e293b; color:#34d399; font-size:18px; font-weight:700; }}
.total {{ display:flex; justify-content:space-between; font-size:18px; font-weight:800; color:#34d399; padding:14px 0; }}
.pay-opt {{ display:flex; gap:10px; margin:12px 0; }}
.pay-opt button {{ flex:1; padding:12px; border-radius:12px; border:1px solid #334155; background:#1e293b; color:#e2e8f0; font-weight:700; }}
.pay-opt button.on {{ background:#34d399; color:#062e1f; border-color:#34d399; }}
.qr-box {{ display:flex; justify-content:center; margin:10px 0; background:#fff; border-radius:14px; padding:12px; }}
.qr-box img {{ width:260px; height:260px; }}
.exito {{ text-align:center; padding:24px 8px; }}
.exito .big {{ font-size:22px; font-weight:800; color:#34d399; }}
.nota {{ font-size:13px; color:#94a3b8; line-height:1.5; }}
.hidden {{ display:none !important; }}
</style></head><body>{cuerpo}</body></html>"""


# ---------- Catálogo ----------
@router.get("/menu/{mesa_id}/datos")
def datos_menu(mesa_id: int, db: Session = Depends(get_db)):
    from ..models import Mesa

    mesa = db.get(Mesa, mesa_id)
    if not mesa:
        raise HTTPException(404, "Mesa no encontrada")
    return {
        "negocio": _negocio(db, mesa),
        "mesa": {"id": mesa.id, "nombre": mesa.nombre, "numero": mesa.numero},
        "categorias": _catalogo(db),
    }


@router.get("/mesas")
def mesas_publicas(db: Session = Depends(get_db)):
    from ..models import Mesa, Salon
    emp = _empresa(db)
    q = db.query(Mesa, Salon).join(Salon, Mesa.salon_id == Salon.id)
    if emp:
        q = q.filter(Salon.empresa_id == emp.id)
    mesas = []
    for m, s in q.order_by(Salon.nombre, Mesa.nombre).all():
        mesas.append({
            "id": m.id,
            "nombre": m.nombre,
            "numero": m.numero,
            "capacidad": m.capacidad,
            "estado": m.estado,
            "salon": s.nombre,
        })
    return mesas


@router.get("/carta/datos")
def datos_carta_general(db: Session = Depends(get_db)):
    from ..models import Mesa, Salon
    emp = _empresa(db)
    q = db.query(Mesa, Salon).join(Salon, Mesa.salon_id == Salon.id)
    if emp:
        q = q.filter(Salon.empresa_id == emp.id)
    mesas = []
    for m, s in q.order_by(Salon.nombre, Mesa.nombre).all():
        mesas.append({
            "id": m.id,
            "nombre": m.nombre,
            "numero": m.numero,
            "capacidad": m.capacidad,
            "estado": m.estado,
            "salon": s.nombre,
        })
    return {
        "negocio": _negocio(db),
        "categorias": _catalogo(db),
        "mesas": mesas,
    }


# ---------- Pedido desde la mesa ----------
class ItemPedido(BaseModel):
    producto_id: int
    cantidad: float = 1
    preparacion: str | None = None


class PedidoIn(BaseModel):
    llave: str
    mesa_id: int
    items: list[ItemPedido]
    cliente: str = ""
    telefono: str = ""


@router.post("/pedido", status_code=201)
def crear_pedido(data: PedidoIn, db: Session = Depends(get_db)):
    if not _llave_ok(db, data.llave):
        raise HTTPException(403, "Llave pública inválida")
    if not data.items:
        raise HTTPException(400, "El pedido está vacío")
    from ..models import Comanda, ComandaDetalle, Mesa, Producto, Salon

    mesa = db.get(Mesa, data.mesa_id)
    if not mesa:
        raise HTTPException(404, "Mesa no encontrada")
    for item in data.items:
        p = db.get(Producto, item.producto_id)
        if not p or not p.activo:
            raise HTTPException(400, f"Producto {item.producto_id} no disponible")
        if item.cantidad <= 0:
            raise HTTPException(400, "Las cantidades deben ser positivas")

    abierta = (
        db.query(Comanda)
        .join(Mesa, Comanda.mesa_id == Mesa.id)
        .join(Salon, Mesa.salon_id == Salon.id)
        .filter(Comanda.mesa_id == data.mesa_id, Comanda.estado == "abierta")
        .first()
    )
    usuario = _usuario_servicio(db)
    if abierta:
        nueva = False
        for item in data.items:
            p = db.get(Producto, item.producto_id)
            db.add(
                ComandaDetalle(
                    comanda_id=abierta.id,
                    producto_id=item.producto_id,
                    cantidad=item.cantidad,
                    precio=float(p.precio_venta or 0),
                    preparacion=item.preparacion,
                    entregado=False,
                )
            )
        comanda = abierta
    else:
        nueva = True
        comanda = Comanda(
            empresa_id=usuario.empresa_id,
            mesa_id=data.mesa_id,
            estado="abierta",
            mesero_id=usuario.id,
        )
        db.add(comanda)
        db.flush()
        comanda.numero = f"CM-{comanda.id:06d}"
        for item in data.items:
            p = db.get(Producto, item.producto_id)
            db.add(
                ComandaDetalle(
                    comanda_id=comanda.id,
                    producto_id=item.producto_id,
                    cantidad=item.cantidad,
                    precio=float(p.precio_venta or 0),
                    preparacion=item.preparacion,
                    entregado=False,
                )
            )
        if mesa.estado == "disponible":
            mesa.estado = "ocupada"
    db.commit()
    total = sum(float(d.precio or 0) * float(d.cantidad or 1) for d in comanda.detalle)
    return {
        "ok": True,
        "comanda_id": comanda.id,
        "numero": comanda.numero,
        "mesa": mesa.nombre,
        "total": round(total, 2),
        "nueva": nueva,
        "estado": comanda.estado,
    }


# ---------- Venta desde el kiosko ----------
class ItemKiosko(BaseModel):
    producto_id: int
    cantidad: float = 1


class VentaKiosko(BaseModel):
    llave: str
    items: list[ItemKiosko]
    medio: str = "efectivo"  # efectivo, nequi, daviplata, tarjeta
    recibido: float | None = None
    cliente_nombre: str = ""
    telefono: str = ""


@router.post("/venta", status_code=201)
def crear_venta_kiosko(data: VentaKiosko, db: Session = Depends(get_db)):
    if not _llave_ok(db, data.llave):
        raise HTTPException(403, "Llave pública inválida")
    if not data.items:
        raise HTTPException(400, "El carrito está vacío")
    from ..models import Cliente, Producto
    from ..schemas.ventas import VentaCreate, VentaDetalleCreate, VentaPagoCreate
    from .ventas import crear_venta

    usuario = _usuario_servicio(db)
    emp = _empresa(db)
    sucursal = _sucursal_default(db)
    if not emp or not sucursal:
        raise HTTPException(503, "El negocio no está configurado")

    cliente_id = None
    tel = (data.telefono or "").strip()
    if tel:
        cliente = (
            db.query(Cliente)
            .filter(Cliente.empresa_id == emp.id, Cliente.telefono == tel)
            .first()
        )
        if not cliente:
            cliente = Cliente(
                empresa_id=emp.id,
                nombre=(data.cliente_nombre or "Cliente kiosko").strip() or "Cliente kiosko",
                telefono=tel,
                tipo_documento="CC",
                documento=NIT_CONSUMIDOR_FINAL,
                tipo="ocasional",
            )
            db.add(cliente)
            db.flush()
        cliente_id = cliente.id

    detalle = []
    subtotal_previo = 0.0
    for item in data.items:
        p = db.get(Producto, item.producto_id)
        if not p or not p.activo:
            raise HTTPException(400, f"Producto {item.producto_id} no disponible")
        if item.cantidad <= 0:
            raise HTTPException(400, "Las cantidades deben ser positivas")
        subtotal_previo += round(
            float(p.precio_venta or 0) * (1 + float(p.impuesto or 0) / 100) * item.cantidad, 2
        )
        detalle.append(VentaDetalleCreate(producto_id=p.id, cantidad=item.cantidad, precio=None))

    medio = (data.medio or "efectivo").strip().lower()
    recibido = data.recibido or subtotal_previo
    venta = crear_venta(
        VentaCreate(
            empresa_id=emp.id,
            sucursal_id=sucursal.id,
            cliente_id=cliente_id,
            tipo="contado",
            detalle=detalle,
            pagos=[VentaPagoCreate(medio=medio if medio in ("nequi", "daviplata", "breb", "tarjeta", "efectivo") else "efectivo", monto=round(float(recibido), 2))],
            nota="Venta kiosko de autoservicio",
        ),
        db,
        usuario,
    )
    cambio = max(0.0, round(float(recibido) - float(venta.total or 0), 2))
    from ..wa import config_bool

    envio_wa = bool(cliente_id and tel and config_bool(db, "pos.recibo_whatsapp"))
    return {
        "ok": True,
        "venta_id": venta.id,
        "numero": venta.numero,
        "total": round(float(venta.total or 0), 2),
        "cambio": cambio,
        "recibido": round(float(recibido), 2),
        "cliente_id": cliente_id,
        "whatsapp": envio_wa,
    }


# ---------- Tirilla pública (enlace WhatsApp / QR) ----------
@router.get("/tirilla/{venta_id}", response_class=Response)
def tirilla_publica(
    venta_id: int,
    llave: str = "",
    recibido: float | None = None,
    cambio: float | None = None,
    db: Session = Depends(get_db),
):
    if not _llave_ok(db, llave):
        raise HTTPException(403, "Llave pública inválida")
    from .ventas import tirilla_html, obtener_venta_publica

    venta = obtener_venta_publica(db, venta_id)
    return tirilla_html(db, venta, recibido=recibido, cambio=cambio)


# ---------- Códigos QR ----------
@router.get("/qr", response_class=Response)
def codigo_qr(texto: str = "", tam: int = 320):
    if not texto:
        raise HTTPException(400, "Falta el parámetro 'texto'")
    if len(texto) > 4000:
        raise HTTPException(400, "Texto demasiado largo")
    return Response(content=_qr_png_bytes(texto, tam=max(96, min(tam, 720))), media_type="image/png")


@router.get("/qr-pago/{tipo}", response_class=Response)
def qr_pago(tipo: str, db: Session = Depends(get_db)):
    mime, datos = montar_qr_pago(db, tipo)
    if mime == "text/url":
        from fastapi.responses import RedirectResponse

        return RedirectResponse(datos)
    return Response(content=datos, media_type=mime)


# ---------- Páginas ----------
_JS_CARRITO = """
function moneda(n){return '$'+Math.round(n || 0).toLocaleString('es-CO');}
const estado = { carrito: {}, cat: 'Todos' };
function reRender() {
  const n = Object.values(estado.carrito).reduce((a,b)=>a+b,0);
  const tot = Object.entries(estado.carrito).reduce((a,[id,q])=>a + q * (PRECIOS[id] ? PRECIOS[id].precio : 0),0);
  const barTxt = document.getElementById('bartxt');
  if (barTxt) barTxt.textContent = `Ver pedido · ${n} · ${moneda(tot)}`;
  const verBtn = document.getElementById('vercarrito');
  if (verBtn) verBtn.textContent = `Ver pedido (${n}) · ${moneda(tot)}`;
  const bar = document.getElementById('bar');
  if (bar) bar.style.display = n ? 'block' : 'none';
  document.querySelectorAll('.card').forEach(c => {
    const q = estado.carrito[c.dataset.id];
    const boton = c.querySelector('.add');
    if (boton) boton.textContent = q ? `Agregado ×${q}` : 'Agregar';
  });
}
function addItem(id){ estado.carrito[id]=Number(estado.carrito[id]||0)+1; reRender(); }
function selCat(btn,cat){
  document.querySelectorAll('.chip').forEach(x=>x.classList.remove('on'));
  btn.classList.add('on'); estado.cat=cat;
  document.querySelectorAll('.sec').forEach(s=>s.style.display=(cat==='Todos'||s.dataset.cat===cat)?'':'none');
}
"""


def _html_menu_page(llave, mesa_id, tipo, negocio):
    es_comida = tipo in _TIPOS_COMIDA
    titulo = "Escanea y pide" if es_comida else "Nuestros productos"
    sub = (
        negocio.get("nombre", "Menú digital") + " · " + (
            "el mesero llevará el pedido a tu mesa." if es_comida
            else "agrega tus artículos y confirma el pedido en caja."
        )
    )
    prep_html = """
    <label>Modo de preparación</label>
    <select id="prep"><option value="">(sin especificar)</option><option value="crudo">Crudo</option><option value="3">Término 3</option><option value="medio">Medio</option><option value="medio bien">Medio bien</option><option value="termino">Término</option></select>""" if es_comida else ""
    envio_txt = "Enviar a cocina" if es_comida else "Confirmar pedido"
    return _html_pagina(
        "Menú",
        f"""
<header><h1>📋 {titulo}</h1><div class="sub">{escape(sub)}</div></header>
<div class="cat-wrap" id="cats"></div>
<section id="secs"></section>
<div class="bar" id="bar" style="display:none"><button id="vercarrito">Ver pedido</button></div>
<div class="overlay" id="ov">
 <div class="panel">
   <div style="display:flex;justify-content:space-between;align-items:center"><b style="font-size:17px">Tu pedido</b><button class="btn2" onclick="cierra()">✕</button></div>
   <div id="lista"></div>
   <div class="total" id="tot"></div>
   <label>Nombre (opcional)</label><input id="nom" placeholder="Tu nombre" />
   <label>Teléfono (opcional, para tu recibo)</label><input id="tel" type="tel" placeholder="300 000 0000" />
   <label>Nota general</label><input id="nota" placeholder="Ej: sin cebolla" />
   {prep_html}
   <div style="height:14px"></div>
   <button id="enviar" class="btn2" style="background:#34d399;color:#062e1f;border:0;font-weight:800;padding:14px">{envio_txt}</button>
 </div>
</div>
<script>
const MESA = {mesa_id};
const LLAVE = {_json_str(llave)};
const TIPO = {_json_str(tipo)};
const PRECIOS = {{}};
{_JS_CARRITO}
function cierra(){{ document.getElementById('ov').classList.remove('on'); }}
document.getElementById('vercarrito').addEventListener('click',()=>{{
  const list=document.getElementById('lista'); list.innerHTML='';
  Object.entries(estado.carrito).forEach(([id,q])=>{{
    const p=PRECIOS[id];
    list.insertAdjacentHTML('beforeend', `<div class="row"><span><b>${{p.nombre}}</b><br><span class="nota">${{moneda(p.precio)}} c/u</span></span>
      <span class="qty"><button onclick="q('${{id}}',-1)">-</button><b>${{q}}</b><button onclick="q('${{id}}',1)">+</button></span></div>`);
  }});
  document.getElementById('tot').textContent = 'Total ' + moneda(Object.entries(estado.carrito).reduce((a,[i,q])=>a+q*PRECIOS[i].precio,0));
  document.getElementById('ov').classList.add('on');
}});
function q(id,d){{ estado.carrito[id]=Number(estado.carrito[id]||0)+d; if(estado.carrito[id]<=0) delete estado.carrito[id]; cierra(); document.getElementById('vercarrito').click(); }}
document.getElementById('enviar').addEventListener('click', async ()=>{{
  const selPrep=document.getElementById('prep');
  const items=Object.entries(estado.carrito).filter(([,q])=>q>0).map(([id,q])=>({{producto_id:Number(id),cantidad:q,preparacion:(selPrep?selPrep.value:null)||null}}));
  const btn=document.getElementById('enviar'); btn.disabled=true; btn.textContent='Enviando\u2026';
  try{{
    const r=await fetch('/publico/pedido',{{method:'POST',headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{llave:LLAVE,mesa_id:MESA,items,cliente:document.getElementById('nom').value,telefono:document.getElementById('tel').value}})}});
    const d=await r.json();
    if(!r.ok) throw new Error(d.detail||'Error');
    estado.carrito={{}}; cierra();
    document.getElementById('bar').style.display='none';
    document.querySelector('#secs').insertAdjacentHTML('beforebegin',
      `<div class="overlay on"><div class="panel"><div class="exito">🎉<div class="big">{{d.numero}}</div>
       <p class="nota" style="margin-top:8px">Tu pedido fue enviado a la cocina. ¡Disfruta!</p>
       <div style="height:14px"></div><button class="btn2" style="background:#34d399;color:#062e1f;border:0;font-weight:800" onclick="this.closest('.overlay').remove();location.reload()">Seguir pidiendo</button></div></div></div>`);
  }} catch(e){{
    btn.disabled=false; btn.textContent='Reintentar enviar'; alert(e.message);
  }}
}});
fetch('/publico/menu/'+MESA+'/datos').then(r=>r.json()).then(d=>{{
  const secs=document.getElementById('secs'), cats=document.getElementById('cats');
  cats.insertAdjacentHTML('beforeend',`<button class="chip on" onclick="selCat(this,'Todos')">Todo</button>`);
  d.categorias.filter(c=>c.productos.length).forEach(c=>{{
    cats.insertAdjacentHTML('beforeend',`<button class="chip" onclick="selCat(this,'${{c.nombre.replace(/'/g,'')}}')">${{c.nombre}}</button>`);
    secs.insertAdjacentHTML('beforeend',`<section class="sec" data-cat="${{c.nombre.replace(/'/g,'')}}"><h2>${{c.nombre}}</h2><div class="grid">${{c.productos.map(p=>{{
      PRECIOS[p.id]=p;
      return `<div class="card" data-id="${{p.id}}" onclick="addItem(${{p.id}})">
        <b>${{p.nombre}}</b><div class="desc">${{p.descripcion||''}}</div>
        <div class="precio">${{moneda(p.precio)}}</div>
        <button class="add">Agregar</button></div>`;
    }}).join('')}}</div></section>`);
  }});
  reRender();
}});
</script>
""",
    )


def _json_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


@router.get("/menu/{mesa_id}", response_class=Response)
def pagina_menu(mesa_id: int, db: Session = Depends(get_db)):
    from ..models import Mesa

    mesa = db.get(Mesa, mesa_id)
    if not mesa:
        raise HTTPException(404, "Mesa no encontrada")
    return Response(
        content=_html_menu_page(
            obtener_config(db, "publico.llave", "publico"),
            mesa_id,
            _tipo_publico(db),
            _negocio(db, mesa),
        ),
        media_type="text/html",
    )


@router.get("/kiosko", response_class=Response)
def pagina_kiosko(db: Session = Depends(get_db)):
    llave = obtener_config(db, "publico.llave", "publico")
    pagos = {"nequi": bool(obtener_config(db, "pagos.qr_nequi", "")), "daviplata": bool(obtener_config(db, "pagos.qr_daviplata", "")), "breb": bool(obtener_config(db, "pagos.qr_breb", ""))}
    js_pagos = "nequi" if pagos["nequi"] else ("daviplata" if pagos["daviplata"] else ("breb" if pagos["breb"] else ""))
    tipo = _tipo_publico(db)
    negocio = _negocio(db)
    es_comida = tipo in _TIPOS_COMIDA
    sub = (
        (negocio.get("nombre", "Autoservicio") + " · " + (
            "pide y paga directo en la pantalla." if es_comida
            else "agrega tus productos y paga aquí; recibo y factura automáticos."
        ))
    )
    return Response(
        content=_html_pagina(
        "Autoservicio",
        f"""
<header><h1>🛒 Autoservicio</h1><div class="sub">{escape(sub)}</div></header>
<div class="cat-wrap" id="cats"></div>
<section id="secs"></section>
<div class="bar" id="bar" style="display:none"><button id="vercarrito">Ver carrito</button></div>
<div class="overlay" id="ov">
 <div class="panel">
   <div style="display:flex;justify-content:space-between;align-items:center"><b style="font-size:17px">Tu carrito</b><button class="btn2" onclick="document.getElementById('ov').classList.remove('on')">✕</button></div>
   <div id="lista"></div>
   <div class="total" id="tot"></div>
   <label>Nombre (opcional)</label><input id="nom" placeholder="Tu nombre" />
   <label>Teléfono (opcional, te llega tu recibo por WhatsApp)</label><input id="tel" type="tel" placeholder="300 000 0000" />
   <label>Pago</label>
   <div class="pay-opt">
     <button class="on" id="opt-efectivo" onclick="pago('efectivo')">💵 Efectivo</button>
     {"<button id=\"opt-nequi\" onclick=\"pago('nequi')\">💚 Nequi</button>" if pagos['nequi'] else ""}
     {"<button id=\"opt-daviplata\" onclick=\"pago('daviplata')\">🔵 Daviplata</button>" if pagos['daviplata'] else ""}
     {"<button id=\"opt-breb\" onclick=\"pago('breb')\">🟩 Bre-B</button>" if pagos['breb'] else ""}
   </div>
   <div id="efectivo-box">
     <label>¿Con cuánto pagas?</label>
     <div class="pay-opt" id="quick"></div>
   </div>
   <div id="qr-box" class="hidden">
     <div class="qr-box" id="qrimg"></div>
     <p class="nota" style="text-align:center">Paga desde tu app y toca <b>Listo</b> cuando se confirme el pago.</p>
   </div>
   <div style="height:14px"></div>
   <button id="enviar" class="btn2" style="background:#34d399;color:#062e1f;border:0;font-weight:800;padding:14px">Confirmar y pagar</button>
 </div>
</div>
<script>
const LLAVE = {_json_str(llave)};
const PRECIOS = {{}};
const JS_PAGOS = "{js_pagos}";
const TIPO = {_json_str(tipo)};
let medio = 'efectivo', recibido = null, total = 0;
{_JS_CARRITO}
function cierra(){{ document.getElementById('ov').classList.remove('on'); }}
function pago(m){{
  medio=m;
  ['efectivo','nequi','daviplata','breb'].forEach(x=>{{ const b=document.getElementById('opt-'+x); if(b) b.classList.toggle('on', x===m); }});
  document.getElementById('efectivo-box').style.display = m==='efectivo' ? '' : 'none';
  const qb=document.getElementById('qr-box');
  qb.classList.toggle('hidden', m==='efectivo');
  if(m!=='efectivo'){{
    document.getElementById('qrimg').innerHTML=`<img src="/publico/qr-pago/${{m}}" alt="${{m}}">`;
  }}
}}
document.getElementById('vercarrito').addEventListener('click',()=>{{
  total = Object.entries(estado.carrito).reduce((a,[i,q])=>a+q*PRECIOS[i].precio,0);
  const list=document.getElementById('lista'); list.innerHTML='';
  Object.entries(estado.carrito).forEach(([id,q])=>{{
    const p=PRECIOS[id];
    list.insertAdjacentHTML('beforeend', `<div class="row"><span><b>${{p.nombre}}</b><br><span class="nota">${{moneda(p.precio)}} c/u</span></span>
      <span class="qty"><button onclick="q('${{id}}',-1)">-</button><b>${{q}}</b><button onclick="q('${{id}}',1)">+</button></span></div>`);
  }});
  document.getElementById('tot').textContent = 'Total ' + moneda(total);
  const quick=document.getElementById('quick');
  quick.innerHTML='';
  const opciones=[total, Math.ceil(total/1000)*1000, (Math.ceil(total/10000)*10000), (Math.ceil(total/20000)*20000), (Math.ceil(total/50000)*50000)].filter((v,i,a)=>a.indexOf(v)===i && v>0);
  opciones.forEach(v=>quick.insertAdjacentHTML('beforeend',`<button onclick="rec(${{v}})">${{moneda(v)}}</button>`));
  rec(opciones[0]);
  document.getElementById('ov').classList.add('on');
}});
function rec(v){{ recibido=v; document.getElementById('quick').querySelectorAll('button').forEach(b=>b.classList.toggle('on', Number(b.textContent.replace(/[^0-9]/g,''))===v)); }}
function q(id,d){{ estado.carrito[id]=Number(estado.carrito[id]||0)+d; if(estado.carrito[id]<=0) delete estado.carrito[id]; cierra(); document.getElementById('vercarrito').click(); }}
document.getElementById('enviar').addEventListener('click', async ()=>{{
  const items=Object.entries(estado.carrito).filter(([,q])=>q>0).map(([id,q])=>({{producto_id:Number(id),cantidad:q}}));
  const btn=document.getElementById('enviar'); btn.disabled=true; btn.textContent='Procesando\u2026';
  const body={{llave:LLAVE, items, medio, telefono:document.getElementById('tel').value, cliente_nombre:document.getElementById('nom').value}};
  if(medio==='efectivo') body.recibido = recibido;
  try{{
    const r=await fetch('/publico/venta',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
    const d=await r.json();
    if(!r.ok) throw new Error(d.detail||'Error');
    estado.carrito={{}}; cierra();
    document.getElementById('bar').style.display='none';
    const wa = d.whatsapp ? '<p class="nota" style="margin-top:6px">💬 Recibo enviado por WhatsApp.</p>' : '';
    document.querySelector('#secs').insertAdjacentHTML('beforebegin',
      `<div class="overlay on"><div class="panel"><div class="exito">✅<div class="big">${{moneda(d.total)}}</div>
       <p class="nota" style="margin-top:8px">Comprobante {{d.numero}}${{medio==='efectivo'?' · Cambio '+moneda(d.cambio):''}}</p>
       ${{wa}}
       <div style="height:14px"></div>
       <a class="btn2" style="display:block;text-align:center;background:#34d399;color:#062e1f;border:0;font-weight:800;text-decoration:none" target="_blank" href="/publico/tirilla/${{d.venta_id}}?llave="+LLAVE>Ver tirilla / imprimir</a>
       <div style="height:8px"></div><button class="btn2" onclick="location.reload()">Nueva compra</button></div></div></div>`);
  }} catch(e){{ btn.disabled=false; btn.textContent='Reintentar'; alert(e.message); }}
}});
fetch('/publico/katalogo/datos').then(r=>r.json()).then(d=>{{
  const secs=document.getElementById('secs'), cats=document.getElementById('cats');
  cats.insertAdjacentHTML('beforeend',`<button class="chip on" onclick="selCat(this,'Todos')">Todo</button>`);
  d.categorias.filter(c=>c.productos.length).forEach(c=>{{
    cats.insertAdjacentHTML('beforeend',`<button class="chip" onclick="selCat(this,'${{c.nombre.replace(/'/g,'')}}')">${{c.nombre}}</button>`);
    secs.insertAdjacentHTML('beforeend',`<section class="sec" data-cat="${{c.nombre.replace(/'/g,'')}}"><h2>${{c.nombre}}</h2><div class="grid">${{c.productos.map(p=>{{
      PRECIOS[p.id]=p;
      return `<div class="card" data-id="${{p.id}}" onclick="addItem(${{p.id}})">
        <b>${{p.nombre}}</b><div class="desc">${{p.descripcion||''}}</div>
        <div class="precio">${{moneda(p.precio)}}</div>
        <button class="add">Agregar</button></div>`;
    }}).join('')}}</div></section>`);
  }});
  reRender();
}});
</script>
""",
        )
    )