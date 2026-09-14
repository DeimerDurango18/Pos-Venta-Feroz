from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Caja, Empresa, PuntoVenta, Sucursal, Usuario
from ..schemas.organizacion import (
    CajaCreate,
    CajaOut,
    CajaUpdate,
    EmpresaCreate,
    EmpresaOut,
    EmpresaUpdate,
    PuntoVentaCreate,
    PuntoVentaOut,
    SucursalCreate,
    SucursalOut,
    SucursalUpdate,
)

router = APIRouter(prefix="/organizacion", tags=["organizacion"])


# ---------- Empresas ----------
@router.get("/empresas", response_model=list[EmpresaOut])
def listar_empresas(db: Session = Depends(get_db)):
    return db.query(Empresa).all()


@router.post("/empresas", response_model=EmpresaOut, status_code=201)
def crear_empresa(data: EmpresaCreate, db: Session = Depends(get_db)):
    if db.query(Empresa).filter(Empresa.nit == data.nit).first():
        raise HTTPException(400, "Ya existe una empresa con ese NIT")
    empresa = Empresa(**data.model_dump())
    db.add(empresa)
    db.commit()
    db.refresh(empresa)
    return empresa


@router.get("/empresas/{empresa_id}", response_model=EmpresaOut)
def obtener_empresa(empresa_id: int, db: Session = Depends(get_db)):
    empresa = db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(404, "Empresa no encontrada")
    return empresa


@router.put("/empresas/{empresa_id}", response_model=EmpresaOut)
def actualizar_empresa(
    empresa_id: int, data: EmpresaUpdate, db: Session = Depends(get_db)
):
    empresa = db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(404, "Empresa no encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(empresa, k, v)
    db.commit()
    db.refresh(empresa)
    return empresa


# ---------- Sucursales ----------
@router.get("/sucursales", response_model=list[SucursalOut])
def listar_sucursales(db: Session = Depends(get_db)):
    return db.query(Sucursal).all()


@router.post("/sucursales", response_model=SucursalOut, status_code=201)
def crear_sucursal(data: SucursalCreate, db: Session = Depends(get_db)):
    if not db.get(Empresa, data.empresa_id):
        raise HTTPException(400, "Empresa no existe")
    sucursal = Sucursal(**data.model_dump())
    db.add(sucursal)
    db.commit()
    db.refresh(sucursal)
    return sucursal


@router.put("/sucursales/{sucursal_id}", response_model=SucursalOut)
def actualizar_sucursal(
    sucursal_id: int, data: SucursalUpdate, db: Session = Depends(get_db)
):
    sucursal = db.get(Sucursal, sucursal_id)
    if not sucursal:
        raise HTTPException(404, "Sucursal no encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(sucursal, k, v)
    db.commit()
    db.refresh(sucursal)
    return sucursal


# ---------- Puntos de venta ----------
@router.get("/puntos-venta", response_model=list[PuntoVentaOut])
def listar_puntos_venta(db: Session = Depends(get_db)):
    return db.query(PuntoVenta).all()


@router.post("/puntos-venta", response_model=PuntoVentaOut, status_code=201)
def crear_punto_venta(data: PuntoVentaCreate, db: Session = Depends(get_db)):
    if not db.get(Sucursal, data.sucursal_id):
        raise HTTPException(400, "Sucursal no existe")
    pv = PuntoVenta(**data.model_dump())
    db.add(pv)
    db.commit()
    db.refresh(pv)
    return pv


# ---------- Cajas ----------
@router.get("/cajas", response_model=list[CajaOut])
def listar_cajas(db: Session = Depends(get_db)):
    return db.query(Caja).all()


@router.post("/cajas", response_model=CajaOut, status_code=201)
def crear_caja(data: CajaCreate, db: Session = Depends(get_db)):
    if not db.get(PuntoVenta, data.punto_venta_id):
        raise HTTPException(400, "Punto de venta no existe")
    caja = Caja(**data.model_dump())
    if data.es_principal:
        for otra in db.query(Caja).filter(Caja.id != 0).all():
            otra.es_principal = False
    db.add(caja)
    db.commit()
    db.refresh(caja)
    return caja


@router.put("/cajas/{caja_id}", response_model=CajaOut)
def actualizar_caja(
    caja_id: int, data: CajaUpdate, db: Session = Depends(get_db)
):
    caja = db.get(Caja, caja_id)
    if not caja:
        raise HTTPException(404, "Caja no encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(caja, k, v)
    if data.es_principal:
        for otra in db.query(Caja).filter(Caja.id != caja_id).all():
            otra.es_principal = False
    db.commit()
    db.refresh(caja)
    return caja