from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..codigos import codigo_para_producto, svg_ean13
from ..database import get_db
from ..models import (
    AuditoriaLog,
    Categoria,
    Empresa,
    Marca,
    PrecioCompetencia,
    PrecioHistorico,
    Presentacion,
    Producto,
    Usuario,
)
from ..deps import get_current_user
from ..schemas.avanzado import ErrorLogOut, PrecioCompetenciaCreate, PrecioCompetenciaOut, PrecioHistoricoOut
from ..schemas.producto import (
    CategoriaCreate,
    CategoriaOut,
    MarcaCreate,
    MarcaOut,
    PresentacionCreate,
    PresentacionOut,
    ProductoCreate,
    ProductoOut,
    ProductoUpdate,
)

router = APIRouter(prefix="/productos", tags=["productos"])

CAMPOS_PRECIO = (
    "precio_compra",
    "precio_venta",
    "precio_mayorista",
    "precio_minorista",
    "precio_institucional",
    "costo",
)


def _registrar_precios(db, producto, datos, usuario):
    """Guarda el historial de cambios de precios."""
    for campo in CAMPOS_PRECIO:
        nuevo = getattr(datos, campo, None)
        if nuevo is not None and nuevo != float(getattr(producto, campo) or 0):
            db.add(
                PrecioHistorico(
                    producto_id=producto.id,
                    campo=campo,
                    valor_anterior=float(getattr(producto, campo) or 0),
                    valor_nuevo=nuevo,
                    usuario_id=usuario.id if usuario else None,
                )
            )


def _auditar(db, usuario, accion, entidad, entidad_id, detalle):
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id if usuario else None,
            modulo="productos",
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            detalle=detalle,
        )
    )


# ---------- Categorías ----------
@router.get("/categorias", response_model=list[CategoriaOut])
def listar_categorias(db: Session = Depends(get_db)):
    return db.query(Categoria).all()


@router.post("/categorias", response_model=CategoriaOut, status_code=201)
def crear_categoria(data: CategoriaCreate, db: Session = Depends(get_db)):
    cat = Categoria(**data.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


# ---------- Marcas ----------
@router.get("/marcas", response_model=list[MarcaOut])
def listar_marcas(db: Session = Depends(get_db)):
    return db.query(Marca).all()


@router.post("/marcas", response_model=MarcaOut, status_code=201)
def crear_marca(data: MarcaCreate, db: Session = Depends(get_db)):
    marca = Marca(nombre=data.nombre)
    db.add(marca)
    db.commit()
    db.refresh(marca)
    return marca


# ---------- Presentaciones ----------
@router.get("/presentaciones", response_model=list[PresentacionOut])
def listar_presentaciones(db: Session = Depends(get_db)):
    return db.query(Presentacion).all()


@router.post("/presentaciones", response_model=PresentacionOut, status_code=201)
def crear_presentacion(data: PresentacionCreate, db: Session = Depends(get_db)):
    pres = Presentacion(**data.model_dump())
    db.add(pres)
    db.commit()
    db.refresh(pres)
    return pres


# ---------- Productos ----------
@router.get("", response_model=list[ProductoOut])
def listar_productos(
    q: str | None = Query(None, description="Buscar por nombre, SKU, código o PLU"),
    categoria_id: int | None = None,
    activo: bool | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Producto)
    if q:
        busqueda = f"%{q}%"
        query = query.filter(
            or_(
                Producto.nombre.ilike(busqueda),
                Producto.sku.ilike(busqueda),
                Producto.codigo_barras.ilike(busqueda),
                Producto.plu.ilike(busqueda),
            )
        )
    if categoria_id:
        query = query.filter(Producto.categoria_id == categoria_id)
    if activo is not None:
        query = query.filter(Producto.activo == activo)
    return query.order_by(Producto.nombre).all()


@router.post("", response_model=ProductoOut, status_code=201)
def crear_producto(data: ProductoCreate, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    if not db.get(Empresa, data.empresa_id):
        raise HTTPException(400, "Empresa no existe")
    producto = Producto(**data.model_dump())
    db.add(producto)
    db.flush()
    if not producto.codigo_barras:
        producto.codigo_barras = codigo_para_producto(producto.id)
    _registrar_precios(db, producto, data, usuario)
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="productos",
            accion="crear",
            entidad="producto",
            entidad_id=producto.id,
            detalle=f"Producto creado: {data.nombre}",
        )
    )
    db.commit()
    db.refresh(producto)
    return producto


