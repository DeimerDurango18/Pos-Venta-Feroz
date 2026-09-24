from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Configuracion, Empresa, Establecimiento, Impuesto, ModeloNegocio, Usuario
from ..plan import (
    PLANES,
    TIPOS_NEGOCIO,
    calcular_modulos,
    catalogo_planes,
    estado_suscripcion,
    guardar_licencia,
    leer_licencia,
    leer_suscripcion,
    modelo_negocio_de_empresa,
    sugerir_plan,
)
from ..schemas.configuracion import (
    ConfiguracionCreate,
    ConfiguracionOut,
    ImpuestoCreate,
    ImpuestoOut,
)
from ..schemas.establecimiento import EstablecimientoOut, EstablecimientoUpdate

router = APIRouter(prefix="/configuracion", tags=["configuracion"])


# ---------- Configuración general (clave/valor) ----------
@router.get("/general", response_model=list[ConfiguracionOut])
def listar_config(db: Session = Depends(get_db)):
    return db.query(Configuracion).all()


@router.put("/general/{clave}", response_model=ConfiguracionOut)
def guardar_config(
    clave: str,
    valor: str,
    descripcion: str | None = None,
    db: Session = Depends(get_db),
):
    conf = db.query(Configuracion).filter(Configuracion.clave == clave).first()
    if conf:
        conf.valor = valor
        if descripcion:
            conf.descripcion = descripcion
    else:
        conf = Configuracion(clave=clave, valor=valor, descripcion=descripcion)
        db.add(conf)
    db.commit()
    db.refresh(conf)
    return conf


# ---------- Dispositivos y formato POS ----------
import json as _json

_DEFAULTS = {
    "pos.factura": {"ancho_mm": 72, "copias": 1, "leyenda_pie": ""},
    "pos.impresoras": [{"nombre": "Impresora térmica 80mm", "puerto": "USB", "papel_mm": 80}],
    "pos.lector": {"habilitado": True, "marca": "Genérico", "sufijo": "Enter"},
    "pos.terminal": {"nombre": "Terminal 1", "serie": "", "habilitado": True},
    "pos.cajon": {"habilitado": False, "puerto": "Drawer (RJ12)"},
    "pos.correo": {"servidor": "smtp.gmail.com", "puerto": 587, "usuario": "", "desde": "", "tls": True},
}


def _leer_bloque(db: Session, clave: str):
    conf = db.query(Configuracion).filter(Configuracion.clave == clave).first()
    if not conf:
        return _json.loads(_json.dumps(_DEFAULTS[clave]))
    try:
        return _json.loads(conf.valor or "")
    except ValueError:
        return _json.loads(_json.dumps(_DEFAULTS[clave]))


def _guardar_bloque(db: Session, clave: str, valor):
    conf = db.query(Configuracion).filter(Configuracion.clave == clave).first()
    texto = _json.dumps(valor, ensure_ascii=False)
    if conf:
        conf.valor = texto
    else:
        conf = Configuracion(clave=clave, valor=texto, descripcion="Dispositivos POS")
        db.add(conf)
    db.commit()
    db.refresh(conf)
    return conf


class FacturaFormato(BaseModel):
    ancho_mm: int = 72
    copias: int = 1
    leyenda_pie: str = ""


class ImpresoraItem(BaseModel):
    nombre: str = ""
    puerto: str = "USB"
    papel_mm: int = 80


class LectorConfig(BaseModel):
    habilitado: bool = True
    marca: str = ""
    sufijo: str = "Enter"


class TerminalConfig(BaseModel):
    nombre: str = ""
    serie: str = ""
    habilitado: bool = True


class CajonConfig(BaseModel):
    habilitado: bool = False
    puerto: str = ""


class CorreoConfig(BaseModel):
    servidor: str = ""
    puerto: int = 587
    usuario: str = ""
    password: str = ""
    desde: str = ""
    url_publica: str = ""
    tls: bool = True


