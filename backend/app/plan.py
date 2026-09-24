import datetime
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

# ---------- Catálogo de planes de suscripción ----------

_SIN_REST = set(MODULOS_TODOS) - _SIN_RESTAURANT - {"apartados", "fidelizacion"}
POR_PLAN = {
    "esencial": ["dashboard", "pos", "productos", "inventario", "ventas", "caja", "clientes", "reportes", "configuracion", "seguridad"],
    "avanzado": [m for m in MODULOS_TODOS if m in _SIN_REST] + ["compras", "proveedores", "cartera", "promociones", "facturacion", "vendedores"],
    "completo": MODULOS_TODOS,
    "gastronomia": MODULOS_TODOS,
}

PLANES = {
    "esencial": {
        "nombre": "Esencial",
        "precio_mensual": 49000,
        "limite_usuarios": 1,
        "modulos": POR_PLAN["esencial"],
        "descripcion": "Para negocios pequeños que venden en mostrador: ventas, inventario y caja.",
    },
    "avanzado": {
        "nombre": "Avanzado",
        "precio_mensual": 89000,
        "limite_usuarios": 3,
        "modulos": POR_PLAN["avanzado"],
        "descripcion": "Agrega compras, proveedores, cartera, promociones y facturación electrónica.",
    },
    "completo": {
        "nombre": "Completo",
        "precio_mensual": 129000,
        "limite_usuarios": None,
        "modulos": POR_PLAN["completo"],
        "descripcion": "Todos los módulos, usuarios ilimitados y soporte prioritario.",
    },
    "gastronomia": {
        "nombre": "Gastronomía",
        "precio_mensual": 159000,
        "limite_usuarios": None,
        "modulos": POR_PLAN["gastronomia"],
        "descripcion": "Mesas, comandas, domicilios, apartados y fidelización para restaurantes.",
    },
}


def catalogo_planes() -> list[dict]:
    return [
        {
            "clave": clave,
            **plan,
            "modulos": plan["modulos"],
        }
        for clave, plan in PLANES.items()
    ]


def leer_suscripcion(db: Session) -> dict:
    """Suscripción estructurada del negocio (plan, vence, estado)."""
    conf = db.query(Configuracion).filter(Configuracion.clave == "suscripcion").first()
    sus = {}
    if conf and conf.valor:
        try:
            sus = json.loads(conf.valor)
        except ValueError:
            sus = {}
    sus.setdefault("plan", "")
    sus.setdefault("vence", "")
    return sus


def sugerir_plan(habilitados: set[str]) -> str:
    """Elige el plan más pequeño cuyo catálogo cubra los módulos habilitados."""
    habilitados = set(habilitados)
    for clave in ("esencial", "avanzado", "completo", "gastronomia"):
        if habilitados.issubset(set(POR_PLAN[clave])):
            return clave
    mejor = "completo"
    mejor_score = -1
    for clave, mods in POR_PLAN.items():
        score = len(set(mods) & habilitados)
        if score > mejor_score:
            mejor, mejor_score = clave, score
    return mejor


def estado_suscripcion(db: Session) -> dict:
    sus = leer_suscripcion(db)
    plan = sus.get("plan", "")
    vence = sus.get("vence", "")
    hoy = datetime.date.today()
    if vence:
        try:
            fecha = __import__("datetime").date.fromisoformat(vence)
            vencida = fecha < hoy
            dias = (fecha - hoy).days
        except ValueError:
            vencida = False
            dias = None
    else:
        vencida = False
        dias = None
    estado = "vencida" if vencida else ("activa" if plan else "prueba")
    datos_plan = PLANES.get(plan) if plan else None
    return {
        "plan": plan,
        "plan_nombre": datos_plan["nombre"] if datos_plan else ("Prueba" if not plan else plan),
        "vence": vence,
        "dias_restantes": dias,
        "estado": estado,
        "planes": catalogo_planes(),
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
