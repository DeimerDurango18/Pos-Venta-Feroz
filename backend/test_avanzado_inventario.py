import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from datetime import date, timedelta

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


# Limpieza de datos de corridas previas
# Limpieza de datos de corridas previas
from app.database import SessionLocal
from app.models import Bodega, Configuracion, InventarioTransito, StockBodega, Sucursal, Ubicacion

with SessionLocal() as db:
    import sqlalchemy as sa
    db.query(InventarioTransito).delete()
    db.query(StockBodega).delete()
    db.query(Ubicacion).delete()
    db.query(Bodega).filter(Bodega.codigo.in_(["BOD-AI-1", "BOD-AI-2", "BOD-AI-3", "BOD-AL-1", "BOD-AL-2"])).delete()
    suc_ids = db.execute(sa.text("SELECT id FROM sucursales WHERE codigo LIKE 'SUC-AI-%'")).scalars().all()
    if suc_ids:
        sids = ",".join(str(i) for i in suc_ids)
        db.execute(sa.text(f"DELETE FROM stock WHERE sucursal_id IN ({sids})"))
        db.execute(sa.text(f"DELETE FROM movimientos_inventario WHERE sucursal_id IN ({sids})"))
        db.execute(sa.text(f"DELETE FROM sucursales WHERE id IN ({sids})"))
    row = db.query(Configuracion).filter(Configuracion.clave == "pos.inventario_negativo").first()
    if row:
        row.valor = "0"
    db.commit()
print("limpieza previa OK")

r = C.post("/auth/login", json={"username": "admin", "password": "admin123"})
H = {"Authorization": "Bearer " + r.json()["access_token"]}
print("login admin OK")

# ---- Producto propio y sucursal 2 ----
r = C.post("/productos", headers=H, json={"empresa_id": 1, "nombre": "AI Producto", "sku": "AI-PROD", "precio_venta": 1000, "precio_compra": 200, "costo": 200})
PROD = r.json()["id"]

r = C.post("/organizacion/sucursales", headers=H, json={"empresa_id": 1, "nombre": "AI Sucursal 2", "codigo": "SUC-AI-2"})
check("crear sucursal 2", r.status_code == 201 and r.json()["id"] > 1, str(r.status_code))
SUC2 = r.json()["id"]

# Compra contado para alimentar reportes de compras y proveedores (queda recibida)
r = C.post("/compras", headers=H, json={"empresa_id": 1, "sucursal_id": 1, "proveedor_id": 1, "tipo": "contado",
                                        "detalle": [{"producto_id": PROD, "cantidad": 10, "costo_unitario": 200}]})
check("crear compra recibida", r.status_code == 201 and r.json()["estado"] == "recibida", str(r.status_code))
COMPRA = r.json()["id"]

# ---- Bodegas y ubicaciones ----
r = C.post("/inventario/bodegas", headers=H, json={"empresa_id": 1, "sucursal_id": 1, "nombre": "AI Bodega 1", "codigo": "BOD-AI-1"})
B1 = r.json()["id"]
r = C.post("/inventario/bodegas", headers=H, json={"empresa_id": 1, "sucursal_id": 1, "nombre": "AI Bodega 2", "codigo": "BOD-AI-2"})
B2 = r.json()["id"]
r = C.post("/inventario/bodegas", headers=H, json={"empresa_id": 1, "sucursal_id": SUC2, "nombre": "AI Bodega 3", "codigo": "BOD-AI-3"})
B3 = r.json()["id"]
check("crear bodegas", B1 and B2 and B3, "")

r = C.post(f"/inventario/bodegas/{B1}/ubicaciones", headers=H, json={"bodega_id": B1, "nombre": "Est. AI A"})
UA = r.json()["id"]
r = C.get("/inventario/bodegas", headers=H)
check("listar bodegas", any(b["id"] == B3 for b in r.json()), "")
r = C.get(f"/inventario/bodegas/{B1}/ubicaciones", headers=H)
check("listar ubicaciones", any(u["id"] == UA for u in r.json()), "")

