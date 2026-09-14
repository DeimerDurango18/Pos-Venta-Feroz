from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_permiso
from ..models import (
    AuditoriaLog,
    Bodega,
    ConteoFisico,
    ConteoFisicoDetalle,
    InventarioTransito,
    Lote,
    MovimientoInventario,
    Producto,
    Stock,
    StockBodega,
    Sucursal,
    Ubicacion,
    Usuario,
)
from ..schemas.avanzado import ConteoFisicoCreate, ConteoFisicoOut
from ..schemas.inventario import (
    AjusteStock,
    BodegaCreate,
    BodegaOut,
    LoteCreate,
    LoteMovimiento,
    LoteOut,
    MovimientoInventarioCreate,
    MovimientoInventarioOut,
    RecibirTransito,
    StockBodegaMovimiento,
    StockBodegaOut,
    StockOut,
    TransferenciaBodegaCreate,
    TransferenciaStock,
    UbicacionCreate,
    UbicacionOut,
)

router = APIRouter(prefix="/inventario", tags=["inventario"])


def _config(db: Session, clave: str, valor: str | None = None):
    """Lee o fija una configuración global (clave=valor)."""
    from ..models import Configuracion

    if valor is None:
        row = db.query(Configuracion).filter(Configuracion.clave == clave).first()
        return row.valor if row else None
    row = db.query(Configuracion).filter(Configuracion.clave == clave).first()
    if row:
        row.valor = valor
    else:
        db.add(Configuracion(clave=clave, valor=valor))
    return valor


def _boolean(valor) -> bool:
    return str(valor or "").strip().lower() in ("1", "true", "si", "sí", "on")


def _obtener_o_crear_stock(db: Session, producto_id: int, sucursal_id: int) -> Stock:
    stock = (
        db.query(Stock)
        .filter_by(producto_id=producto_id, sucursal_id=sucursal_id)
        .first()
    )
    if not stock:
        stock = Stock(producto_id=producto_id, sucursal_id=sucursal_id)
        db.add(stock)
        db.flush()
    return stock


def _registrar_movimiento(
    db: Session,
    producto_id: int,
    sucursal_id: int,
    tipo: str,
    cantidad: float,
    motivo: str | None,
    referencia: str | None,
    saldo: float,
):
    mov = MovimientoInventario(
        producto_id=producto_id,
        sucursal_id=sucursal_id,
        tipo=tipo,
        cantidad=cantidad,
        motivo=motivo,
        referencia=referencia,
        saldo=saldo,
    )
    db.add(mov)
    return mov


@router.get("/stock", response_model=list[StockOut])
def listar_stock(
    sucursal_id: int | None = None,
    producto_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Stock)
    if sucursal_id:
        query = query.filter(Stock.sucursal_id == sucursal_id)
    if producto_id:
        query = query.filter(Stock.producto_id == producto_id)
    return query.all()


@router.get("/producto/{producto_id}", response_model=StockOut)
def stock_producto(producto_id: int, sucursal_id: int, db: Session = Depends(get_db)):
    stock = (
        db.query(Stock)
        .filter_by(producto_id=producto_id, sucursal_id=sucursal_id)
        .first()
    )
    if not stock:
        raise HTTPException(404, "Sin stock registrado")
    return stock


@router.post("/movimientos", response_model=MovimientoInventarioOut, status_code=201)
def crear_movimiento(
    data: MovimientoInventarioCreate, db: Session = Depends(get_db)
):
    if not db.get(Producto, data.producto_id):
        raise HTTPException(400, "Producto no existe")
    stock = _obtener_o_crear_stock(db, data.producto_id, data.sucursal_id)

    if data.tipo == "entrada":
        stock.existencias = float(stock.existencias or 0) + data.cantidad
        cant = data.cantidad
    elif data.tipo == "salida":
        if float(stock.existencias or 0) < data.cantidad and not _boolean(_config(db, "pos.inventario_negativo")):
            raise HTTPException(400, "Stock insuficiente")
        stock.existencias = float(stock.existencias or 0) - data.cantidad
        cant = -data.cantidad
    elif data.tipo == "ajuste":
        stock.existencias = data.cantidad
        cant = data.cantidad
    else:
        raise HTTPException(400, "Tipo de movimiento inválido")

    stock.disponible = stock.existencias - float(stock.reservado or 0)
    mov = _registrar_movimiento(
        db, data.producto_id, data.sucursal_id, data.tipo,
        cant, data.motivo, data.referencia, float(stock.existencias),
    )
    db.commit()
    db.refresh(mov)
    return mov


