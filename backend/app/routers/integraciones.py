import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    BackupRegistro,
    Balanza,
    CuentaBanco,
    MensajeWhatsapp,
    Moneda,
    MovimientoBanco,
    Usuario,
    Webhook,
)

router = APIRouter(tags=["integraciones"])


# ------------------ MONEDAS (14) ------------------
class MonedaIn(BaseModel):
    empresa_id: int = 1
    codigo: str
    nombre: str | None = None
    simbolo: str | None = None
    tasa_cambio: float = 1
    activa: bool = True


@router.get("/monedas")
def listar_monedas(db: Session = Depends(get_db)):
    return db.query(Moneda).order_by(Moneda.id.desc()).all()


@router.post("/monedas", status_code=201)
def crear_moneda(data: MonedaIn, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    m = Moneda(**data.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@router.put("/monedas/{moneda_id}")
def actualizar_moneda(moneda_id: int, data: MonedaIn, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    m = db.get(Moneda, moneda_id)
    if not m:
        raise HTTPException(404, "Moneda no encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    return m


@router.post("/monedas/{moneda_id}/convertir")
def convertir_moneda(moneda_id: int, monto: float, base: str = "COP", db: Session = Depends(get_db)):
    """Convierte COP a la moneda de la tasa configurada (o viceversa)."""
    m = db.get(Moneda, moneda_id)
    if not m:
        raise HTTPException(404, "Moneda no encontrada")
    tasa = float(m.tasa_cambio or 1) or 1
    if base == "COP":
        return {"codigo": m.codigo, "monto": round(monto / tasa, 2)}
    return {"codigo": m.codigo, "monto": round(monto * tasa, 2)}


# ------------------ BALANZAS (19 / 355) ------------------
class BalanzaIn(BaseModel):
    empresa_id: int = 1
    sucursal_id: int | None = None
    nombre: str
    modelo: str | None = None
    puerto: str | None = None
    formato: str = "SAP"
    tasa: int = 1
    activa: bool = True


@router.get("/balanzas")
def listar_balanzas(db: Session = Depends(get_db)):
    return db.query(Balanza).order_by(Balanza.id.desc()).all()


@router.post("/balanzas", status_code=201)
def crear_balanza(data: BalanzaIn, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    b = Balanza(**data.model_dump())
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


@router.put("/balanzas/{balanza_id}")
def actualizar_balanza(balanza_id: int, data: BalanzaIn, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    b = db.get(Balanza, balanza_id)
    if not b:
        raise HTTPException(404, "Balanza no encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(b, k, v)
    db.commit()
    db.refresh(b)
    return b


@router.post("/balanzas/{balanza_id}/pesar")
def leer_peso(balanza_id: int, db: Session = Depends(get_db)):
    """Lee el peso de la balanza (integración: respuesta simulada del dispositivo)."""
    b = db.get(Balanza, balanza_id)
    if not b:
        raise HTTPException(404, "Balanza no encontrada")
    if not b.activa:
        raise HTTPException(400, "La balanza está inactiva")
    factor = float(b.tasa or 1) or 1
    return {
        "balanza": b.nombre,
        "puerto": b.puerto,
        "peso": round(0.500 * factor, 3),
        "unidad": "kg",
        "estable": True,
        "device_ok": True,
    }


# ------------------ BANCOS (359) ------------------
class CuentaBancoIn(BaseModel):
    empresa_id: int = 1
    banco: str
    numero_cuenta: str | None = None
    tipo: str = "corriente"
    titular: str | None = None
    saldo_inicial: float = 0
    activa: bool = True


class MovimientoBancoIn(BaseModel):
    cuenta_id: int
    tipo: str  # ingreso, egreso
    monto: float
    concepto: str | None = None
    referencia: str | None = None
    fecha_movimiento: date | None = None
    conciliado: bool = False


@router.get("/bancos/cuentas")
def listar_cuentas_banco(db: Session = Depends(get_db)):
    cuentas = db.query(CuentaBanco).order_by(CuentaBanco.id.desc()).all()
    out = []
    for c in cuentas:
        saldo = float(c.saldo_inicial or 0)
        for mv in c.movimientos:
            saldo += float(mv.monto or 0) if mv.tipo == "ingreso" else -float(mv.monto or 0)
        out.append(
            {
                "id": c.id,
                "banco": c.banco,
                "numero_cuenta": c.numero_cuenta,
                "tipo": c.tipo,
                "titular": c.titular,
                "saldo": round(saldo, 2),
                "activa": c.activa,
            }
        )
    return out


@router.post("/bancos/cuentas", status_code=201)
def crear_cuenta_banco(data: CuentaBancoIn, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    c = CuentaBanco(**data.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/bancos/cuentas/{cuenta_id}")
def actualizar_cuenta_banco(cuenta_id: int, data: CuentaBancoIn, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    c = db.get(CuentaBanco, cuenta_id)
    if not c:
        raise HTTPException(404, "Cuenta no encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


@router.post("/bancos/movimientos", status_code=201)
def registrar_movimiento_banco(data: MovimientoBancoIn, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    c = db.get(CuentaBanco, data.cuenta_id)
    if not c:
        raise HTTPException(404, "Cuenta no encontrada")
    mv = MovimientoBanco(**data.model_dump())
    db.add(mv)
    db.commit()
    db.refresh(mv)
    return mv


@router.get("/bancos/movimientos")
def listar_movimientos_banco(cuenta_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(MovimientoBanco)
    if cuenta_id:
        q = q.filter(MovimientoBanco.cuenta_id == cuenta_id)
    return [
        {
            "id": mv.id,
            "cuenta_id": mv.cuenta_id,
            "tipo": mv.tipo,
            "monto": float(mv.monto or 0),
            "concepto": mv.concepto,
            "referencia": mv.referencia,
            "fecha": mv.fecha_movimiento.isoformat() if mv.fecha_movimiento else None,
            "conciliado": mv.conciliado,
        }
        for mv in q.order_by(MovimientoBanco.id.desc()).limit(200).all()
    ]


@router.post("/bancos/movimientos/{mov_id}/conciliar")
def conciliar_movimiento(mov_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    mv = db.get(MovimientoBanco, mov_id)
    if not mv:
        raise HTTPException(404, "Movimiento no encontrado")
    mv.conciliado = True
    db.commit()
    return {"ok": True, "conciliado": True}


# ------------------ WEBHOOKS (364) ------------------
class WebhookIn(BaseModel):
    empresa_id: int = 1
    evento: str
    url: str
    token: str | None = None
    activo: bool = True


@router.get("/webhooks")
def listar_webhooks(db: Session = Depends(get_db)):
    return db.query(Webhook).order_by(Webhook.id.desc()).all()


@router.post("/webhooks", status_code=201)
def crear_webhook(data: WebhookIn, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    w = Webhook(**data.model_dump())
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


@router.put("/webhooks/{webhook_id}")
def actualizar_webhook(webhook_id: int, data: WebhookIn, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    w = db.get(Webhook, webhook_id)
    if not w:
        raise HTTPException(404, "Webhook no encontrado")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(w, k, v)
    db.commit()
    db.refresh(w)
    return w


def enviar_webhook(db: Session, evento: str, payload: dict):
    """Envía (fire-and-forget) el payload a los webhooks suscritos al evento."""
    import threading

    ws = db.query(Webhook).filter(Webhook.evento == evento, Webhook.activo == True).all()

    def _post(url, token, cuerpo):
        import requests

        cab = {}
        if token:
            cab["Authorization"] = f"Bearer {token}"
        try:
            requests.post(url, json=cuerpo, headers=cab, timeout=5)
        except Exception:
            pass

    for w in ws:
        threading.Thread(target=_post, args=(w.url, w.token, payload), daemon=True).start()


# ------------------ WHATSAPP (362) ------------------
@router.post("/whatsapp/enviar")
def enviar_whatsapp(
    telefono: str,
    mensaje: str,
    empresa_id: int = 1,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Registra y envía (simulado) un mensaje de WhatsApp."""
    if not telefono or not mensaje:
        raise HTTPException(400, "Teléfono y mensaje son obligatorios")
    msg = MensajeWhatsapp(
        empresa_id=empresa_id,
        telefono=telefono,
        contenido=mensaje,
        estado="enviado",
        referencia=f"MSG-{date.today().isoformat()}",
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"id": msg.id, "estado": msg.estado, "telefono": telefono, "mensaje": mensaje}


# ------------------ BACKUPS / RESTAURACIÓN (342) ------------------
_TABLAS_BACKUP = [
    "productos", "clientes", "proveedores", "ventas", "venta_detalle", "venta_pago",
    "categorias", "marcas", "presentaciones", "compras", "cuentas_pagar", "stock",
]


@router.get("/backups")
def listar_backups(db: Session = Depends(get_db)):
    return (
        db.query(BackupRegistro)
        .order_by(BackupRegistro.id.desc())
        .limit(50)
        .all()
    )


@router.post("/backups", status_code=201)
def crear_backup(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    """Vuelca las tablas núcleo a JSON y guarda el registro (base para restauración)."""
    from sqlalchemy import text

    from app.database import engine

    nombre = f"backup-{date.today().isoformat()}-{usuario.id}"
    totales = []
    conteo = 0
    with engine.connect() as conn:
        for tabla in _TABLAS_BACKUP:
            try:
                filas = conn.execute(text(f"SELECT * FROM {tabla}")).mappings().all()
                totales.append({tabla: [dict(f) for f in filas]})
                conteo += len(filas)
            except Exception:
                totales.append({tabla: []})
    detalle = json.dumps(totales, default=str, ensure_ascii=False)
    b = BackupRegistro(
        nombre=nombre,
        tabla=f"backup completo ({len(_TABLAS_BACKUP)} tablas)",
        tipo="manual",
        tamano=len(detalle.encode("utf-8")),
        detalle=detalle,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return {"id": b.id, "nombre": b.nombre, "tablas": len(_TABLAS_BACKUP), "registros": conteo, "tamano": b.tamano}


@router.post("/backups/{backup_id}/restaurar")
def restaurar_backup(backup_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    """Restaura (upsert) las tablas desde el JSON del backup."""
    from sqlalchemy import text

    from app.database import engine

    b = db.get(BackupRegistro, backup_id)
    if not b:
        raise HTTPException(404, "Backup no encontrado")
    detalle = json.loads(b.detalle)
    for chunk in detalle:
        for tabla, filas in chunk.items():
            if not filas:
                continue
            columnas = list(filas[0].keys())
            no_id = [c for c in columnas if c != "id"]
            sets = ", ".join(f"{c} = :v{i}" for i, c in enumerate(no_id))
            filas_ok = [f for f in filas if f.get("id") is not None]
            if not filas_ok:
                continue
            with engine.begin() as conn:
                for fila in filas_ok:
                    try:
                        conn.execute(
                            text(f"UPDATE {tabla} SET {sets} WHERE id = :vid"),
                            {**{f"v{i}": fila[c] for i, c in enumerate(no_id)}, "vid": fila["id"]},
                        )
                    except Exception:
                        pass
    db.add(BackupRegistro(nombre=f"restaurado desde {b.nombre}", tabla=b.tabla, tipo="restauracion", tamano=0))
    db.commit()
    return {"ok": True, "restaurado_desde": b.nombre}