@router.get("/{producto_id}", response_model=ProductoOut)
def obtener_producto(producto_id: int, db: Session = Depends(get_db)):
    producto = db.get(Producto, producto_id)
    if not producto:
        raise HTTPException(404, "Producto no encontrado")
    return producto


@router.get("/{producto_id}/precios", response_model=list[PrecioHistoricoOut])
def historial_precios(producto_id: int, db: Session = Depends(get_db)):
    if not db.get(Producto, producto_id):
        raise HTTPException(404, "Producto no encontrado")
    return (
        db.query(PrecioHistorico)
        .filter(PrecioHistorico.producto_id == producto_id)
        .order_by(PrecioHistorico.id.desc())
        .all()
    )


# ---------- 451 Precios de competencia ----------
@router.get("/{producto_id}/precios-competencia", response_model=list[PrecioCompetenciaOut])
def listar_precios_competencia(producto_id: int, db: Session = Depends(get_db)):
    if not db.get(Producto, producto_id):
        raise HTTPException(404, "Producto no encontrado")
    return (
        db.query(PrecioCompetencia)
        .filter(PrecioCompetencia.producto_id == producto_id)
        .order_by(PrecioCompetencia.fecha.desc())
        .all()
    )


@router.post("/{producto_id}/precios-competencia", response_model=PrecioCompetenciaOut, status_code=201)
def crear_precio_competencia(
    producto_id: int,
    data: PrecioCompetenciaCreate,
    db: Session = Depends(get_db),
):
    if not db.get(Producto, producto_id):
        raise HTTPException(404, "Producto no encontrado")
    reg = PrecioCompetencia(producto_id=producto_id, **data.model_dump())
    db.add(reg)
    db.commit()
    db.refresh(reg)
    return reg


@router.delete("/precios-competencia/{precio_id}", status_code=204)
def eliminar_precio_competencia(precio_id: int, db: Session = Depends(get_db)):
    reg = db.get(PrecioCompetencia, precio_id)
    if not reg:
        raise HTTPException(404, "Registro de competencia no encontrado")
    db.delete(reg)
    db.commit()


@router.put("/{producto_id}", response_model=ProductoOut)
def actualizar_producto(
    producto_id: int,
    data: ProductoUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    producto = db.get(Producto, producto_id)
    if not producto:
        raise HTTPException(404, "Producto no encontrado")
    _registrar_precios(db, producto, data, usuario)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(producto, k, v)
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="productos",
            accion="editar",
            entidad="producto",
            entidad_id=producto.id,
            detalle=f"Producto editado: {producto.nombre}",
        )
    )
    db.commit()
    db.refresh(producto)
    return producto


@router.get("/{producto_id}/codigo-barras", response_class=HTMLResponse)
def codigo_barras_producto(
    producto_id: int,
    altura: int = Query(40, ge=10, le=200),
    ancho: int = Query(170, ge=50, le=600),
    mostrar: bool = Query(True),
    db: Session = Depends(get_db),
):
    producto = db.get(Producto, producto_id)
    if not producto:
        raise HTTPException(404, "Producto no encontrado")
    e13 = codigo_para_producto(producto.id, producto.codigo_barras)
    return HTMLResponse(svg_ean13(e13, altura=altura, ancho=ancho, mostrar=mostrar))