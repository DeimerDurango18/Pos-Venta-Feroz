"""Validación del módulo de COTIZACIONES (presupuestos 1-clic)."""

import random

from sqlalchemy import text
from starlette.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Promocion, Stock

C = TestClient(app)


def login(user, pw):
    r = C.post("/auth/login", json={"username": user, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f'Bearer {r.json()["access_token"]}'}


H = login("admin", "admin123")
Hc = login("cajero", "cajero123")
print("login OK")

with SessionLocal() as db:
    db.query(Promocion).update({"activa": False})
    db.commit()

ok = 0
fail = 0


def check(nombre, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {nombre}")
    else:
        fail += 1
        print(f"  [FALLO] {nombre}  {extra}")


def crear_producto(precio=10000, costo=5000, impuesto=19):
    r = C.post("/productos", headers=H, json={
        "empresa_id": 1,
        "nombre": f"Prod COT {random.randint(1000, 9999)}",
        "sku": f"COT{random.randint(10000, 99999)}",
        "codigo_barras": f"770{random.randint(100000000, 999999999)}",
        "precio_venta": precio, "precio_compra": costo, "costo": costo,
        "impuesto": impuesto,
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


def crear_cotizacion(detalle, **kw):
    body = {
        "empresa_id": 1,
        "sucursal_id": 1,
        "detalle": detalle,
        **kw,
    }
    return C.post("/cotizaciones", headers=H, json=body)


# ================= 1. CREAR COTIZACIÓN =================
print("\n== 1. Crear y listar cotizaciones ==")
p1 = crear_producto(precio=10000, impuesto=19)
p2 = crear_producto(precio=25000, impuesto=19)
stk_inicial = stock_de(p1["id"])

r = crear_cotizacion([
    {"producto_id": p1["id"], "cantidad": 2},
    {"producto_id": p2["id"], "cantidad": 1},
], cliente_nombre="Cliente Cotización", cliente_telefono="3012345678", vence="2099-12-31")
check("Crear cotización 201", r.status_code == 201, r.text)
c = r.json()
check("Número COT-xxxxxx", (c.get("numero") or "").startswith("COT-"), c)
# 2*10000 + 1*25000 = 45000 subtotal, IVA 19% -> 8550
check("Subtotal correcto", abs(c["subtotal"] - 45000) < 0.01, c)
check("IVA 19% correcto", abs(c["impuesto"] - 8550) < 0.01, c)
check("Total correcto", abs(c["total"] - 53550) < 0.01, c)
check("Estado vigente", c["estado"] == "vigente", c)
check("No descuenta inventario", stock_de(p1["id"]) == stk_inicial, stock_de(p1["id"]))

r2 = crear_cotizacion([{"producto_id": p1["id"], "cantidad": 1}], descuento_global=10)
check("Cotización con descuento global", r2.status_code == 201, r2.text)
c2 = r2.json()
# Igual que ventas: el descuento global resta al subtotal pero el IVA se
# calculó antes (10000 + 1900 - 1000) = 10900
check("Descuento global 10%", abs(c2["total"] - 10900) < 0.01, c2)

r3 = crear_cotizacion([])
check("Sin productos rechazada (400)", r3.status_code == 400, r3.text)

lst = C.get("/cotizaciones", headers=H).json()
check("Listar todas incluye las creadas", len(lst) >= 2, len(lst))
lst_vig = C.get("/cotizaciones?estado=vigente", headers=H).json()
check("Filtro por estado vigente", all(x["estado"] == "vigente" for x in lst_vig), [x["estado"] for x in lst_vig])

# ================= 2. VENCIMIENTO AUTOMÁTICO =================
print("\n== 2. Vencimiento ==")
rv = crear_cotizacion([{"producto_id": p1["id"], "cantidad": 1}], vence="2000-01-01")
check("Cotización vencimiento pasado 201", rv.status_code == 201, rv.text)
lst2 = C.get("/cotizaciones?estado=vencida", headers=H).json()
check("Marcada automáticamente como vencida", any(x["id"] == rv.json()["id"] and x["estado"] == "vencida" for x in lst2), lst2)

# ================= 3. CONVERTIR A VENTA =================
print("\n== 3. Convertir a venta (1-clic) ==")
stk_inicial2 = stock_de(p1["id"])
r = C.post(f"/cotizaciones/{c['id']}/convertir", headers=H)
check("Convertir 200", r.status_code == 200, r.text)
j = r.json()
check("Venta creada y asociada", j.get("venta_id") and j["numero_venta"].startswith("V-"), j)
check("Descuenta inventario (-2)", stock_de(p1["id"]) == stk_inicial2 - 2, stock_de(p1["id"]))

det = C.get(f"/cotizaciones/{c['id']}", headers=H).json()
check("Cotización marcada convertida", det["estado"] == "convertida" and det["venta_id"] == j["venta_id"], det)

# Segunda conversión debe rechazarse
r = C.post(f"/cotizaciones/{c['id']}/convertir", headers=H)
check("Doble conversión rechazada (400)", r.status_code == 400, r.text)

# ================= 4. ANULAR =================
print("\n== 4. Anulación ==")
ra = crear_cotizacion([{"producto_id": p2["id"], "cantidad": 1}])
aid = ra.json()["id"]
r = C.post(f"/cotizaciones/{aid}/anular", headers=H)
check("Anular 200", r.status_code == 200, r.text)
det = C.get(f"/cotizaciones/{aid}", headers=H).json()
check("Estado anulada", det["estado"] == "anulada", det)
r = C.post(f"/cotizaciones/{aid}/anular", headers=H)
check("Doble anulación rechazada (400)", r.status_code == 400, r.text)
r = C.post(f"/cotizaciones/{aid}/convertir", headers=H)
check("Convertir anulada rechazada (400)", r.status_code == 400, r.text)

# ================= 5. PERMISOS / AUDITORÍA =================
print("\n== 5. Auditoría ==")
with SessionLocal() as db:
    desde_app = db.execute(text("SELECT COUNT(*) FROM auditoria_log WHERE accion LIKE '%cotizacion%'")).scalar()
check("Hay auditoría de cotizaciones", int(desde_app or 0) >= 3, desde_app)

print(f"\nRESUMEN COTIZACIONES: {ok} OK · {fail} FAIL")
raise SystemExit(0 if fail == 0 else 1)