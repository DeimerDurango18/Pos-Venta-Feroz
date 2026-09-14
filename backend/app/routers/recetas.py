"""Recetas / ingredientes de productos compuestos (combos y kits) y costeo.

Permite definir de qué materias primas se compone un producto (es_compuesto),
recalcular su costo a partir de las recetas y -opcionalmente- descontar dichas
materias primas del inventario cuando se vende el combo (flag pos.combos_consumen).
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    AuditoriaLog,
    MovimientoInventario,
    Producto,
    ProductoComponente,
    Stock,
    Usuario,
)

router = APIRouter(prefix="/productos", tags=["recetas"])


class IngredienteItem(BaseModel):
    componente_id: int
    cantidad: float = 1


class RecetaUpdate(BaseModel):
    ingredientes: list[IngredienteItem]


def _costeo(db: Session, producto: Producto, filas: list[ProductoComponente] | None = None):
    filas = filas or db.query(ProductoComponente).filter_by(producto_id=producto.id).all()
    total = 0.0
    for c in filas:
        ing = db.get(Producto, c.componente_id)
        total += (float(ing.costo or 0) if ing else 0) * float(c.cantidad or 1)
    return round(total, 2)


def _receta_out(db: Session, producto: Producto, sucursal_id: int = 1):
    filas = db.query(ProductoComponente).filter_by(producto_id=producto.id).all()
    costo_calculado = _costeo(db, producto, filas)
    ingredientes = []
    for c in filas:
        ing = db.get(Producto, c.componente_id)
        linea = (float(ing.costo or 0) if ing else 0) * float(c.cantidad or 1)
        stock = (
            db.query(Stock).filter_by(producto_id=c.componente_id, sucursal_id=sucursal_id).first()
        )
        ingredientes.append(
            {
                "componente_id": c.componente_id,
                "nombre": ing.nombre if ing else "?",
                "cantidad": float(c.cantidad or 1),
                "unidad": ing.tipo if ing else "unidad",
                "costo_unitario": float(ing.costo or 0) if ing else 0,
                "costo_linea": round(linea, 2),
                "stock": float(stock.existencias or 0) if stock else 0,
            }
        )
    return {
        "producto_id": producto.id,
        "nombre": producto.nombre,
        "es_compuesto": bool(producto.es_compuesto),
        "costo": float(producto.costo or 0),
        "costo_calculado": costo_calculado,
        "ingredientes": ingredientes,
    }


@router.get("/{producto_id}/receta")
def obtener_receta(
    producto_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    producto = db.get(Producto, producto_id)
    if not producto:
        raise HTTPException(404, "Producto no encontrado")
    return _receta_out(db, producto, usuario.sucursal_id)


@router.put("/{producto_id}/receta", status_code=201)
def actualizar_receta(
    producto_id: int,
    data: RecetaUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    producto = db.get(Producto, producto_id)
    if not producto:
        raise HTTPException(404, "Producto no encontrado")

    agregados: dict[int, float] = {}
    for item in data.ingredientes:
        if item.componente_id == producto_id:
            raise HTTPException(400, "Un producto no puede ser ingrediente de sí mismo")
        ing = db.get(Producto, item.componente_id)
        if not ing:
            raise HTTPException(400, f"Ingrediente {item.componente_id} no existe")
        if item.cantidad <= 0:
            raise HTTPException(400, f"Cantidad inválida para {ing.nombre}")
        agregados[item.componente_id] = agregados.get(item.componente_id, 0) + float(item.cantidad)

    db.query(ProductoComponente).filter(ProductoComponente.producto_id == producto_id).delete()
    db.flush()
    for comp_id, cantidad in agregados.items():
        db.add(ProductoComponente(producto_id=producto_id, componente_id=comp_id, cantidad=cantidad))

    producto.es_compuesto = bool(agregados)
    producto.costo = _costeo(db, producto)
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="recetas",
            accion="guardar",
            entidad="receta",
            entidad_id=producto.id,
            detalle=f"Receta de {producto.nombre}: {len(agregados)} ingredientes, costo {producto.costo}",
        )
    )
    db.commit()
    db.refresh(producto)
    return _receta_out(db, producto, usuario.sucursal_id)


@router.post("/{producto_id}/costear")
def costear_receta(
    producto_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    producto = db.get(Producto, producto_id)
    if not producto:
        raise HTTPException(404, "Producto no encontrado")
    anterior = float(producto.costo or 0)
    calculado = _costeo(db, producto)
    producto.costo = calculado
    margen = None
    if float(producto.precio_venta or 0) > 0:
        margen = round((float(producto.precio_venta) - calculado) / float(producto.precio_venta) * 100, 2)
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="recetas",
            accion="costear",
            entidad="receta",
            entidad_id=producto.id,
            detalle=f"Costeo de {producto.nombre}: {anterior} -> {calculado}",
        )
    )
    db.commit()
    return {
        "producto_id": producto.id,
        "nombre": producto.nombre,
        "costo_anterior": anterior,
        "costo_calculado": calculado,
        "margen_pct": margen,
    }


def consumir_componentes(
    db: Session,
    producto: Producto,
    cantidad: float,
    sucursal_id: int,
    referencia: str,
    usuario: Usuario,
):
    """Descuenta las materias primas de un combo vendido (si es_compuesto).

    Es estricto: si alguna materia prima no tiene stock suficiente, la venta
    se rechaza para que el operador lo sepa. Se usa solo cuando está activo
    el flag de configuración `pos.combos_consumen`.
    """
    if not producto.es_compuesto:
        return []
    filas = db.query(ProductoComponente).filter_by(producto_id=producto.id).all()
    if not filas:
        return []
    consumidos = []
    for c in filas:
        ing = db.get(Producto, c.componente_id)
        if not ing:
            raise HTTPException(400, f"La receta de {producto.nombre} referencia un ingrediente inexistente")
        necesario = float(c.cantidad or 1) * cantidad
        stock = (
            db.query(Stock).filter_by(producto_id=c.componente_id, sucursal_id=sucursal_id).first()
        )
        if not stock or float(stock.existencias or 0) < necesario:
            raise HTTPException(
                400,
                f"No hay materia prima para la venta del combo {producto.nombre}: "
                f"{ing.nombre} requiere {necesario}",
            )
        stock.existencias = float(stock.existencias or 0) - necesario
        stock.disponible = stock.existencias - float(stock.reservado or 0)
        db.add(
            MovimientoInventario(
                producto_id=c.componente_id,
                sucursal_id=sucursal_id,
                tipo="salida",
                cantidad=-necesario,
                motivo="Venta combo",
                referencia=referencia,
                saldo=float(stock.existencias),
            )
        )
        consumidos.append({"ingrediente": ing.nombre, "cantidad": necesario})
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="recetas",
            accion="consumir",
            entidad="venta",
            entidad_id=None,
            detalle=f"Venta {referencia}: {producto.nombre} x{cantidad} consume {len(consumidos)} materias primas",
        )
    )
    return consumidos


def consumir_lineas_combo(
    db: Session,
    lineas_compuestas: list,
    sucursal_id: int,
    referencia: str,
    usuario: Usuario,
):
    """Consume las materias primas de las líneas compuestas vendidas."""
    total = []
    for producto, cantidad in lineas_compuestas:
        total.extend(consumir_componentes(db, producto, cantidad, sucursal_id, referencia, usuario))
    return total