@router.post("/ajustar", status_code=201)
def ajustar_stock(data: AjusteStock, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    from ..seguridad import requiere_autorizacion

    requiere_autorizacion(
        db, usuario, "inventario", "ajustar",
        entidad="producto", entidad_id=data.producto_id,
        datos={"sucursal_id": data.sucursal_id, "existencias": data.existencias, "motivo": data.motivo},
    )
    stock = _obtener_o_crear_stock(db, data.producto_id, data.sucursal_id)
    diferencia = data.existencias - float(stock.existencias or 0)
    stock.existencias = data.existencias
    stock.disponible = stock.existencias - float(stock.reservado or 0)
    _registrar_movimiento(
        db, data.producto_id, data.sucursal_id, "ajuste",
        diferencia, data.motivo, "ajuste manual", data.existencias,
    )
    db.commit()
    return {"ok": True, "producto_id": data.producto_id, "existencias": data.existencias}


@router.post("/transferir", status_code=201)
def transferir_stock(data: TransferenciaStock, db: Session = Depends(get_db)):
    if data.origen_sucursal_id == data.destino_sucursal_id:
        raise HTTPException(400, "Las sucursales deben ser diferentes")
    origen = _obtener_o_crear_stock(db, data.producto_id, data.origen_sucursal_id)
    destino = _obtener_o_crear_stock(db, data.producto_id, data.destino_sucursal_id)
    if float(origen.existencias or 0) < data.cantidad:
        raise HTTPException(400, "Stock insuficiente en origen")
    origen.existencias = float(origen.existencias or 0) - data.cantidad
    destino.existencias = float(destino.existencias or 0) + data.cantidad
    origen.disponible = origen.existencias - float(origen.reservado or 0)
    destino.disponible = destino.existencias - float(destino.reservado or 0)
    _registrar_movimiento(
        db, data.producto_id, data.origen_sucursal_id, "traslado",
        -data.cantidad, data.motivo, f"hacia sucursal {data.destino_sucursal_id}",
        float(origen.existencias),
    )
    _registrar_movimiento(
        db, data.producto_id, data.destino_sucursal_id, "traslado",
        data.cantidad, data.motivo, f"desde sucursal {data.origen_sucursal_id}",
        float(destino.existencias),
    )
    db.commit()
    return {"ok": True}


@router.get("/movimientos", response_model=list[MovimientoInventarioOut])
def listar_movimientos(
    producto_id: int | None = None,
    sucursal_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(MovimientoInventario)
    if producto_id:
        query = query.filter(MovimientoInventario.producto_id == producto_id)
    if sucursal_id:
        query = query.filter(MovimientoInventario.sucursal_id == sucursal_id)
    return query.order_by(MovimientoInventario.id.desc()).limit(200).all()


# ---------- Mermas / dañados / vencidos ----------
@router.post("/mermas", status_code=201)
def registrar_merma(
    producto_id: int,
    cantidad: float,
    sucursal_id: int,
    motivo: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Registra merma/daño/producto vencido: sale del inventario."""
    from ..seguridad import requiere_autorizacion

    requiere_autorizacion(
        db, usuario, "inventario", "ajustar",
        entidad="producto", entidad_id=producto_id,
        datos={"sucursal_id": sucursal_id, "cantidad": cantidad, "motivo": motivo},
    )
    stock = _obtener_o_crear_stock(db, producto_id, sucursal_id)
    if float(stock.existencias or 0) < cantidad:
        raise HTTPException(400, "Stock insuficiente")
    stock.existencias = float(stock.existencias or 0) - cantidad
    stock.disponible = stock.existencias - float(stock.reservado or 0)
    _registrar_movimiento(
        db, producto_id, sucursal_id, "merma",
        -cantidad, motivo, "merma", float(stock.existencias),
    )
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="inventario",
            accion="merma",
            entidad="producto",
            entidad_id=producto_id,
            detalle=f"Merma de {cantidad} unidades: {motivo}",
        )
    )
    db.commit()
    return {"ok": True, "existencias": float(stock.existencias)}


# ---------- Conteo físico ----------
@router.post("/conteos", response_model=ConteoFisicoOut, status_code=201)
def crear_conteo(
    data: ConteoFisicoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    conteo = ConteoFisico(
        empresa_id=data.empresa_id,
        sucursal_id=data.sucursal_id,
        usuario_id=usuario.id,
        tipo=data.tipo or "fisico",
        observacion=data.observacion,
        estado="abierto",
    )
    db.add(conteo)
    db.flush()
    conteo.numero = f"CF-{conteo.id:06d}"
    for linea in data.detalle:
        stock = _obtener_o_crear_stock(db, linea.producto_id, data.sucursal_id)
        esperado = float(stock.existencias or 0)
        diferencia = float(linea.contado) - esperado
        db.add(
            ConteoFisicoDetalle(
                conteo_id=conteo.id,
                producto_id=linea.producto_id,
                esperado=esperado,
                contado=linea.contado,
                diferencia=diferencia,
            )
        )
    db.commit()
    db.refresh(conteo)
    return conteo


@router.get("/conteos", response_model=list[ConteoFisicoOut])
def listar_conteos(
    sucursal_id: int | None = None,
    tipo: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(ConteoFisico)
    if sucursal_id:
        q = q.filter(ConteoFisico.sucursal_id == sucursal_id)
    if tipo:
        q = q.filter(ConteoFisico.tipo == tipo)
    return q.order_by(ConteoFisico.id.desc()).all()


@router.post("/conteos/{conteo_id}/liquidar")
def liquidar_conteo(
    conteo_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Aplica las diferencias del conteo al inventario y lo cierra."""
    from ..seguridad import requiere_autorizacion

    conteo = db.get(ConteoFisico, conteo_id)
    if not conteo or conteo.estado != "abierto":
        raise HTTPException(400, "Conteo no válido")
    requiere_autorizacion(
        db, usuario, "inventario", "ajustar",
        entidad="conteo_fisico", entidad_id=conteo_id,
        datos={"numero": conteo.numero},
    )
    ajustes = 0
    for linea in conteo.detalle:
        if float(linea.diferencia or 0) == 0:
            continue
        stock = _obtener_o_crear_stock(db, linea.producto_id, conteo.sucursal_id)
        stock.existencias = float(stock.existencias or 0) + float(linea.diferencia)
        stock.disponible = stock.existencias - float(stock.reservado or 0)
        _registrar_movimiento(
            db, linea.producto_id, conteo.sucursal_id, "ajuste",
            float(linea.diferencia), f"Conteo físico {conteo.numero}",
            conteo.numero, float(stock.existencias),
        )
        ajustes += 1
    conteo.estado = "liquidado"
    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="inventario",
            accion="conteo",
            entidad="conteo",
            entidad_id=conteo.id,
            detalle=f"Conteo {conteo.numero} liquidado con {ajustes} ajustes",
        )
    )
    db.commit()
    return {"ok": True, "estado": conteo.estado, "ajustes_aplicados": ajustes}


# ============================================================
#  Multibodega: bodegas, ubicaciones, stock por bodega y
#  transferencias (incluye inventario en tránsito)
# ============================================================

def _obtener_stock_bodega(
    db: Session, producto_id: int, bodega_id: int, ubicacion_id: int | None
) -> StockBodega:
    if ubicacion_id is not None:
        fila = (
            db.query(StockBodega)
            .filter_by(producto_id=producto_id, bodega_id=bodega_id, ubicacion_id=ubicacion_id)
            .first()
        )
    else:
        fila = (
            db.query(StockBodega)
            .filter_by(producto_id=producto_id, bodega_id=bodega_id, ubicacion_id=None)
            .first()
        )
    if not fila:
        bodega = db.get(Bodega, bodega_id)
        if not bodega:
            raise HTTPException(404, "Bodega no existe")
        fila = StockBodega(
            producto_id=producto_id,
            sucursal_id=bodega.sucursal_id,
            bodega_id=bodega_id,
            ubicacion_id=ubicacion_id,
        )
        db.add(fila)
        db.flush()
    return fila


def _sync_stock_sucursal(db: Session, producto_id: int, sucursal_id: int, delta: float):
    stock = (
        db.query(Stock)
        .filter_by(producto_id=producto_id, sucursal_id=sucursal_id)
        .first()
    )
    if not stock:
        stock = Stock(producto_id=producto_id, sucursal_id=sucursal_id)
        db.add(stock)
        db.flush()
    stock.existencias = float(stock.existencias or 0) + delta
    stock.disponible = float(stock.existencias or 0) - float(stock.reservado or 0)
    return stock


@router.get("/bodegas", response_model=list[BodegaOut])
def listar_bodegas(
    sucursal_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Bodega)
    if sucursal_id:
        q = q.filter(Bodega.sucursal_id == sucursal_id)
    return q.order_by(Bodega.id.asc()).all()


@router.post("/bodegas", response_model=BodegaOut, status_code=201)
def crear_bodega(data: BodegaCreate, db: Session = Depends(get_db)):
    bodega = Bodega(
        empresa_id=data.empresa_id,
        sucursal_id=data.sucursal_id,
        nombre=data.nombre,
        codigo=data.codigo,
        direccion=data.direccion,
        activa=data.activa,
    )
    db.add(bodega)
    db.commit()
    db.refresh(bodega)
    return bodega


@router.put("/bodegas/{bodega_id}")
def actualizar_bodega(bodega_id: int, data: BodegaCreate, db: Session = Depends(get_db)):
    bodega = db.get(Bodega, bodega_id)
    if not bodega:
        raise HTTPException(404, "Bodega no existe")
    bodega.nombre = data.nombre
    bodega.codigo = data.codigo
    bodega.direccion = data.direccion
    bodega.activa = data.activa
    db.commit()
    return {"ok": True, "id": bodega.id}


@router.post("/bodegas/{bodega_id}/ubicaciones", response_model=UbicacionOut, status_code=201)
def crear_ubicacion(bodega_id: int, data: UbicacionCreate, db: Session = Depends(get_db)):
    if not db.get(Bodega, bodega_id):
        raise HTTPException(404, "Bodega no existe")
    ubicacion = Ubicacion(bodega_id=bodega_id, nombre=data.nombre, codigo=data.codigo)
    db.add(ubicacion)
    db.commit()
    db.refresh(ubicacion)
    return ubicacion


@router.get("/bodegas/{bodega_id}/ubicaciones", response_model=list[UbicacionOut])
def listar_ubicaciones(bodega_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Ubicacion)
        .filter(Ubicacion.bodega_id == bodega_id)
        .order_by(Ubicacion.id.asc())
        .all()
    )


