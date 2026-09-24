"""Backups automáticos programados.

Reutiliza el volcado JSON de tablas núcleo de la API (POST /backups) y lo
extiende: también escribe el respaldo a disco en el volumen persistente
`/app/datos/backups/` y aplica retención (conserva solo los N más recientes).
Configuración (claves de Configuracion):
- pos.backup_automatico : bool  (activa/desactiva el respaldo diario)
- pos.hora_backup        : "HH:MM"  (hora local del respaldo, por defecto 03:00)
- pos.retener_backups    : int   (número de respaldos automáticos a conservar)
"""
import json
import os
import threading
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import text

from .database import engine, get_session
from .models import BackupRegistro
from .wa import config_bool, guardar_config, obtener_config

_TABLAS_BACKUP = [
    "empresas", "sucursales", "puntos_venta", "cajas", "bodegas", "ubicaciones",
    "productos", "clientes", "proveedores", "ventas", "venta_detalle", "venta_pago",
    "categorias", "marcas", "presentaciones", "compras", "cuentas_pagar", "stock",
]

_DIR_DISCO = Path(os.environ.get("BACKUPS_DIR", "/app/datos/backups"))

_hilo = None


def volcar_tablas() -> tuple[list[dict], int]:
    """Vuelca las tablas núcleo a JSON (mismo criterio que la API)."""
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
    return totales, conteo


def ejecutar_backup(db, tipo: str = "manual", guardar_disco: bool = True) -> dict:
    """Genera un respaldo completo y lo registra en la BD (y en disco)."""
    totales, conteo = volcar_tablas()
    detalle = json.dumps(totales, default=str, ensure_ascii=False)
    nombre = f"backup-{date.today().isoformat()}-{tipo}"
    tamano = len(detalle.encode("utf-8"))

    b = BackupRegistro(
        nombre=nombre,
        tabla=f"backup completo ({len(_TABLAS_BACKUP)} tablas)",
        tipo=tipo,
        tamano=tamano,
        detalle=detalle,
    )
    db.add(b)
    db.commit()
    db.refresh(b)

    ruta_disco = ""
    if guardar_disco:
        try:
            _DIR_DISCO.mkdir(parents=True, exist_ok=True)
            destino = _DIR_DISCO / f"backup-{b.id:04d}-{date.today().isoformat()}.json"
            temporal = destino.with_suffix(".tmp")
            temporal.write_text(detalle, encoding="utf-8")
            temporal.replace(destino)
            ruta_disco = str(destino)
            b.detalle = detalle  # ya registrado; el archivo es copia de seguridad
            db.commit()
        except Exception:
            ruta_disco = ""

    return {"id": b.id, "nombre": b.nombre, "tablas": len(_TABLAS_BACKUP), "registros": conteo, "tamano": b.tamano, "archivo": ruta_disco}


def aplicar_retencion(db, mantener: int) -> int:
    """Elimina respaldos automáticos viejos conservando los `mantener` más recientes."""
    if mantener <= 0:
        return 0
    viejos = (
        db.query(BackupRegistro)
        .filter(BackupRegistro.tipo == "automatico")
        .order_by(BackupRegistro.id.desc())
        .offset(mantener)
        .all()
    )
    for v in viejos:
        db.delete(v)
    db.commit()
    return len(viejos)


def _tick():
    import time as _time

    db = get_session()
    try:
        ahora = datetime.now()
        if not config_bool(db, "pos.backup_automatico", True):
            return
        hora = obtener_config(db, "pos.hora_backup", "03:00").strip()[:5]
        if ahora.strftime("%H:%M") != hora:
            return
        ultimo = obtener_config(db, "pos.ultimo_backup", "")
        if ultimo == str(date.today()):
            return
        ejecutar_backup(db, tipo="automatico")
        retener = int(obtener_config(db, "pos.retener_backups", "14") or "14")
        aplicar_retencion(db, retener)
        guardar_config(db, "pos.ultimo_backup", str(date.today()))
    except Exception:
        pass
    finally:
        db.close()


def _loop():
    import time as _time

    _time.sleep(5)
    while True:
        try:
            _tick()
        except Exception:
            pass
        _time.sleep(60)


def iniciar_scheduler():
    global _hilo
    if _hilo and _hilo.is_alive():
        return
    _hilo = threading.Thread(target=_loop, daemon=True, name="backup-scheduler")
    _hilo.start()