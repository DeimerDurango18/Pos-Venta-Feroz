from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import MetaVendedor, ReglaComision, Usuario
from ..schemas.avanzado import (
    MetaVendedorCreate,
    MetaVendedorOut,
    ReglaComisionCreate,
    ReglaComisionOut,
)

router = APIRouter(prefix="/vendedores", tags=["vendedores"])


@router.get("")
def listar_vendedores(db: Session = Depends(get_db)):
    vendedores = db.query(Usuario).filter(Usuario.vendedor == True).all()
    metas = {m.vendedor_id: m for m in db.query(MetaVendedor).all()}
    return [
        {
            "id": v.id,
            "nombre": v.nombre,
            "username": v.username,
            "meta_actual": {
                "periodo": m.periodo,
                "meta_ventas": float(m.meta_ventas or 0),
                "meta_utilidad": float(m.meta_utilidad or 0),
            }
            if (m := metas.get(v.id))
            else None,
        }
        for v in vendedores
    ]


@router.post("/metas", response_model=MetaVendedorOut, status_code=201)
def crear_meta(data: MetaVendedorCreate, db: Session = Depends(get_db)):
    if not db.get(Usuario, data.vendedor_id):
        raise HTTPException(400, "Vendedor no existe")
    meta = (
        db.query(MetaVendedor)
        .filter_by(vendedor_id=data.vendedor_id, periodo=data.periodo)
        .first()
    )
    if meta:
        meta.meta_ventas = data.meta_ventas
        meta.meta_utilidad = data.meta_utilidad
    else:
        meta = MetaVendedor(**data.model_dump())
        db.add(meta)
    db.commit()
    db.refresh(meta)
    return meta


@router.post("/reglas-comision", response_model=ReglaComisionOut, status_code=201)
def crear_regla(data: ReglaComisionCreate, db: Session = Depends(get_db)):
    regla = ReglaComision(**data.model_dump())
    db.add(regla)
    db.commit()
    db.refresh(regla)
    return regla


@router.get("/reglas-comision", response_model=list[ReglaComisionOut])
def listar_reglas(db: Session = Depends(get_db)):
    return db.query(ReglaComision).all()