from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import PantallaCliente, Usuario

router = APIRouter(prefix="/pantalla", tags=["pantalla de cliente"])


class PantallaUpdate(BaseModel):
    items: list = []
    subtotal: float = 0
    descuento: float = 0
    impuesto: float = 0
    propina: float = 0
    total: float = 0
    mensaje: str | None = None


def _leer(db: Session) -> PantallaCliente:
    row = db.get(PantallaCliente, 1)
    if not row:
        row = PantallaCliente(id=1, items=[], subtotal=0, descuento=0, impuesto=0, propina=0, total=0, updated_at=datetime.now())
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.post("")
def actualizar_pantalla(
    data: PantallaUpdate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    row = _leer(db)
    row.items = data.items
    row.subtotal = data.subtotal
    row.descuento = data.descuento
    row.impuesto = data.impuesto
    row.propina = data.propina
    row.total = data.total
    row.mensaje = data.mensaje
    row.updated_at = datetime.now()
    db.commit()
    return {"ok": True}


@router.get("")
def ver_pantalla(db: Session = Depends(get_db)):
    row = _leer(db)
    return {
        "items": row.items or [],
        "subtotal": float(row.subtotal or 0),
        "descuento": float(row.descuento or 0),
        "impuesto": float(row.impuesto or 0),
        "propina": float(row.propina or 0),
        "total": float(row.total or 0),
        "mensaje": row.mensaje,
        "updated_at": str(row.updated_at) if row.updated_at else None,
    }


VISTA_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Pantalla de cliente</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:#0f172a; color:#fff; font-family:'Segoe UI',Arial,sans-serif; }
  #wrap { display:flex; flex-direction:column; min-height:100vh; padding:24px; }
  h1 { text-align:center; font-size:1.6em; font-weight:300; color:#94a3b8; margin-bottom:12px; }
  #items { flex:1; overflow:hidden; }
  .row { display:flex; justify-content:space-between; padding:10px 4px; border-bottom:1px solid #1e293b; font-size:1.4em; }
  .row .cant { color:#22d3ee; font-weight:700; margin-right:14px; }
  .row .name { flex:1; }
  .row .sub { font-weight:600; }
  #total { display:flex; justify-content:space-between; align-items:baseline; font-size:3.2em; font-weight:800; color:#4ade80; padding-top:10px; border-top:3px solid #334155; }
  #total .lbl { font-size:.35em; color:#94a3b8; }
  #msg { text-align:center; font-size:1.1em; color:#fbbf24; margin-top:8px; min-height:1.2em; }
</style>
</head>
<body>
<div id="wrap">
  <h1>Su compra</h1>
  <div id="items"></div>
  <div id="total"><span class="lbl">TOTAL</span><span id="val">$0</span></div>
  <div id="msg"></div>
</div>
<script>
  function money(n){ return '$' + Number(n||0).toLocaleString('es-CO', {maximumFractionDigits:0}); }
  async function cargar(){
    var r = await fetch('/api/pantalla', {cache:'no-store'});
    var d = await r.json();
    var box = document.getElementById('items');
    box.innerHTML = (d.items||[]).map(function(i){ return '<div class="row"><span class="cant">'+i.cantidad+'</span><span class="name">'+i.nombre+'</span><span class="sub">'+money(i.subtotal)+'</span></div>'; }).join('');
    document.getElementById('val').textContent = money(d.total);
    document.getElementById('msg').textContent = d.mensaje || '';
  }
  cargar();
  setInterval(cargar, 2000);
</script>
</body>
</html>
"""


@router.get("/vista", response_class=HTMLResponse, include_in_schema=False)
def vista_pantalla():
    return HTMLResponse(VISTA_HTML)