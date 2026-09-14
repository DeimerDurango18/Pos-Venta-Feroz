from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..codigos import codigo_para_producto, ean13_completo, svg_ean13
from ..database import get_db
from ..models import Lote, Producto, Stock

router = APIRouter(prefix="/etiquetas", tags=["etiquetas"])


@router.get("/productos", response_class=HTMLResponse)
def etiquetas_productos(
    ids: str = Query(...),
    copias: int = Query(2, ge=1, le=20),
    precio: str = Query("venta"),  # venta | mayorista | ambos
    con_vencimiento: bool = Query(True),
    con_precio: bool = Query(True),
    print: bool = Query(False),
    db: Session = Depends(get_db),
):
    try:
        producto_ids = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    except Exception:
        raise HTTPException(400, "ids inválidos")
    if not producto_ids:
        raise HTTPException(400, "Debe indicar al menos un producto")
    productos = db.query(Producto).filter(Producto.id.in_(producto_ids)).all()
    if not productos:
        raise HTTPException(404, "Productos no encontrados")
    por_id = {p.id: p for p in productos}

    etiquetas = []
    for pid in producto_ids:
        p = por_id.get(pid)
        if not p:
            continue
        e13 = codigo_para_producto(p.id, p.codigo_barras)
        lotes = (
            db.query(Lote)
            .filter(Lote.producto_id == p.id, Lote.activo == True)
            .order_by(Lote.vencimiento.asc())
            .all()
        )
        vencimiento = None
        if con_vencimiento and p.con_vencimiento and lotes:
            vencimiento = lotes[0].vencimiento.isoformat() if lotes[0].vencimiento else None
        etiqueta = f"""
        <div class="etiqueta">
          <div class="nombre">{_esc(p.nombre)}</div>
          <div class="codigo">{p.sku or e13}</div>"""
        if con_precio:
            if precio == "mayorista":
                etiqueta += f'<div class="precio">$ {_formato(p.precio_mayorista)}</div>'
            elif precio == "ambos":
                etiqueta += (
                    f'<div class="precio">$ {_formato(p.precio_venta)}'
                    f'<span class="precio2"> / {_formato(p.precio_mayorista)}</span></div>'
                )
            else:
                etiqueta += f'<div class="precio">$ {_formato(p.precio_venta)}</div>'
        etiqueta += f'<div class="codigo">{svg_ean13(e13, altura=34, ancho=110, mostrar=True)}</div>'
        if vencimiento:
            etiqueta += f'<div class="vencimiento">Vec: {vencimiento}</div>'
        etiqueta += "</div>"
        etiquetas.extend([etiqueta] * copias)

    auto = "<script>window.onload=function(){window.print();}</script>" if print else ""
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Etiquetas</title>
<style>
  @page {{ size: 210mm 297mm; margin: 5mm; }}
  body {{ font-family: Arial, sans-serif; margin: 0; }}
  .hoja {{ display: flex; flex-wrap: wrap; gap: 3mm; }}
  .etiqueta {{
    width: 66mm; height: 26mm; border: 0.4mm solid #000;
    padding: 1mm 2mm; overflow: hidden; box-sizing: border-box;
  }}
  .nombre {{ font-size: 9pt; font-weight: bold; white-space: nowrap; overflow: hidden; }}
  .precio {{ font-size: 12pt; font-weight: bold; }}
  .precio2 {{ font-size: 9pt; font-weight: normal; }}
  .codigo {{ font-size: 6pt; line-height: 1.1; }}
  .vencimiento {{ font-size: 7pt; color: #333; }}
</style></head><body>
<div class="hoja">{"".join(etiquetas)}</div>
{auto}
</body></html>"""
    return HTMLResponse(html)


@router.get("/gondola", response_class=HTMLResponse)
def etiqueta_gondola(
    ids: str = Query(...),
    precio: str = Query("venta"),
    db: Session = Depends(get_db),
):
    """Etiqueta grande de góndola/estante con precio destacado."""
    try:
        producto_ids = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    except Exception:
        raise HTTPException(400, "ids inválidos")
    productos = db.query(Producto).filter(Producto.id.in_(producto_ids)).all()
    por_id = {p.id: p for p in productos}
    tarjetas = []
    for pid in producto_ids:
        p = por_id.get(pid)
        if not p:
            continue
        e13 = codigo_para_producto(p.id, p.codigo_barras)
        monto = p.precio_mayorista if precio == "mayorista" else p.precio_venta
        tarjetas.append(
            f"""
        <div class="tarjeta">
          <div class="nombre">{_esc(p.nombre)}</div>
          <div class="precio">$ {_formato(monto)}</div>
          <div class="codigo">{svg_ean13(e13, altura=50, ancho=200, mostrar=True)}</div>
        </div>"""
        )
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Etiquetas de góndola</title>
<style>
  @page {{ size: A4 landscape; margin: 5mm; }}
  body {{ font-family: Arial, sans-serif; }}
  .grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 5mm; }}
  .tarjeta {{ border: 0.5mm solid #000; padding: 4mm; text-align: center; }}
  .nombre {{ font-size: 14pt; font-weight: bold; margin-bottom: 2mm; }}
  .precio {{ font-size: 30pt; font-weight: bold; margin: 2mm 0; }}
</style></head><body>
<div class="grid">{"".join(tarjetas)}</div>
</body></html>"""
    return HTMLResponse(html)


def _esc(t):
    if t is None:
        return ""
    return (
        str(t)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _formato(v):
    try:
        return f"{float(v or 0):,.0f}".replace(",", ".")
    except Exception:
        return "0"