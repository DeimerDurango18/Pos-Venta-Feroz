import io

from starlette.testclient import TestClient
from app.main import app

C = TestClient(app)
r = C.post("/auth/login", json={"username": "admin", "password": "admin123"})
assert r.status_code == 200, r.text
H = {"Authorization": f'Bearer {r.json()["access_token"]}'}
print("login OK")

# -- Producto base con stock --
r = C.post(
    "/productos",
    headers=H,
    json={"empresa_id": 1, "nombre": "Promo Test", "sku": "PRM1", "precio_venta": 10000, "precio_compra": 5000, "costo": 5000},
)
assert r.status_code == 201, r.text
prod = r.json()
C.post(
    "/compras",
    headers=H,
    json={"empresa_id": 1, "sucursal_id": 1, "proveedor_id": 1, "tipo": "contado",
          "detalle": [{"producto_id": prod["id"], "cantidad": 50, "costo_unitario": 5000}]},
)
print("producto base OK", prod["id"])

# -- Producto con margen minimo (bloqueo bajo costo) --
r = C.post(
    "/productos",
    headers=H,
    json={"empresa_id": 1, "nombre": "Margen Test", "sku": "MGN1", "precio_venta": 220, "precio_compra": 100, "costo": 100, "margen_minimo": 10},
)
assert r.status_code == 201, r.text
r = C.post(
    "/compras",
    headers=H,
    json={"empresa_id": 1, "sucursal_id": 1, "proveedor_id": 1, "tipo": "contado",
          "detalle": [{"producto_id": r.json()["id"], "cantidad": 10, "costo_unitario": 100}]},
)
assert r.status_code == 201, r.text
margen_id = r.request.content
r = C.get("/productos?q=MGN1", headers=H)
margen_id = [p for p in r.json() if p["sku"] == "MGN1"][0]["id"]
# venta bajo margen minimo debe fallar (precio 100 < 110)
r = C.post(
    "/ventas",
    headers=H,
    json={"empresa_id": 1, "sucursal_id": 1, "tipo": "contado",
          "detalle": [{"producto_id": margen_id, "cantidad": 1, "precio": 100}],
          "pagos": [{"medio": "efectivo", "monto": 100}]},
)
assert r.status_code == 400, r.text
print("bloqueo por margen minimo OK:", r.json()["detail"])

# -- Historial de precios --
r = C.post("/ventas", headers=H, json={"empresa_id": 1, "sucursal_id": 1, "tipo": "contado",
          "detalle": [{"producto_id": prod["id"], "cantidad": 1}], "pagos": [{"medio": "efectivo", "monto": 10000}]})
assert r.status_code == 201, r.text
C.put(f"/productos/{prod['id']}", headers=H, json={"precio_venta": 12000})
r = C.get(f"/productos/{prod['id']}/precios", headers=H)
assert r.status_code == 200 and any(p["campo"] == "precio_venta" for p in r.json()), r.text
print("historial de precios OK:", [(p["campo"], p["valor_anterior"], p["valor_nuevo"]) for p in r.json()])

# -- Promociones -- 2x1 sobre el producto
r = C.post(
    "/promociones",
    headers=H,
    json={"empresa_id": 1, "nombre": "2x1 Promo", "tipo": "2x1", "valor": 0, "aplica_a": "producto",
          "productos": [{"producto_id": prod["id"]}]},
)
assert r.status_code == 201, r.text
print("promo 2x1 creada OK")

# Venta de 3 unidades: 1 gratis -> descuento 10000
r = C.post("/ventas", headers=H, json={"empresa_id": 1, "sucursal_id": 1, "tipo": "contado",
        "detalle": [{"producto_id": prod["id"], "cantidad": 3}],
        "pagos": [{"medio": "efectivo", "monto": 30000}], "propina": 2000})
assert r.status_code == 201, r.text
v = r.json()
assert v["descuento"] == 12000, (v["descuento"], v)
print("promo 2x1 aplicada OK: descuento", v["descuento"], "propina", v["propina"], "total", v["total"])

# -- Suspender / reanudar --
r = C.post(f"/ventas/{v['id']}/suspender", headers=H)
assert r.status_code == 200 and r.json()["estado"] == "suspendida", r.text
r = C.post(f"/ventas/{v['id']}/reanudar", headers=H)
assert r.status_code == 200 and r.json()["estado"] == "completada", r.text
print("suspender/reanudar OK")

# -- Nota debito --
r = C.post(f"/ventas/{v['id']}/nota-debito", headers=H, json={"monto": 500, "concepto": "Ajuste de empaque"})
assert r.status_code == 200, r.text
print("nota debito OK: total", r.json()["total"])

