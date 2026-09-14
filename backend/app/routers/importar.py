import csv
import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    AuditoriaLog,
    Cliente,
    Producto,
    Proveedor,
    Stock,
    Sucursal,
    Usuario,
)

router = APIRouter(prefix="", tags=["importar/exportar"])


def _csv_response(nombre: str, filas: list[dict]) -> Response:
    buf = io.StringIO()
    if filas:
        writer = csv.DictWriter(buf, fieldnames=list(filas[0].keys()))
        writer.writeheader()
        writer.writerows(filas)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}.csv"'},
    )


def _leer_csv(archivo: UploadFile) -> list[dict]:
    datos = archivo.file.read().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(datos)))


@router.get("/exportar/productos")
def exportar_productos(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    productos = db.query(Producto).all()
    return _csv_response(
        "productos",
        [
            {
                "id": p.id, "nombre": p.nombre, "sku": p.sku, "codigo_barras": p.codigo_barras,
                "plu": p.plu, "precio_venta": float(p.precio_venta or 0),
                "precio_compra": float(p.precio_compra or 0), "costo": float(p.costo or 0),
                "impuesto": float(p.impuesto or 0), "activo": p.activo,
            }
            for p in productos
        ],
    )


@router.get("/exportar/clientes")
def exportar_clientes(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    return _csv_response(
        "clientes",
        [
            {"id": c.id, "nombre": c.nombre, "tipo_documento": c.tipo_documento, "documento": c.documento,
             "telefono": c.telefono, "email": c.email, "tipo": c.tipo}
            for c in db.query(Cliente).all()
        ],
    )


@router.get("/exportar/proveedores")
def exportar_proveedores(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    return _csv_response(
        "proveedores",
        [
            {"id": p.id, "nombre": p.nombre, "nit": p.nit, "contacto": p.contacto,
             "telefono": p.telefono, "email": p.email}
            for p in db.query(Proveedor).all()
        ],
    )


@router.get("/exportar/inventario")
def exportar_inventario(
    sucursal_id: int | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    q = db.query(Stock)
    if sucursal_id:
        q = q.filter(Stock.sucursal_id == sucursal_id)
    filas = []
    for s in q.all():
        p = db.get(Producto, s.producto_id)
        filas.append(
            {
                "producto_id": s.producto_id, "producto": p.nombre if p else "",
                "sucursal_id": s.sucursal_id, "existencias": float(s.existencias or 0),
                "reservado": float(s.reservado or 0), "disponible": float(s.disponible or 0),
            }
        )
    return _csv_response("inventario", filas)


@router.post("/importar/productos")
def importar_productos(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    creados = actualizados = 0
    for fila in _leer_csv(archivo):
        sku = fila.get("sku") or ""
        if not sku:
            continue
        producto = db.query(Producto).filter(Producto.sku == sku).first()
        campos = {
            "nombre": fila.get("nombre") or sku,
            "codigo_barras": fila.get("codigo_barras"),
            "plu": fila.get("plu"),
            "precio_venta": float(fila.get("precio_venta") or 0),
            "precio_compra": float(fila.get("precio_compra") or 0),
            "costo": float(fila.get("costo") or 0),
            "impuesto": float(fila.get("impuesto") or 0),
        }
        if producto:
            for k, v in campos.items():
                setattr(producto, k, v)
            actualizados += 1
        else:
            db.add(Producto(empresa_id=1, sku=sku, **campos))
            creados += 1
    db.add(AuditoriaLog(usuario_id=usuario.id, modulo="importar", accion="importar",
                        entidad="productos", detalle=f"{creados} creados, {actualizados} actualizados"))
    db.commit()
    return {"creados": creados, "actualizados": actualizados}


@router.post("/importar/clientes")
def importar_clientes(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    creados = actualizados = 0
    for fila in _leer_csv(archivo):
        documento = fila.get("documento") or ""
        if not documento:
            continue
        cliente = db.query(Cliente).filter(Cliente.documento == documento).first()
        if cliente:
            cliente.nombre = fila.get("nombre") or cliente.nombre
            cliente.telefono = fila.get("telefono")
            cliente.email = fila.get("email")
            actualizados += 1
        else:
            db.add(Cliente(empresa_id=1, nombre=fila.get("nombre") or "Sin nombre",
                           documento=documento, tipo_documento=fila.get("tipo_documento") or "CC",
                           telefono=fila.get("telefono"), email=fila.get("email"),
                           tipo=fila.get("tipo") or "ocasional"))
            creados += 1
    db.add(AuditoriaLog(usuario_id=usuario.id, modulo="importar", accion="importar",
                        entidad="clientes", detalle=f"{creados} creados, {actualizados} actualizados"))
    db.commit()
    return {"creados": creados, "actualizados": actualizados}


@router.post("/importar/proveedores")
def importar_proveedores(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    creados = actualizados = 0
    for fila in _leer_csv(archivo):
        nit = fila.get("nit") or ""
        if not nit:
            continue
        proveedor = db.query(Proveedor).filter(Proveedor.nit == nit).first()
        if proveedor:
            proveedor.nombre = fila.get("nombre") or proveedor.nombre
            proveedor.contacto = fila.get("contacto")
            proveedor.telefono = fila.get("telefono")
            actualizados += 1
        else:
            db.add(Proveedor(empresa_id=1, nombre=fila.get("nombre") or "Sin nombre", nit=nit,
                             contacto=fila.get("contacto"), telefono=fila.get("telefono")))
            creados += 1
    db.commit()
    return {"creados": creados, "actualizados": actualizados}


@router.post("/importar/inventario")
def importar_inventario(
    archivo: UploadFile = File(...),
    sucursal_id: int = 1,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    if not db.get(Sucursal, sucursal_id):
        raise HTTPException(400, "Sucursal no existe")
    ajustados = 0
    for fila in _leer_csv(archivo):
        try:
            producto_id = int(fila.get("producto_id") or 0)
        except ValueError:
            continue
        if not db.get(Producto, producto_id):
            continue
        stock = db.query(Stock).filter_by(producto_id=producto_id, sucursal_id=sucursal_id).first()
        if not stock:
            stock = Stock(producto_id=producto_id, sucursal_id=sucursal_id)
            db.add(stock)
        stock.existencias = float(fila.get("existencias") or 0)
        stock.disponible = float(stock.existencias) - float(stock.reservado or 0)
        ajustados += 1
    db.commit()
    return {"ajustados": ajustados}