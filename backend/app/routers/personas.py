from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Cliente, Empresa, Proveedor
from ..schemas.personas import (
    ClienteCreate,
    ClienteOut,
    ClienteUpdate,
    ProveedorCreate,
    ProveedorOut,
    ProveedorUpdate,
)

router = APIRouter(tags=["personas"])


# ---------- Clientes ----------
@router.get("/clientes", response_model=list[ClienteOut])
def listar_clientes(
    q: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Cliente)
    if q:
        busqueda = f"%{q}%"
        query = query.filter(
            or_(
                Cliente.nombre.ilike(busqueda),
                Cliente.documento.ilike(busqueda),
                Cliente.telefono.ilike(busqueda),
            )
        )
    return query.order_by(Cliente.nombre).all()


@router.post("/clientes", response_model=ClienteOut, status_code=201)
def crear_cliente(data: ClienteCreate, empresa_id: int, db: Session = Depends(get_db)):
    if not db.get(Empresa, empresa_id):
        raise HTTPException(400, "Empresa no existe")
    cliente = Cliente(empresa_id=empresa_id, **data.model_dump())
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return cliente


@router.get("/clientes/{cliente_id}", response_model=ClienteOut)
def obtener_cliente(cliente_id: int, db: Session = Depends(get_db)):
    cliente = db.get(Cliente, cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    return cliente


@router.put("/clientes/{cliente_id}", response_model=ClienteOut)
def actualizar_cliente(
    cliente_id: int, data: ClienteUpdate, db: Session = Depends(get_db)
):
    cliente = db.get(Cliente, cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(cliente, k, v)
    db.commit()
    db.refresh(cliente)
    return cliente


# ---------- Proveedores ----------
@router.get("/proveedores", response_model=list[ProveedorOut])
def listar_proveedores(
    q: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Proveedor)
    if q:
        busqueda = f"%{q}%"
        query = query.filter(
            or_(
                Proveedor.nombre.ilike(busqueda),
                Proveedor.nit.ilike(busqueda),
                Proveedor.telefono.ilike(busqueda),
            )
        )
    return query.order_by(Proveedor.nombre).all()


@router.post("/proveedores", response_model=ProveedorOut, status_code=201)
def crear_proveedor(data: ProveedorCreate, empresa_id: int, db: Session = Depends(get_db)):
    if not db.get(Empresa, empresa_id):
        raise HTTPException(400, "Empresa no existe")
    prov = Proveedor(empresa_id=empresa_id, **data.model_dump())
    db.add(prov)
    db.commit()
    db.refresh(prov)
    return prov


@router.put("/proveedores/{proveedor_id}", response_model=ProveedorOut)
def actualizar_proveedor(
    proveedor_id: int, data: ProveedorUpdate, db: Session = Depends(get_db)
):
    prov = db.get(Proveedor, proveedor_id)
    if not prov:
        raise HTTPException(404, "Proveedor no encontrado")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(prov, k, v)
    db.commit()
    db.refresh(prov)
    return prov