@router.post("/stock-bodega", response_model=StockBodegaOut, status_code=201)
def mover_stock_bodega(data: StockBodegaMovimiento, db: Session = Depends(get_db)):
    """Entrada/salida/ajuste/reubicación de existencias por bodega/ubicación.
    Mantiene sincronizado el Stock agregado de la sucursal."""
    if not db.get(Producto, data.producto_id):
        raise HTTPException(400, "Producto no existe")
    bodega = db.get(Bodega, data.bodega_id)
    if not bodega:
        raise HTTPException(404, "Bodega no existe")
    if data.ubicacion_id is not None and not db.get(Ubicacion, data.ubicacion_id):
        raise HTTPException(404, "Ubicación no existe")
    if not _boolean(_config(db, "pos.inventario_negativo")) and data.cantidad < 0:
        raise HTTPException(400, "La cantidad debe ser positiva; use tipo=salida")

    fila = _obtener_stock_bodega(db, data.producto_id, data.bodega_id, data.ubicacion_id)

    if data.tipo == "entrada":
        fila.existencias = float(fila.existencias or 0) + data.cantidad
        delta = data.cantidad
    elif data.tipo == "salida":
        if float(fila.existencias or 0) < data.cantidad and not _boolean(_config(db, "pos.inventario_negativo")):
            raise HTTPException(400, "Stock insuficiente en bodega")
        fila.existencias = float(fila.existencias or 0) - data.cantidad
        delta = -data.cantidad
    elif data.tipo == "ajuste":
        delta = data.cantidad - float(fila.existencias or 0)
        fila.existencias = data.cantidad
    elif data.tipo == "reubicar":
        if not data.ubicacion_id:
            raise HTTPException(400, "reubicar requiere ubicacion_id de destino")
        origen = _obtener_stock_bodega(db, data.producto_id, data.bodega_id, None)
        destino = _obtener_stock_bodega(db, data.producto_id, data.bodega_id, data.ubicacion_id)
        if float(origen.existencias or 0) < data.cantidad:
            raise HTTPException(400, "Stock insuficiente en ubicación de origen")
        origen.existencias = float(origen.existencias or 0) - data.cantidad
        destino.existencias = float(destino.existencias or 0) + data.cantidad
        db.commit()
        db.refresh(destino)
        return destino
    else:
        raise HTTPException(400, "Tipo de movimiento inválido")

    fila.disponible = float(fila.existencias or 0) - float(fila.reservado or 0)
    _sync_stock_sucursal(db, data.producto_id, bodega.sucursal_id, delta)
    _registrar_movimiento(
        db, data.producto_id, bodega.sucursal_id, "bodega",
        data.cantidad if data.tipo == "entrada" else -data.cantidad if data.tipo == "salida" else delta,
        data.motivo or f"bodega {bodega.nombre}",
        f"bodega {bodega.id}", float(fila.existencias),
    )
    db.commit()
    db.refresh(fila)
    return fila