def _leer_correo(db):
    """Devuelve el bloque correo sin exponer la contraseña."""
    cfg = _leer_bloque(db, "pos.correo") or {}
    cfg["password"] = ""
    return cfg


@router.get("/dispositivos")
def obtener_dispositivos(db: Session = Depends(get_db)):
    return {
        "factura": _leer_bloque(db, "pos.factura"),
        "impresoras": _leer_bloque(db, "pos.impresoras"),
        "lector": _leer_bloque(db, "pos.lector"),
        "terminal": _leer_bloque(db, "pos.terminal"),
        "cajon": _leer_bloque(db, "pos.cajon"),
        "correo": _leer_correo(db),
    }


@router.put("/dispositivos/factura")
def guardar_factura(data: FacturaFormato, db: Session = Depends(get_db)):
    _guardar_bloque(db, "pos.factura", data.model_dump())
    return _leer_bloque(db, "pos.factura")


@router.put("/dispositivos/impresoras")
def guardar_impresoras(data: list[ImpresoraItem], db: Session = Depends(get_db)):
    _guardar_bloque(db, "pos.impresoras", [i.model_dump() for i in data])
    return _leer_bloque(db, "pos.impresoras")


@router.put("/dispositivos/lector")
def guardar_lector(data: LectorConfig, db: Session = Depends(get_db)):
    _guardar_bloque(db, "pos.lector", data.model_dump())
    return _leer_bloque(db, "pos.lector")


@router.put("/dispositivos/terminal")
def guardar_terminal(data: TerminalConfig, db: Session = Depends(get_db)):
    _guardar_bloque(db, "pos.terminal", data.model_dump())
    return _leer_bloque(db, "pos.terminal")


@router.put("/dispositivos/cajon")
def guardar_cajon(data: CajonConfig, db: Session = Depends(get_db)):
    _guardar_bloque(db, "pos.cajon", data.model_dump())
    return _leer_bloque(db, "pos.cajon")


@router.put("/dispositivos/correo")
def guardar_correo(data: CorreoConfig, db: Session = Depends(get_db)):
    datos = data.model_dump()
    actual = _leer_bloque(db, "pos.correo") or {}
    if not datos.get("password"):
        datos["password"] = actual.get("password", "")
    _guardar_bloque(db, "pos.correo", datos)
    return _leer_correo(db)