# ---- Stock por bodega ----
r = C.post("/inventario/stock-bodega", headers=H, json={"producto_id": PROD, "bodega_id": B1, "tipo": "entrada", "cantidad": 10, "motivo": "entrada inicial"})
check("entrada bodega", r.status_code == 201 and r.json()["existencias"] == 10.0, str(r.status_code) + str(r.json()))
r = C.post("/inventario/stock-bodega", headers=H, json={"producto_id": PROD, "bodega_id": B1, "tipo": "salida", "cantidad": 4, "motivo": "consumo"})
check("salida bodega", r.status_code == 201 and r.json()["existencias"] == 6.0, str(r.status_code) + str(r.json()))
r = C.post("/inventario/stock-bodega", headers=H, json={"producto_id": PROD, "bodega_id": B1, "tipo": "salida", "cantidad": 100})
check("salida bodega insuficiente", r.status_code == 400, str(r.status_code))
r = C.post("/inventario/stock-bodega", headers=H, json={"producto_id": PROD, "bodega_id": B1, "tipo": "reubicar", "cantidad": 3, "ubicacion_id": UA})
check("reubicar a ubicacion", r.status_code == 201 and r.json()["existencias"] == 3.0, str(r.status_code) + str(r.json()))
r = C.get("/inventario/por-bodega", headers=H, params={"bodega_id": B1})
check("reporte por bodega", any(x["existencias"] == 6.0 for x in r.json()), str(r.json())[:120])
r = C.get("/inventario/por-ubicacion", headers=H)
check("reporte por ubicacion", any(x["ubicacion"] == "Est. AI A" and x["existencias"] == 3.0 for x in r.json()), str(r.json())[:120])

# ---- Transferencias ----
r = C.post("/inventario/transferir-bodega", headers=H, json={"producto_id": PROD, "cantidad": 2, "origen_bodega_id": B1, "destino_bodega_id": B2})
check("transferencia misma sucursal", r.status_code == 201 and r.json()["estado"] == "recibido", str(r.status_code) + str(r.json()))
r = C.get("/inventario/por-bodega", headers=H, params={"bodega_id": B1})
check("origen descontado", any(x["existencias"] == 4.0 for x in r.json()), str(r.json())[:120])
r = C.get("/inventario/por-bodega", headers=H, params={"bodega_id": B2})
check("destino acreditado", any(x["existencias"] == 2.0 for x in r.json()), str(r.json())[:120])

# Stock propio de B2 para la trayectoria entre sucursales (desacoplada)
r = C.post("/inventario/stock-bodega", headers=H, json={"producto_id": PROD, "bodega_id": B2, "tipo": "entrada", "cantidad": 5, "motivo": "stock b2"})
check("entrada bodega B2", r.status_code == 201, str(r.status_code))

r = C.post("/inventario/transferir-bodega", headers=H, json={"producto_id": PROD, "cantidad": 3, "origen_bodega_id": B2, "destino_bodega_id": B3, "motivo": "envio"})
check("transferencia entre sucursales -> transito", r.status_code == 201 and r.json()["estado"] == "en_transito", str(r.status_code) + str(r.json()))
TID = r.json()["transito"]["id"]
r = C.get("/inventario/transito", headers=H)
check("listar en transito", any(t["id"] == TID for t in r.json()), str(r.json()))
r = C.post(f"/inventario/transito/{TID}/recibir", headers=H)
check("recibir transito", r.status_code == 200 and r.json()["estado"] == "recibido", str(r.status_code))
r = C.get("/inventario/por-bodega", headers=H, params={"bodega_id": B3})
check("transito recibido en destino", any(x["existencias"] == 3.0 for x in r.json()), str(r.json())[:120])

# segunda transfer cancelable (desde B2, que quedó en 4)
r = C.post("/inventario/transferir-bodega", headers=H, json={"producto_id": PROD, "cantidad": 1, "origen_bodega_id": B2, "destino_bodega_id": B3})
TID2 = r.json()["transito"]["id"]
r = C.post(f"/inventario/transito/{TID2}/cancelar", headers=H)
check("cancelar transito", r.status_code == 200 and r.json()["estado"] == "cancelado", str(r.status_code))
r = C.get("/inventario/por-bodega", headers=H, params={"bodega_id": B2})
check("cancelar devuelve al origen", any(x["existencias"] == 4.0 for x in r.json()), str(r.json())[:120])

