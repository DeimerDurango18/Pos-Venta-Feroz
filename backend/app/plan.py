import json
from sqlalchemy.orm import Session

from .models import Configuracion, Empresa, Establecimiento, ModeloNegocio

TIPOS_NEGOCIO = ["general", "ferreteria", "restaurante", "minimarket"]

MODULOS_TODOS = [
    "dashboard",
    "pos",
    "productos",
    "inventario",
    "compras",
    "ventas",
    "caja",
    "clientes",
    "proveedores",
    "cartera",
    "promociones",
    "facturacion",
    "fidelizacion",
    "apartados",
    "domicilios",
    "restaurante",
    "seguridad",
    "vendedores",
    "sistema",
    "reportes",
    "integraciones",
    "offline",
    "configuracion",
]

_TODOS = set(MODULOS_TODOS)
_SIN_RESTAURANT = {"restaurante", "domicilios"}

MODULOS_POR_TIPO = {
    "general": _TODOS,
    "ferreteria": _TODOS - _SIN_RESTAURANT - {"apartados", "fidelizacion"},
    "minimarket": _TODOS - _SIN_RESTAURANT - {"apartados"},
    # Un restaurante puede requerir factura electrónica igual que cualquier
    # otro negocio; el módulo no debe quedar excluido por defecto.
    "restaurante": _TODOS - {"apartados"},
}

# Prefijos de API -> módulo (para el guard de middleware)
RUTA_MODULO = {
    "/ventas": "ventas",
    "/pos": "pos",
    "/productos": "productos",
    "/inventario": "inventario",
    "/compras": "compras",
    "/proveedores": "proveedores",
    "/clientes": "clientes",
    "/cartera": "cartera",
    "/promociones": "promociones",
    "/facturacion": "facturacion",
    "/fidelizacion": "fidelizacion",
    "/apartados": "apartados",
    "/pedidos": "domicilios",
    "/domicilios": "domicilios",
    "/restaurante": "restaurante",
    "/vendedores": "vendedores",
    "/integraciones": "integraciones",
    "/offline": "offline",
    "/reportes": "reportes",
    "/caja": "caja",
}

LICENCIA_VACIA = {
    "cliente": "",
    "vence": "",
    "modulos_extra": [],
    "modulos_ocultos": [],
}


def leer_licencia(db: Session) -> dict:
    conf = db.query(Configuracion).filter(Configuracion.clave == "licencia").first()
    if not conf or not conf.valor:
        return dict(LICENCIA_VACIA)
    try:
        lic = json.loads(conf.valor)
    except ValueError:
        return dict(LICENCIA_VACIA)
    for k, v in LICENCIA_VACIA.items():
        lic.setdefault(k, v)
    return lic


def guardar_licencia(db: Session, lic: dict) -> dict:
    conf = db.query(Configuracion).filter(Configuracion.clave == "licencia").first()
    texto = json.dumps(lic, ensure_ascii=False)
    if conf:
        conf.valor = texto
    else:
        conf = Configuracion(clave="licencia", valor=texto, descripcion="Plan y licencia del negocio")
        db.add(conf)
    db.commit()
    db.refresh(conf)
    return lic


def modelo_negocio_de_empresa(empresa: Empresa, db: Session) -> ModeloNegocio | None:
    """Devuelve el modelo de negocio asociado al NIT de la empresa (vía establecimientos)."""
    if not empresa:
        return None
    est = db.query(Establecimiento).filter(Establecimiento.nit == empresa.nit).first()
    if not est or not est.modelo_negocio_id:
        return None
    return db.get(ModeloNegocio, est.modelo_negocio_id)


def _modulos_de_modelo(modelo: ModeloNegocio | None, base) -> set[str]:
    """Los módulos que habilita el modelo de negocio (JSON en la columna modulos)."""
    if not modelo or not modelo.modulos:
        return set(base)
    try:
        lista = json.loads(modelo.modulos)
        habilitados = {str(m) for m in lista if m}
    except (ValueError, TypeError):
        return set(base)
    return habilitados


def calcular_modulos(empresa: Empresa, db: Session) -> list[str]:
    lic = leer_licencia(db)
    tipo = empresa.tipo_negocio or "general"
    base = MODULOS_POR_TIPO.get(tipo, MODULOS_POR_TIPO["general"])
    modelo = modelo_negocio_de_empresa(empresa, db)
    habilitados = _modulos_de_modelo(modelo, base)
    habilitados |= set(lic.get("modulos_extra", []))
    habilitados -= set(lic.get("modulos_ocultos", []))
    return sorted(habilitados)