# ---------- Establecimiento / negocio por NIT ----------
@router.get("/establecimiento", response_model=EstablecimientoOut)
def obtener_establecimiento(
    nit: str,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nit = nit.strip()
    if not nit:
        raise HTTPException(400, "Debes indicar un NIT")
    est = db.query(Establecimiento).filter(Establecimiento.nit == nit).first()
    if est:
        return est
    emp = db.query(Empresa).filter(Empresa.nit == nit).first()
    if emp:
        return EstablecimientoOut(
            id=0,
            nit=emp.nit,
            nombre=emp.nombre or "",
            razon_social=emp.razon_social or "",
            tipo_negocio=emp.tipo_negocio or "general",
            regimen=emp.regimen or "",
            direccion=emp.direccion or "",
            telefono=emp.telefono or "",
            email=emp.email or "",
            activo=emp.activa,
        )
    return EstablecimientoOut(id=0, nit=nit, nombre="", tipo_negocio="general", activo=True)


@router.put("/establecimiento", response_model=EstablecimientoOut)
def guardar_establecimiento(
    data: EstablecimientoUpdate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nit = data.nit.strip()
    if not nit:
        raise HTTPException(400, "Debes indicar un NIT")
    est = db.query(Establecimiento).filter(Establecimiento.nit == nit).first()
    if not est:
        est = Establecimiento(nit=nit)
        db.add(est)
    campos = data.model_dump(exclude={"nit"})
    for k, v in campos.items():
        if v == "":
            v = None
        setattr(est, k, v)
    if est.modelo_negocio_id is not None and not db.get(ModeloNegocio, est.modelo_negocio_id):
        raise HTTPException(400, "Ese modelo de negocio no existe")
    emp = db.query(Empresa).filter(Empresa.nit == nit).first()
    if emp:
        est.empresa_id = emp.id
    db.commit()
    db.refresh(est)
    return est


# ---------- Modelos de negocio (solo administrador) ----------
@router.get("/modelo-negocio")
def listar_modelos_negocio(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not (usuario.es_admin or (usuario.rol and usuario.rol.nombre.lower() == "admin")):
        raise HTTPException(403, "Solo un administrador puede ver los modelos de negocio")
    return [
        {
            "id": m.id,
            "nombre": m.nombre,
            "descripcion": m.descripcion,
            "modulos": _json.loads(m.modulos or "[]"),
            "activo": m.activo,
        }
        for m in db.query(ModeloNegocio).order_by(ModeloNegocio.id).all()
    ]


# ---------- Plan / Licencia por NIT ----------
@router.get("/plan")
def obtener_plan(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    empresa = db.get(Empresa, usuario.empresa_id)
    if not empresa:
        empresa = db.query(Empresa).first()
    if not empresa:
        raise HTTPException(404, "No hay empresas configuradas")
    lic = leer_licencia(db)
    modelo = modelo_negocio_de_empresa(empresa, db)
    habilitados = set(calcular_modulos(empresa, db))
    sus = estado_suscripcion(db)
    return {
        "nit": empresa.nit,
        "tipo_negocio": empresa.tipo_negocio or "general",
        "tipos_disponibles": TIPOS_NEGOCIO,
        "modulos": sorted(habilitados),
        "modelo": modelo.id if modelo else None,
        "cliente": lic.get("cliente", ""),
        "vence": lic.get("vence", ""),
        "modulos_extra": lic.get("modulos_extra", []),
        "modulos_ocultos": lic.get("modulos_ocultos", []),
        "suscripcion": sus,
        "plan_sugerido": sugerir_plan(habilitados),
        "planes": catalogo_planes(),
    }


class SuscripcionUpdate(BaseModel):
    plan: str
    vence: str | None = None


@router.put("/plan")
def actualizar_suscripcion(
    data: SuscripcionUpdate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not (usuario.es_admin or (usuario.rol and usuario.rol.nombre.lower() == "admin")):
        raise HTTPException(403, "Solo un administrador puede cambiar el plan")
    if data.plan not in PLANES:
        raise HTTPException(400, f"Plan desconocido: {data.plan}")
    sus = leer_suscripcion(db)
    sus["plan"] = data.plan
    if data.vence:
        sus["vence"] = data.vence
    conf = db.query(Configuracion).filter(Configuracion.clave == "suscripcion").first()
    texto = _json.dumps(sus, ensure_ascii=False)
    if conf:
        conf.valor = texto
    else:
        conf = Configuracion(clave="suscripcion", valor=texto, descripcion="Plan de suscripción del negocio")
        db.add(conf)
    db.commit()
    db.refresh(conf)
    return estado_suscripcion(db)


# ---------- Conexión a la base de datos (solo administrador) ----------
@router.get("/conexion")
def info_conexion(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not (usuario.es_admin or (usuario.rol and usuario.rol.nombre.lower() == "admin")):
        raise HTTPException(403, "Solo un administrador puede ver la conexión a la base de datos")
    from sqlalchemy import text as _text
    from sqlalchemy.engine import make_url

    from .. import direccionamiento as _dirmod

    url = make_url(db.bind.url)
    razon = "ok"
    error = ""
    try:
        db.execute(_text("SELECT 1"))
    except Exception as e:
        razon = "error"
        error = str(e)[:160]
    return {
        "razon": razon,
        "error": error,
        "dialecto": (db.bind.dialect.name or "desconocido"),
        "host": url.host,
        "puerto": url.port or 0,
        "base": url.database,
        "origen": "archivo" if _dirmod.leer() else "entorno",
    }


class ConexionUpdate(BaseModel):
    dialecto: str = "mssql"
    host: str
    puerto: int = 1433
    base: str = "posdb"
    usuario: str = ""
    password: str = ""
    driver: str = "ODBC Driver 18 for SQL Server"


@router.put("/conexion")
def actualizar_conexion(
    data: ConexionUpdate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not (usuario.es_admin or (usuario.rol and usuario.rol.nombre.lower() == "admin")):
        raise HTTPException(403, "Solo un administrador puede cambiar la conexión a la base de datos")
    from .. import direccionamiento as _dirmod
    from ..database import reconectar

    datos = data.model_dump()
    if not datos.get("usuario"):
        datos["usuario"] = _dirmod.usuario_guardado(datos)
    if not datos.get("password"):
        datos["password"] = _dirmod.password_guardado_o_heredado(datos)
    try:
        url = _dirmod.url_desde_dato(datos)
    except Exception as e:
        raise HTTPException(400, f"Datos de conexión inválidos: {e}")
    try:
        resultado = reconectar(url)
    except Exception as e:
        raise HTTPException(400, f"No se pudo conectar al nuevo destino: {str(e)[:200]}")
    _dirmod.guardar(datos)
    resultado["origen"] = "archivo"
    return resultado


class LicenciaUpdate(BaseModel):
    cliente: str | None = None
    vence: str | None = None
    modulos_extra: list[str] | None = None
    modulos_ocultos: list[str] | None = None


@router.put("/licencia")
def actualizar_licencia(
    data: LicenciaUpdate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not (usuario.es_admin or (usuario.rol and usuario.rol.nombre.lower() == "admin")):
        raise HTTPException(403, "Solo un administrador puede modificar la licencia")
    lic = leer_licencia(db)
    for k, v in data.model_dump(exclude_unset=True).items():
        lic[k] = v
    guardar_licencia(db, lic)
    empresa = db.get(Empresa, usuario.empresa_id) or db.query(Empresa).first()
    return {
        "nit": empresa.nit,
        "tipo_negocio": empresa.tipo_negocio or "general",
        "modulos": calcular_modulos(empresa, db),
        "cliente": lic.get("cliente", ""),
        "vence": lic.get("vence", ""),
        "modulos_extra": lic.get("modulos_extra", []),
        "modulos_ocultos": lic.get("modulos_ocultos", []),
    }


# ---------- Impuestos ----------
@router.get("/impuestos", response_model=list[ImpuestoOut])
def listar_impuestos(db: Session = Depends(get_db)):
    return db.query(Impuesto).all()


@router.post("/impuestos", response_model=ImpuestoOut, status_code=201)
def crear_impuesto(data: ImpuestoCreate, db: Session = Depends(get_db)):
    imp = Impuesto(nombre=data.nombre, tasa=data.tasa)
    db.add(imp)
    db.commit()
    db.refresh(imp)
    return imp


@router.put("/impuestos/{impuesto_id}", response_model=ImpuestoOut)
def actualizar_impuesto(
    impuesto_id: int,
    data: ImpuestoCreate,
    db: Session = Depends(get_db),
):
    imp = db.get(Impuesto, impuesto_id)
    if not imp:
        raise HTTPException(404, "Impuesto no encontrado")
    imp.nombre = data.nombre
    imp.tasa = data.tasa
    db.commit()
    db.refresh(imp)
    return imp


# ---------- QR de pago Nequi / Daviplata ----------
@router.get("/qr-pago/{tipo}")
def qr_pago_config(
    tipo: str,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """PNG (o URL) del QR de pago configurado en `pagos.qr_{tipo}`.

    Mismo generador del kiosko (/publico/qr-pago/...), pero reservado
    para operadores autenticados (punto de venta).
    """
    from fastapi.responses import RedirectResponse, Response

    from .publico import montar_qr_pago

    mime, datos = montar_qr_pago(db, tipo)
    if mime == "text/url":
        return RedirectResponse(datos)
    return Response(content=datos, media_type=mime)