@router.get("/por-bodega")
def inventario_por_bodega(
    bodega_id: int | None = None,
    producto_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = (
        db.query(
            StockBodega.producto_id,
            StockBodega.bodega_id,
            Bodega.nombre.label("bodega"),
            Producto.nombre.label("producto"),
            func.sum(StockBodega.existencias).label("existencias"),
        )
        .join(Producto, Producto.id == StockBodega.producto_id)
        .join(Bodega, Bodega.id == StockBodega.bodega_id)
        .group_by(StockBodega.producto_id, StockBodega.bodega_id, Bodega.nombre, Producto.nombre)
    )
    if bodega_id:
        q = q.filter(StockBodega.bodega_id == bodega_id)
    if producto_id:
        q = q.filter(StockBodega.producto_id == producto_id)
    filas = q.order_by(Bodega.nombre.asc()).all()
    return [
        {
            "producto_id": pid,
            "producto": pnombre,
            "bodega_id": bid,
            "bodega": bnombre,
            "existencias": float(exist or 0),
        }
        for pid, bid, bnombre, pnombre, exist in filas
    ]


@router.get("/por-ubicacion")
def inventario_por_ubicacion(
    bodega_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = (
        db.query(
            StockBodega.bodega_id,
            StockBodega.ubicacion_id,
            Bodega.nombre.label("bodega"),
            StockBodega.producto_id,
            Producto.nombre.label("producto"),
            func.sum(StockBodega.existencias).label("existencias"),
        )
        .join(Producto, Producto.id == StockBodega.producto_id)
        .join(Bodega, Bodega.id == StockBodega.bodega_id)
        .group_by(
            StockBodega.bodega_id, StockBodega.ubicacion_id, Bodega.nombre,
            StockBodega.producto_id, Producto.nombre,
        )
    )
    if bodega_id:
        q = q.filter(StockBodega.bodega_id == bodega_id)
    nombres_ubic = {u.id: u.nombre for u in db.query(Ubicacion).all()}
    filas = q.order_by(Bodega.nombre.asc()).all()
    return [
        {
            "bodega_id": bid,
            "bodega": bnombre,
            "ubicacion_id": uid,
            "ubicacion": nombres_ubic.get(uid) if uid is not None else "General",
            "producto_id": pid,
            "producto": pnombre,
            "existencias": float(exist or 0),
        }
        for bid, uid, bnombre, pid, pnombre, exist in filas
    ]


@router.post("/transferir-bodega", status_code=201)
def transferir_entre_bodegas(data: TransferenciaBodegaCreate, db: Session = Depends(get_db)):
    """Transfiere existencias entre bodegas. Si son de la MISMA sucursal se aplica
    directo; si son de DIFERENTES sucursales queda 'en tránsito' hasta recibirse."""
    origen = db.get(Bodega, data.origen_bodega_id)
    destino = db.get(Bodega, data.destino_bodega_id)
    if not origen or not destino:
        raise HTTPException(404, "Bodega no existe")
    if data.origen_bodega_id == data.destino_bodega_id:
        raise HTTPException(400, "Las bodegas deben ser diferentes")

    fila_origen = _obtener_stock_bodega(db, data.producto_id, data.origen_bodega_id, data.origen_ubicacion_id)
    if float(fila_origen.existencias or 0) < data.cantidad:
        raise HTTPException(400, "Stock insuficiente en bodega de origen")
    fila_origen.existencias = float(fila_origen.existencias or 0) - data.cantidad
    fila_origen.disponible = float(fila_origen.existencias or 0) - float(fila_origen.reservado or 0)
    _sync_stock_sucursal(db, data.producto_id, origen.sucursal_id, -data.cantidad)

    if origen.sucursal_id == destino.sucursal_id:
        destino_fila = _obtener_stock_bodega(db, data.producto_id, data.destino_bodega_id, data.destino_ubicacion_id)
        destino_fila.existencias = float(destino_fila.existencias or 0) + data.cantidad
        destino_fila.disponible = float(destino_fila.existencias or 0) - float(destino_fila.reservado or 0)
        _sync_stock_sucursal(db, data.producto_id, destino.sucursal_id, data.cantidad)
        _registrar_movimiento(
            db, data.producto_id, origen.sucursal_id, "traslado",
            -data.cantidad, data.motivo or "transferencia entre bodegas",
            f"bodega {origen.id} -> {destino.id}", float(fila_origen.existencias),
        )
        _registrar_movimiento(
            db, data.producto_id, destino.sucursal_id, "traslado",
            data.cantidad, data.motivo or "transferencia entre bodegas",
            f"bodega {origen.id} -> {destino.id}", float(destino_fila.existencias),
        )
        db.commit()
        return {"ok": True, "estado": "recibido", "transito": None}

    transito = InventarioTransito(
        producto_id=data.producto_id,
        origen_sucursal_id=origen.sucursal_id,
        origen_bodega_id=origen.id,
        destino_sucursal_id=destino.sucursal_id,
        destino_bodega_id=destino.id,
        cantidad=data.cantidad,
        estado="en_transito",
        referencia=data.motivo,
    )
    db.add(transito)
    db.commit()
    db.refresh(transito)
    return {"ok": True, "estado": "en_transito", "transito": {"id": transito.id, "cantidad": float(transito.cantidad)}}


@router.get("/transito")
def listar_transito(db: Session = Depends(get_db)):
    filas = db.query(InventarioTransito).filter(InventarioTransito.estado == "en_transito").all()
    nombres = {s.id: s.nombre for s in db.query(Sucursal).all()}
    bodegas = {b.id: b.nombre for b in db.query(Bodega).all()}
    return [
        {
            "id": t.id,
            "producto_id": t.producto_id,
            "cantidad": float(t.cantidad),
            "origen_sucursal": nombres.get(t.origen_sucursal_id),
            "origen_bodega": bodegas.get(t.origen_bodega_id),
            "destino_sucursal": nombres.get(t.destino_sucursal_id),
            "destino_bodega": bodegas.get(t.destino_bodega_id),
            "referencia": t.referencia,
            "creado": str(t.created_at),
        }
        for t in filas
    ]


@router.post("/transito/{transferencia_id}/recibir")
def recibir_transito(transferencia_id: int, db: Session = Depends(get_db)):
    transito = db.get(InventarioTransito, transferencia_id)
    if not transito or transito.estado != "en_transito":
        raise HTTPException(404, "Transferencia en tránsito no encontrada")
    fila_destino = _obtener_stock_bodega(db, transito.producto_id, transito.destino_bodega_id, None)
    fila_destino.existencias = float(fila_destino.existencias or 0) + float(transito.cantidad)
    fila_destino.disponible = float(fila_destino.existencias or 0) - float(fila_destino.reservado or 0)
    _sync_stock_sucursal(db, transito.producto_id, transito.destino_sucursal_id, float(transito.cantidad))
    _registrar_movimiento(
        db, transito.producto_id, transito.destino_sucursal_id, "traslado",
        float(transito.cantidad), "recepción de tránsito",
        f"tránsito {transito.id}", float(fila_destino.existencias),
    )
    transito.estado = "recibido"
    db.commit()
    return {"ok": True, "estado": transito.estado}


@router.post("/transito/{transferencia_id}/cancelar")
def cancelar_transito(transferencia_id: int, db: Session = Depends(get_db)):
    transito = db.get(InventarioTransito, transferencia_id)
    if not transito or transito.estado != "en_transito":
        raise HTTPException(404, "Transferencia en tránsito no encontrada")
    fila_origen = _obtener_stock_bodega(db, transito.producto_id, transito.origen_bodega_id, None)
    fila_origen.existencias = float(fila_origen.existencias or 0) + float(transito.cantidad)
    fila_origen.disponible = float(fila_origen.existencias or 0) - float(fila_origen.reservado or 0)
    _sync_stock_sucursal(db, transito.producto_id, transito.origen_sucursal_id, float(transito.cantidad))
    transito.estado = "cancelado"
    db.commit()
    return {"ok": True, "estado": transito.estado}


# ============================================================
#  Lotes y control de vencimientos
# ============================================================

@router.get("/lotes", response_model=list[LoteOut])
def listar_lotes(
    producto_id: int | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    q = db.query(Lote)
    if producto_id:
        q = q.filter(Lote.producto_id == producto_id)
    return q.order_by(Lote.id.desc()).all()


@router.post("/lotes", response_model=LoteOut, status_code=201)
def crear_lote(data: LoteCreate, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    if not db.get(Producto, data.producto_id):
        raise HTTPException(400, "Producto no existe")
    lote = Lote(
        producto_id=data.producto_id,
        codigo=data.codigo,
        vencimiento=data.vencimiento,
        cantidad=data.cantidad,
    )
    db.add(lote)
    db.flush()
    if data.cantidad:
        _sync_stock_sucursal(db, data.producto_id, usuario.sucursal_id or 1, data.cantidad)
    db.commit()
    db.refresh(lote)
    return lote


@router.post("/lotes/stock", status_code=201)
def lote_ingresar_stock(data: LoteMovimiento, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    """Ingresa mercancía a un lote (incrementa el stock de la sucursal del usuario)."""
    lote = db.get(Lote, data.lote_id)
    if not lote:
        raise HTTPException(404, "Lote no existe")
    if data.cantidad <= 0:
        raise HTTPException(400, "La cantidad debe ser positiva")
    lote.cantidad = float(lote.cantidad or 0) + data.cantidad
    sut = usuario.sucursal_id or 1
    _sync_stock_sucursal(db, lote.producto_id, sut, data.cantidad)
    _registrar_movimiento(
        db, lote.producto_id, sut, "entrada", data.cantidad,
        data.motivo or "entrada por lote", f"lote {lote.codigo}",
        float(db.query(Stock).filter_by(producto_id=lote.producto_id, sucursal_id=sut).first().existencias),
    )
    db.commit()
    return {"ok": True, "lote": lote.codigo, "cantidad": float(lote.cantidad)}


@router.post("/lotes/salida", status_code=201)
def lote_salir_stock(data: LoteMovimiento, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    """Despacha mercancía desde un lote validando disponibilidad."""
    lote = db.get(Lote, data.lote_id)
    if not lote:
        raise HTTPException(404, "Lote no existe")
    if data.cantidad <= 0:
        raise HTTPException(400, "La cantidad debe ser positiva")
    if float(lote.cantidad or 0) < data.cantidad and not _boolean(_config(db, "pos.inventario_negativo")):
        raise HTTPException(400, f"Stock insuficiente en el lote {lote.codigo}")
    lote.cantidad = float(lote.cantidad or 0) - data.cantidad
    sut = usuario.sucursal_id or 1
    _sync_stock_sucursal(db, lote.producto_id, sut, -data.cantidad)
    stock = db.query(Stock).filter_by(producto_id=lote.producto_id, sucursal_id=sut).first()
    _registrar_movimiento(
        db, lote.producto_id, sut, "salida", -data.cantidad,
        data.motivo or "salida por lote", f"lote {lote.codigo}",
        float(stock.existencias) if stock else 0,
    )
    db.commit()
    return {"ok": True, "lote": lote.codigo, "cantidad": float(lote.cantidad)}


@router.get("/por-lote")
def inventario_por_lote(
    producto_id: int | None = None,
    db: Session = Depends(get_db),
):
    from datetime import date

    hoy = date.today()
    nombres = {p.id: p.nombre for p in db.query(Producto).all()}
    q = db.query(Lote)
    if producto_id:
        q = q.filter(Lote.producto_id == producto_id)
    from sqlalchemy import case
    filas = q.filter(Lote.cantidad > 0).order_by(case((Lote.vencimiento.is_(None), 1), else_=0), Lote.vencimiento.asc()).all()
    return [
        {
            "lote_id": l.id,
            "producto_id": l.producto_id,
            "producto": nombres.get(l.producto_id),
            "codigo": l.codigo,
            "vencimiento": str(l.vencimiento) if l.vencimiento else None,
            "dias_para_vencer": (l.vencimiento - hoy).days if l.vencimiento else None,
            "estado": "vencido" if l.vencimiento and l.vencimiento < hoy else "vigente",
            "cantidad": float(l.cantidad or 0),
        }
        for l in filas
    ]


@router.get("/sugerir-reposicion")
def sugerir_reposicion(sucursal_id: int = 1, db: Session = Depends(get_db)):
    """Sugerencia de reposición: productos bajo el punto de reorden."""
    productos = db.query(Producto).filter(Producto.activo == True).all()
    stocks = {
        s.producto_id: float(s.disponible if s.disponible is not None else s.existencias)
        for s in db.query(Stock).filter(Stock.sucursal_id == sucursal_id).all()
    }
    sugerencias = []
    for p in productos:
        existencias = stocks.get(p.id, 0.0)
        minimo = float(p.punto_reorden if p.punto_reorden else (p.stock_minimo or 0))
        maximo = float(p.stock_maximo or 0)
        if minimo > 0 and existencias < minimo:
            sugerencias.append(
                {
                    "producto_id": p.id,
                    "producto": p.nombre,
                    "codigo": p.codigo_barras or p.sku or p.plu or "",
                    "existencias": existencias,
                    "punto_reorden": minimo,
                    "stock_maximo": maximo,
                    "cantidad_sugerida": max(minimo * 2, maximo - existencias) if maximo else minimo * 2 - existencias,
                }
            )
    sugerencias.sort(key=lambda s: s["existencias"] / max(s["punto_reorden"], 0.001))
    return {"total": len(sugerencias), "sugerencias": sugerencias}