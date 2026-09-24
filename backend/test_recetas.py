"""Recetas / ingredientes / costeo / venta de combos (44, 45, 147, 148, 159, 416, 417, 418)."""

import random

from starlette.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Configuracion, MovimientoInventario, Stock

C = TestClient(app)


def login(user, pw):
    r = C.post("/auth/login", json={"username": user, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f'Bearer {r.json()["access_token"]}'}


H = login("admin", "admin123")
print("login admin OK")

ok = 0
fail = 0


def check(nombre, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  [OK] {nombre}")
    else:
        fail += 1
        print(f"  [FALLO] {nombre}  {extra}")


def crear_producto(precio=10000, costo=5000, **kw):
    r = C.post("/productos", headers=H, json={
        "empresa_id": 1,
        "nombre": f"Prod REC {random.randint(1000, 9999)}",
        "sku": f"REC{random.randint(10000, 99999)}",
        "codigo_barras": kw.pop("codigo_barras", f"770{random.randint(100000000, 999999999)}"),
        "precio_venta": precio, "precio_compra": costo, "costo": costo,
        **kw,
    })
    assert r.status_code == 201, f"crear producto {r.text}"
    prod = r.json()
    r = C.post("/compras", headers=H, json={
        "empresa_id": 1, "sucursal_id": 1, "proveedor_id": 1, "tipo": "contado",
        "detalle": [{"producto_id": prod["id"], "cantidad": 60, "costo_unitario": costo}],
    })
    assert r.status_code == 201, r.text
    return prod


def stock_de(producto_id):
    with SessionLocal() as db:
        s = db.query(Stock).filter_by(producto_id=producto_id, sucursal_id=1).first()
        return float(s.existencias) if s else None


def mov_venta_combo():
    with SessionLocal() as db:
        return db.query(MovimientoInventario).filter(MovimientoInventario.motivo == "Venta combo").count()


def venta(detalle, pagos, **kw):
    body = {"empresa_id": 1, "sucursal_id": 1, "tipo": "contado",
            "detalle": detalle, "pagos": pagos, **kw}
    return C.post("/ventas", headers=H, json=body)


print("\n== 1. Receta / ingredientes / costeo ==")
a = crear_producto(precio=2500, costo=1000)
b = crear_producto(precio=4500, costo=2000)
k = crear_producto(precio=15000, costo=2000)

r = C.get(f"/productos/{k['id']}/receta", headers=H)
check("GET receta inicial 200", r.status_code == 200, r.text)
if r.status_code == 200:
    check("Producto no compuesto al inicio", r.json()["es_compuesto"] is False, r.json())

r = C.put(f"/productos/{k['id']}/receta", headers=H,
          json={"ingredientes": [{"componente_id": a["id"], "cantidad": 2},
                                 {"componente_id": b["id"], "cantidad": 1}]})
check("PUT receta 201", r.status_code == 201, r.text)
if r.status_code == 201:
    rec = r.json()
    check("Marcado como compuesto", rec["es_compuesto"] is True)
    check("Costo calculado = 4000", abs(rec["costo_calculado"] - 4000) < 0.01, rec)
    check("2 ingredientes", len(rec["ingredientes"]) == 2, rec["ingredientes"])
    check("Stock de ingrediente mostrado", rec["ingredientes"][0]["stock"] == 60, rec["ingredientes"][0])

r = C.get(f"/productos/{k['id']}/receta", headers=H)
rec = r.json()
check("GET receta refleja componentes y stocks", len(rec["ingredientes"]) == 2 and rec["ingredientes"][0]["stock"] == 60, rec)

r = C.post(f"/productos/{k['id']}/costear", headers=H)
check("POST costear 200", r.status_code == 200, r.text)
if r.status_code == 200:
    cj = r.json()
    check("Costeo = 4000 y margen ~73.33%", abs(cj["costo_calculado"] - 4000) < 0.01 and abs(cj["margen_pct"] - 73.33) < 0.1, cj)

r = C.put(f"/productos/{k['id']}/receta", headers=H, json={"ingredientes":
          [{"componente_id": a["id"], "cantidad": 2}, {"componente_id": a["id"], "cantidad": 1}]})
check("Receta con ingrediente duplicado se suma", r.status_code == 201 and
      r.json()["costo_calculado"] == 3000, r.text[:160])
C.put(f"/productos/{k['id']}/receta", headers=H, json={"ingredientes":
      [{"componente_id": a["id"], "cantidad": 2}, {"componente_id": b["id"], "cantidad": 1}]})

r = C.put(f"/productos/{k['id']}/receta", headers=H, json={"ingredientes":
          [{"componente_id": k["id"], "cantidad": 1}]})
check("Auto-referencia rechazada -> 400", r.status_code == 400, r.text)

print("\n== 2. Venta de combos: consume materias primas (flag off/on) ==")
with SessionLocal() as db:
    db.query(Configuracion).filter(Configuracion.clave == "pos.combos_consumen").delete()
    db.commit()

mov0 = mov_venta_combo()
stk_a0 = stock_de(a["id"])
stk_b0 = stock_de(b["id"])
r = venta([{"producto_id": k["id"], "cantidad": 1}], [{"medio": "efectivo", "monto": 15000}])
check("Venta combo (flag off) 201", r.status_code == 201, r.text)
check("Sin consumo con flag off (stock intacto)", stock_de(a["id"]) == stk_a0 and stock_de(b["id"]) == stk_b0,
      (stock_de(a["id"]), stock_de(b["id"])))
check("Sin movimientos 'Venta combo' con flag off", mov_venta_combo() == mov0, mov_venta_combo())

r = C.put("/configuracion/general/pos.combos_consumen?valor=1", headers=H)
check("Flag combos_consumen activado", r.status_code == 200, r.text)

r = venta([{"producto_id": k["id"], "cantidad": 1}], [{"medio": "efectivo", "monto": 15000}])
check("Venta combo (flag on) 201", r.status_code == 201, r.text)
check("Materias primas descontadas (A -2, B -1)", stock_de(a["id"]) == stk_a0 - 2 and stock_de(b["id"]) == stk_b0 - 1,
      (stock_de(a["id"]), stock_de(b["id"])))
check("Movimientos de consumo registrados", mov_venta_combo() == mov0 + 2, mov_venta_combo())

k2 = crear_producto(precio=20000, costo=1000)
r = C.put(f"/productos/{k2['id']}/receta", headers=H, json={"ingredientes":
          [{"componente_id": b["id"], "cantidad": 100}]})
check("Receta de combo exigente OK", r.status_code == 201, r.text)
r = venta([{"producto_id": k2["id"], "cantidad": 1}], [{"medio": "efectivo", "monto": 20000}])
check("Venta de combo sin materia prima -> 400", r.status_code == 400 and "materia prima" in r.text.lower(), r.text)
check("Sin consumo parcial en rechazo", stock_de(b["id"]) == stk_b0 - 1, stock_de(b["id"]))

C.put("/configuracion/general/pos.combos_consumen?valor=0", headers=H)
print(f"\nResultado: {ok} OK, {fail} FALLO")
exit(1 if fail else 0)