# ---- Lotes y vencimientos ----
r = C.post("/inventario/lotes", headers=H, json={"producto_id": PROD, "codigo": "L-AI-001", "vencimiento": (date.today() - timedelta(days=5)).isoformat()})
LTE = r.json()["id"]
check("crear lote vencido", r.status_code == 201, str(r.status_code))
r = C.post("/inventario/lotes/stock", headers=H, json={"lote_id": LTE, "cantidad": 8, "motivo": "recepcion lote"})
check("ingresar stock a lote", r.status_code == 201 and r.json()["cantidad"] == 8.0, str(r.status_code) + str(r.json()))
r = C.post("/inventario/lotes/salida", headers=H, json={"lote_id": LTE, "cantidad": 3, "motivo": "despacho"})
check("despachar de lote", r.status_code == 201 and r.json()["cantidad"] == 5.0, str(r.status_code) + str(r.json()))
r = C.post("/inventario/lotes/salida", headers=H, json={"lote_id": LTE, "cantidad": 50})
check("lote stock insuficiente", r.status_code == 400, str(r.status_code))
r = C.get("/inventario/por-lote", headers=H, params={"producto_id": PROD})
check("por lote marca vencido", any(x["estado"] == "vencido" for x in r.json()), str(r.json())[:120])
r = C.get("/inventario/lotes", headers=H, params={"producto_id": PROD})
check("listar lotes", any(x["codigo"] == "L-AI-001" for x in r.json()), "")

# ---- Conteo cÃ­clico ----
r = C.post("/inventario/conteos", headers=H, json={"empresa_id": 1, "sucursal_id": 1, "tipo": "ciclico",
                                                   "detalle": [{"producto_id": PROD, "contado": 9}]})
CIC = r.json()["id"]
check("crear conteo ciclico", r.status_code == 201 and r.json().get("tipo") == "ciclico", str(r.status_code) + str(r.json()))
r = C.post(f"/inventario/conteos/{CIC}/liquidar", headers=H)
check("liquidar conteo", r.status_code == 200, str(r.status_code))
r = C.get("/inventario/conteos", headers=H, params={"tipo": "ciclico"})
check("listar conteos ciclicos", any(c["id"] == CIC for c in r.json()), "")

# ---- Inventario negativo (config) ----
r = C.put("/configuracion/general/pos.inventario_negativo?valor=1", headers=H)
check("activar inventario negativo", r.status_code in (200, 204), str(r.status_code))
r = C.post("/inventario/movimientos", headers=H, json={"producto_id": PROD, "sucursal_id": 1, "tipo": "salida", "cantidad": 99999, "motivo": "prueba negativo"})
check("salida sin stock permitida (negativo on)", r.status_code == 201, str(r.status_code))
r = C.put("/configuracion/general/pos.inventario_negativo?valor=0", headers=H)
r = C.post("/inventario/movimientos", headers=H, json={"producto_id": PROD, "sucursal_id": 1, "tipo": "salida", "cantidad": 5, "motivo": "debe fallar"})
check("salida sin stock bloqueada (negativo off)", r.status_code == 400, str(r.status_code))

# ---- Reportes ----
for ep in ("/reportes/rotacion", "/reportes/inventario-por-categoria", "/reportes/inventario-por-sucursal",
           "/reportes/inventario-por-bodega", "/reportes/diferencias-inventario"):
    r = C.get(ep, headers=H)
    check(f"reporte {ep.split('/')[-1]}", r.status_code == 200, str(r.status_code))
for ep in ("/reportes/compras-periodo", "/reportes/compras-por-proveedor", "/reportes/compras-por-producto",
           "/reportes/compras-por-sucursal", "/reportes/compras-pendientes", "/reportes/compras-recibidas",
           "/reportes/compras-anuladas"):
    r = C.get(ep, headers=H)
    check(f"reporte {ep.split('/')[-1]}", r.status_code == 200, str(r.status_code))
r = C.get("/reportes/compras-recibidas", headers=H)
check("compras recibidas incluye la compra", any(c["compra_id"] == COMPRA for c in r.json()), str(r.json())[:160])
r = C.get("/reportes/proveedores-principales", headers=H)
check("proveedores principales", r.status_code == 200 and r.json(), str(r.status_code))
r = C.get("/reportes/proveedores-historial/1", headers=H)
check("historial proveedor", r.status_code == 200 and r.json()["numero_compras"] > 0, str(r.status_code))
r = C.get("/reportes/productos-por-proveedor", headers=H)
check("productos por proveedor", r.status_code == 200, str(r.status_code))
r = C.get("/reportes/precios-proveedor/1", headers=H)
check("precios proveedor", r.status_code == 200 and any(p["producto_id"] == PROD for p in r.json()), str(r.status_code) + str(r.json())[:160])

print(f"\n========== MODULO INVENTARIO AVANZADO: {ok} OK Â· {fail} FALLO ==========")
sys.exit(1 if fail else 0)