# -- Merma --
from app.database import SessionLocal
from app.models import Stock as StockM
sm = SessionLocal()
st_e = sm.query(StockM).filter_by(producto_id=prod["id"], sucursal_id=1).first()
print("stock_producto_antes_de_merma:", st_e.id if st_e else None, float(st_e.existencias) if st_e else None)
sm.close()
r = C.post(f"/inventario/mermas?producto_id={prod['id']}&cantidad=2&sucursal_id=1&motivo=Producto+dañado", headers=H)
assert r.status_code == 201, r.text
print("merma OK:", r.json()["existencias"])

# -- Conteo fisico: esperado X, contamos 40 --
r = C.post("/inventario/conteos", headers=H, json={"empresa_id": 1, "sucursal_id": 1, "observacion": "Conteo semanal",
          "detalle": [{"producto_id": prod["id"], "contado": 40}]})
assert r.status_code == 201, r.text
conteo = r.json()
r = C.post(f"/inventario/conteos/{conteo['id']}/liquidar", headers=H)
assert r.status_code == 200, r.text
print("conteo fisico OK:", conteo["numero"], "diferencia:", conteo["detalle"][0]["diferencia"], "->", r.json())

# -- Devolucion a proveedor (devolvemos 3 de Stock) --
r = C.post(
    "/compras/devoluciones",
    headers=H,
    json={"empresa_id": 1, "sucursal_id": 1, "proveedor_id": 1, "tipo": "parcial", "motivo": "Mercancia en mal estado",
          "detalle": [{"producto_id": prod["id"], "cantidad": 3}]},
)
assert r.status_code == 201, r.text
print("devolucion a proveedor OK:", r.json()["numero"], "total:", r.json()["total_devolucion"])

# -- Estado de cuenta de proveedor --
r = C.get("/compras/estado-cuenta/1", headers=H)
assert r.status_code == 200, r.text
print("estado cuenta proveedor OK: compras", len(r.json()["compras"]), "cuentas", len(r.json()["cuentas"]))

# -- Cotizacion de proveedor --
r = C.post(
    "/compras/cotizaciones",
    headers=H,
    json={"empresa_id": 1, "proveedor_id": 1, "notas": "Costo unitario del mes",
          "detalle": [{"producto_id": prod["id"], "cantidad": 20, "costo_unitario": 4900}]},
)
assert r.status_code == 201, r.text
cot = r.json()
r = C.post(f"/compras/cotizaciones/{cot['id']}/aprobar", headers=H)
assert r.status_code == 200, r.text
print("cotizacion OK:", cot["numero"], "total est:", cot["total_estimado"], "-> estado:", r.json()["estado"])

# -- Compras sugeridas (punto de reorden) --
r = C.get("/reportes/compras-sugeridas", headers=H)
assert r.status_code == 200, r.text
print("compras sugeridas OK:", len(r.json()))

# -- Alertas --
r = C.get("/reportes/alertas", headers=H)
assert r.status_code == 200, r.text
print("alertas OK:", r.json())

# -- Vendedores: marcamos admin como vendedor + meta + regla --
C.put("/usuarios/1", headers=H, json={"vendedor": True})
r = C.post("/vendedores/metas", headers=H, json={"vendedor_id": 1, "periodo": "2026-09", "meta_ventas": 100000, "meta_utilidad": 30000})
assert r.status_code == 201, r.text
r = C.post("/vendedores/reglas-comision", headers=H, json={"empresa_id": 1, "porcentaje": 2})
assert r.status_code == 201, r.text
r = C.get("/reportes/vendedores", headers=H)
assert r.status_code == 200, r.text
print("vendedores OK:", [(x["vendedor"], round(x["ventas"]), x["comision"]) for x in r.json()])

# -- Auditoria --
r = C.get("/reportes/auditoria", headers=H)
assert r.status_code == 200 and len(r.json()) > 0, r.text
print("auditoria OK:", len(r.json()), "registros")

# -- Importar/Exportar CSV --
r = C.get("/exportar/productos", headers=H)
assert r.status_code == 200 and r.text.strip().startswith("id,nombre"), r.text[:100]
csv_ok = r.text
r = C.get("/exportar/clientes", headers=H)
assert r.status_code == 200, "export clientes"
r = C.get("/exportar/inventario", headers=H)
assert r.status_code == 200, "export inventario"
# importar un producto nuevo en CSV
nuevo_csv = csv_ok + "\n,nuevo_sku_imp,IMP1,7700001,,1300,,600,,0,true"
import re
linea = "1000,Importado via CSV,IMPORT1,7700999,,9900,5000,5000,19,true"
nuevo_csv_ok = "id,nombre,sku,codigo_barras,plu,precio_venta,precio_compra,costo,impuesto,activo\n" + linea
r = C.post("/importar/productos", headers=H, files={"archivo": ("p.csv", nuevo_csv_ok, "text/csv")})
assert r.status_code == 200, r.text
print("import/export CSV OK:", r.json())

print("=== TODOS LOS FLUJOS FASE 3 OK ===")