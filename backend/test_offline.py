"""Operación offline (339), sincronización (340) y pantalla de cliente (357)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import random
import uuid

from fastapi.testclient import TestClient

from app.main import app

C = TestClient(app)
ok = 0
fail = 0


def check(nombre, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ok {nombre}")
    else:
        fail += 1
        print(f"  FALLO {nombre} :: {extra}")


r = C.post("/auth/login", json={"username": "admin", "password": "admin123"})
H = {"Authorization": "Bearer " + r.json()["access_token"]}
print("== Offline, sincronización y pantalla de cliente ==")

# Limpia cola de pendientes de corridas previas (evita veneno por re-intentos)
from app.database import SessionLocal
from app.models import PendienteSincronizacion

with SessionLocal() as db:
    db.query(PendienteSincronizacion).delete()
    db.commit()

# Producto propio y con stock para que la sincronización sea determinista
r = C.post("/productos", headers=H, json={
    "empresa_id": 1, "nombre": f"Off {random.randint(1000, 9999)}",
    "sku": f"OFF{random.randint(10000, 99999)}",
    "precio_venta": 12000, "precio_compra": 5000, "costo": 5000,
})
assert r.status_code == 201, r.text
pid_prod = r.json()["id"]
r = C.post("/compras", headers=H, json={
    "empresa_id": 1, "sucursal_id": 1, "proveedor_id": 1, "tipo": "contado",
    "detalle": [{"producto_id": pid_prod, "cantidad": 30, "costo_unitario": 5000}],
})
assert r.status_code == 201, r.text

# ---------- 339/340 Catálogo offline ----------
r = C.get("/offline/catalogo", headers=H)
check("Catálogo offline 200", r.status_code == 200, r.text[:200])
cat = r.json()
check("Catálogo trae productos con precios", len(cat["productos"]) > 0 and "precio_venta" in cat["productos"][0], r.text[:200])
check("Catálogo trae existencias", "existencias" in cat["productos"][0], r.text[:200])
check("Catálogo trae clientes", len(cat["clientes"]) > 0, r.text[:200])
check("Catálogo requiere token", C.get("/offline/catalogo").status_code == 401)

prod = next(p for p in cat["productos"] if p["id"] == pid_prod)
cli = cat["clientes"][0]
precio = float(prod["precio_venta"])

# ---------- 339 Cola de operaciones offline ----------
cid = str(uuid.uuid4())
payload = {
    "empresa_id": 1, "sucursal_id": 1, "tipo": "contado",
    "cliente_id": cli["id"], "caja_id": 1,
    "descuento_global": 0, "propina": 0, "nota": "venta offline demo",
    "detalle": [{"producto_id": prod["id"], "cantidad": 2, "precio": precio}],
    "pagos": [{"medio": "efectivo", "monto": precio * 2}],
}
r = C.post("/offline/pendientes", headers=H, json={"cliente_uuid": cid, "tipo": "venta", "payload": payload})
check("Encolar venta offline 201", r.status_code == 201 and r.json()["ya_existia"] is False, r.text[:200])
pid = r.json()["id"]

r = C.post("/offline/pendientes", headers=H, json={"cliente_uuid": cid, "tipo": "venta", "payload": payload})
check("Re-encolar mismo cliente_uuid no duplica (ya_existia)", r.status_code == 201 and r.json()["ya_existia"] is True, r.text[:200])

r = C.get("/offline/pendientes", headers=H)
check("Cola lista la operación pendiente", r.status_code == 200 and any(p["id"] == pid and p["estado"] == "pendiente" for p in r.json()), r.text[:200])

# ---------- 340 Sincronización ----------
r = C.post("/offline/sincronizar", headers=H)
check("Sincronizar todo 200", r.status_code == 200, r.text[:300])
res = r.json()
check("Una operación sincronizada", res["procesadas"] == 1 and res["errores"] == 0, res)
venta_off = res["sincronizadas"][0]["resultado"]
check("Venta offline creada con número V-", str(venta_off.get("numero", "")).startswith("V-"), venta_off)
check("Total coincidente", abs(float(venta_off["total"]) - precio * 2) < 0.01, venta_off)

r = C.get("/offline/pendientes", headers=H)
p_final = next(p for p in r.json() if p["id"] == pid)
check("Pendiente marcado sincronizada", p_final["estado"] == "sincronizada", p_final)
check("Pendiente quedó enlazado a la venta", p_final["resultado_id"] == venta_off["id"], p_final)

# Idempotencia: sincronizar de nuevo no crea otra venta
r = C.post("/offline/pendientes", headers=H, json={"cliente_uuid": cid, "tipo": "venta", "payload": payload})
check("Re-encolar tras sincronizar -> ya_existia", r.json()["ya_existia"] is True, r.json())
r = C.post("/offline/sincronizar", headers=H)
check("Segunda sincronización sin nuevas ventas", r.json()["procesadas"] == 0, r.json())

# Operación con error (producto inexistente) -> estado error
cid2 = str(uuid.uuid4())
r = C.post(
    "/offline/pendientes", headers=H,
    json={"cliente_uuid": cid2, "tipo": "venta", "payload": {
        "empresa_id": 1, "sucursal_id": 1, "tipo": "contado",
        "cliente_id": cli["id"],
        "detalle": [{"producto_id": 999999, "cantidad": 1}],
        "pagos": [{"medio": "efectivo", "monto": 10000}],
    }},
)
pid2 = r.json()["id"]
r = C.post("/offline/sincronizar", headers=H)
check("Operación inválida marcada en error", r.json()["errores"] == 1, r.json())
r = C.get("/offline/pendientes?estado=error", headers=H)
check("Cola muestra la operación en error", r.status_code == 200 and any(q["id"] == pid2 for q in r.json()), r.text[:200])

# ---------- 340 Novedades ----------
r = C.get("/offline/novedades?desde=2020-01-01T00:00:00", headers=H)
check("Novedades 200", r.status_code == 200, r.text[:200])
nov = r.json()
check("Novedades incluyen la venta sincronizada", any(v["id"] == venta_off["id"] for v in nov["ventas_nuevas"]), r.text[:300])
r = C.get("/offline/novedades?desde=2099-01-01T00:00:00", headers=H)
check("Novedades futuras vacías", len(r.json()["ventas_nuevas"]) == 0, r.text[:200])
check("Novedades con fecha inválida -> 400", C.get("/offline/novedades?desde=zzz", headers=H).status_code == 400)

# ---------- 357 Pantalla de cliente ----------
r = C.post(
    "/pantalla", headers=H,
    json={"items": [{"nombre": prod["nombre"], "cantidad": 2, "subtotal": precio * 2}], "subtotal": precio * 2, "descuento": 0, "impuesto": 0, "propina": 0, "total": precio * 2, "mensaje": "Aguarde su ticket"},
)
check("Push pantalla 200", r.status_code == 200, r.text[:200])

r = C.get("/pantalla")
check("Lectura pública pantalla 200", r.status_code == 200, r.text[:200])
pant = r.json()
check("Pantalla muestra total", abs(float(pant["total"]) - precio * 2) < 0.01, pant)
check("Pantalla muestra ítem", pant["items"][0]["nombre"] == prod["nombre"], pant)
check("Pantalla muestra mensaje", pant["mensaje"] == "Aguarde su ticket", pant)
check("Push pantalla requiere token", C.post("/pantalla", json={"total": 1}).status_code == 401)

r = C.get("/pantalla/vista")
check("Vista pantalla de cliente 200", r.status_code == 200 and "Pantalla de cliente" in r.text, r.text[:80])

print(f"\nOffline/sincronización/pantalla: {ok} OK · {fail} FAIL")
sys.exit(1 if fail else 0)