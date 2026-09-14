"""Integración con métodos de pago por tarjeta (simulador interno, ítem 358)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import random

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
print("== Pagos con tarjeta (simulador) ==")

# --- Flujo autorizar/confirmar/reversar ---
r = C.post("/pagos/tarjeta/autorizar", headers=H, json={"monto": 45000, "marca": "Visa", "ultimos4": "4242"})
check("Autorizar tarjeta 200", r.status_code == 200, r.text[:200])
tx = r.json()
check("Estado aprobada", tx.get("estado") == "aprobada", tx)
check("Código autorización APR", str(tx.get("codigo_autorizacion", "")).startswith("APR"), tx)
check("Tarjeta enmascarada ####4242", tx.get("ultimos4") == "4242", tx)
check("Referencia de pasarela presente", bool(tx.get("referencia")), tx)

r = C.post(f"/pagos/tarjeta/{tx['id']}/confirmar", headers=H)
check("Confirmar (captura) OK", r.status_code == 200 and r.json()["estado"] == "confirmada", r.text[:200])

r = C.post(f"/pagos/tarjeta/{tx['id']}/reversar", headers=H)
check("Reversar transacción OK", r.status_code == 200 and r.json()["estado"] == "reversada", r.text[:200])

r = C.post(f"/pagos/tarjeta/{tx['id']}/confirmar", headers=H)
check("Confirmar sobre reversada -> 400", r.status_code == 400, r.text[:200])

# Rechazo
r = C.post("/pagos/tarjeta/autorizar", headers=H, json={"monto": 999999999})
check("Monto excesivo -> rechazada", r.status_code == 200 and r.json()["estado"] == "rechazada", r.text[:200])

r = C.post("/pagos/tarjeta/autorizar", headers=H, json={"monto": -5})
check("Monto negativo -> rechazada", r.status_code == 200 and r.json()["estado"] == "rechazada", r.text[:200])

# 404 / 401
r = C.post("/pagos/tarjeta/999999/confirmar", headers=H)
check("Confirmar inexistente -> 404", r.status_code == 404, r.text[:200])
check("Sin token -> 401", C.post("/pagos/tarjeta/autorizar", json={"monto": 100}).status_code == 401)

# --- Venta de contado pagada con tarjeta autorizada previamente ---
def crear_producto(precio=12000):
    r = C.post("/productos", headers=H, json={
        "empresa_id": 1, "nombre": f"Tarj {random.randint(1000, 9999)}",
        "sku": f"TARJ{random.randint(10000, 99999)}",
        "precio_venta": precio, "precio_compra": 4000, "costo": 4000,
    })
    assert r.status_code == 201, r.text
    prod = r.json()
    r = C.post("/compras", headers=H, json={
        "empresa_id": 1, "sucursal_id": 1, "proveedor_id": 1, "tipo": "contado",
        "detalle": [{"producto_id": prod["id"], "cantidad": 30, "costo_unitario": 4000}],
    })
    assert r.status_code == 201, r.text
    return prod

prod = crear_producto(12000)
pv = float(prod["precio_venta"])
r = C.post("/pagos/tarjeta/autorizar", headers=H, json={"monto": pv, "marca": "Visa", "ultimos4": "1111"})
tx2 = r.json()
check("Autorización para venta 200", r.status_code == 200 and tx2["estado"] == "aprobada", r.text[:200])

r = C.post(
    "/ventas",
    headers=H,
    json={
        "empresa_id": 1,
        "sucursal_id": 1,
        "tipo": "contado",
        "cliente_id": 1,
        "detalle": [{"producto_id": prod["id"], "cantidad": 1}],
        "pagos": [{"medio": "tarjeta", "monto": pv, "referencia": tx2["codigo_autorizacion"]}],
    },
)
check("Venta pagada con tarjeta 201", r.status_code == 201, r.text[:200])
venta = r.json()
check("Pago tarjeta registrado con referencia", any(p["medio"] == "tarjeta" and p["referencia"] == tx2["codigo_autorizacion"] for p in venta["pagos"]), venta.get("pagos"))
check("Tarjeta confirmada en venta", C.post(f"/pagos/tarjeta/{tx2['id']}/confirmar", headers=H).json()["estado"] == "confirmada")

# Listado
r = C.get("/pagos/tarjeta", headers=H)
check("Listar transacciones 200", r.status_code == 200 and len(r.json()) >= 4, r.text[:200])

# Reversa tras venta fallida: autorizo y luego la venta falla (stock 0 no existe -> apta para error de monto)
r = C.post("/pagos/tarjeta/autorizar", headers=H, json={"monto": 999999999})
tx3 = r.json()
check("Rechazada no reversable (reversar -> 400)", C.post(f"/pagos/tarjeta/{tx3['id']}/reversar", headers=H).status_code == 400)

print(f"\nPagos tarjeta: {ok} OK · {fail} FAIL")
sys.exit(1 if fail else 0)