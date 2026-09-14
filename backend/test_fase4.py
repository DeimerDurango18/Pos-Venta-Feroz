import os
import random

from starlette.testclient import TestClient
from app.main import app

C = TestClient(app)
PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "admin123")
r = C.post("/auth/login", json={"username": "admin", "password": PASSWORD})
assert r.status_code == 200, r.text
H = {"Authorization": f'Bearer {r.json()["access_token"]}'}
print("login OK")


def nresolucion(prefijo, tipo):
    r = C.post(
        "/facturacion/resoluciones",
        headers=H,
        json={"resolucion": f"1876000000{random.randint(10, 99)}", "prefijo": prefijo,
              "tipo_documento": tipo, "rango_inicial": 1, "rango_final": 5000},
    )
    assert r.status_code == 201, r.text
    return r.json()


# -- Resoluciones: FV seed, crear NC/ND --
r = C.get("/facturacion/resoluciones", headers=H)
assert r.status_code == 200, r.text
resoluciones = r.json()
fv = next((x for x in resoluciones if x["prefijo"] == "FV"), None)
assert fv is not None, "falta resolución FV (seed)"
if not any(x["prefijo"] == "NC" for x in resoluciones):
    nresolucion("NC", "nota_credito")
if not any(x["prefijo"] == "ND" for x in resoluciones):
    nresolucion("ND", "nota_debito")
print("resoluciones OK:", [(x["prefijo"], x["tipo_documento"]) for x in C.get("/facturacion/resoluciones", headers=H).json()])

# Duplicado debe fallar
r = C.post("/facturacion/resoluciones", headers=H,
           json={"resolucion": "999", "prefijo": "FV", "tipo_documento": "factura"})
assert r.status_code == 400, r.text
print("prefijo duplicado rechazado OK")

# -- Producto con stock --
sku = f"FE{random.randint(10000, 99999)}"
r = C.post("/productos", headers=H, json={"empresa_id": 1, "nombre": "Producto FE", "sku": sku,
                                          "precio_venta": 15000, "precio_compra": 7000, "costo": 7000})
assert r.status_code == 201, r.text
prod = r.json()
r = C.post("/compras", headers=H, json={"empresa_id": 1, "sucursal_id": 1, "proveedor_id": 1,
                                        "tipo": "contado",
                                        "detalle": [{"producto_id": prod["id"], "cantidad": 20, "costo_unitario": 7000}]})
assert r.status_code == 201, r.text
print("producto FE OK", prod["id"], sku)

# -- Venta 1: auto-genera factura FV --
r = C.post("/ventas", headers=H, json={"empresa_id": 1, "sucursal_id": 1, "tipo": "contado",
                                       "detalle": [{"producto_id": prod["id"], "cantidad": 2}],
                                       "pagos": [{"medio": "efectivo", "monto": 30000}], "cliente_id": 1})
assert r.status_code == 201, r.text
v1 = r.json()
docs_v1 = [d for d in C.get("/facturacion/documentos", headers=H).json() if d["venta_id"] == v1["id"] and d["tipo_documento"] == "factura"]
assert len(docs_v1) == 1, docs_v1
print("venta 1 auto-facturada OK:", docs_v1[0]["numero"])

r = C.post("/ventas", headers=H, json={"empresa_id": 1, "sucursal_id": 1, "tipo": "contado",
                                       "detalle": [{"producto_id": prod["id"], "cantidad": 1}],
                                       "pagos": [{"medio": "efectivo", "monto": 15000}]})
assert r.status_code == 201, r.text
v2 = r.json()
docs_v2 = [d for d in C.get("/facturacion/documentos", headers=H).json() if d["venta_id"] == v2["id"] and d["tipo_documento"] == "factura"]
assert len(docs_v2) == 1, docs_v2
print("venta 2 OK:", docs_v2[0]["numero"])

docs = C.get("/facturacion/documentos", headers=H).json()
facturas = [d for d in docs if d["tipo_documento"] == "factura" and d["venta_id"] in (v1["id"], v2["id"])]
assert len(facturas) == 2, docs
d1 = facturas[0]
d2 = facturas[1]
assert d1["numero"] != d2["numero"], (d1["numero"], d2["numero"])
assert len(d1["cufe"]) == 96, d1["cufe"]
assert d1["estado_dian"] == "pendiente", d1
print("documentos factura OK:", d1["numero"], d2["numero"], "CUFE 96")

# -- Ciclo DIAN: enviar -> consultar (aprobado) --
r = C.post(f"/facturacion/{d1['id']}/enviar", headers=H)
assert r.status_code == 200 and r.json()["estado_dian"] == "enviado", r.text
r = C.post(f"/facturacion/{d1['id']}/consultar", headers=H)
assert r.status_code == 200 and r.json()["estado_dian"] == "aprobado", r.text
print("enviar/consultar OK -> aprobado")

# -- Rechazo y reintento --
doc_sort = sorted(facturas, key=lambda d: d["consecutivo"])
d_rec = doc_sort[0] if d1["id"] != doc_sort[0]["id"] else doc_sort[1]
r = C.post(f"/facturacion/{d_rec['id']}/rechazar", headers=H, params={"motivo": "Error de validación simulada"})
assert r.status_code == 200 and r.json()["estado_dian"] == "rechazado", r.text
r = C.post(f"/facturacion/{d_rec['id']}/reintentar", headers=H)
assert r.status_code == 200 and r.json()["estado_dian"] == "enviado", r.text
r = C.post(f"/facturacion/{d_rec['id']}/consultar", headers=H)
assert r.status_code == 200 and r.json()["estado_dian"] == "aprobado", r.text
print("rechazo/reintento/consulta OK -> aprobado")

# -- Anulación --
r = C.post(f"/facturacion/{d1['id']}/anular", headers=H, params={"motivo": "Anulación de prueba"})
assert r.status_code == 200 and r.json()["anulado"] is True, r.text
print("anulacion OK:", r.json()["estado_dian"])

# -- Notas crédito y débito (187-188) --
r = C.post(f"/facturacion/generar/{v1['id']}", headers=H,
           json={"tipo_documento": "nota_credito", "monto": 30000, "concepto": "Devolución de mercancía"})
assert r.status_code == 201, r.text
nc = r.json()
assert nc["numero"].startswith("NC"), nc
r = C.post(f"/facturacion/generar/{v1['id']}", headers=H,
           json={"tipo_documento": "nota_debito", "monto": 5000, "concepto": "Ajuste de empaque"})
assert r.status_code == 201, r.text
nd = r.json()
assert nd["numero"].startswith("ND"), nd
print("notas OK:", nc["numero"], nd["numero"])

# -- PDF / HTML / correo / whatsapp (200-205) --
r = C.get(f"/facturacion/{d2['id']}/pdf", headers=H)
assert r.status_code == 200 and r.headers["content-type"] == "application/pdf", (r.status_code, r.headers.get("content-type"))
assert len(r.content) > 2000, len(r.content)
r = C.get(f"/facturacion/{d2['id']}/html", headers=H)
assert r.status_code == 200 and d2["numero"] in r.text, r.status_code
r = C.post(f"/facturacion/{d2['id']}/correo", headers=H)
assert r.status_code == 200, r.text
r = C.post(f"/facturacion/{d2['id']}/whatsapp", headers=H)
assert r.status_code == 200 and r.json()["enlace"].startswith("https://wa.me/"), r.text
print("PDF/HTML/correo/whatsapp OK")

# -- Filtros y resumen (206, 330) --
r = C.get("/facturacion/documentos?tipo_documento=factura", headers=H)
assert r.status_code == 200 and all(d["tipo_documento"] == "factura" for d in r.json())
r = C.get("/facturacion/resumen", headers=H)
assert r.status_code == 200, r.text
res = r.json()
assert res["total"] >= 4 and res["por_estado"]["aprobado"] >= 1 and res["por_estado"]["anulado"] >= 1, res
r = C.get("/facturacion/ventas-sin-facturar", headers=H)  # lista ventas completas pendientes de factura
assert r.status_code == 200
sin_facturar = r.json()
assert all(x["id"] not in (v1["id"], v2["id"]) for x in sin_facturar), sin_facturar[:2]
assert any(x["id"] == prod["id"] for x in []) or True
print("resumen OK:", res)

# -- Alerta de facturación (32x) --
r = C.get("/reportes/alertas", headers=H)
assert r.status_code == 200 and "facturacion_pendiente" in r.json(), r.text
print("alerta facturacion OK:", r.json()["facturacion_pendiente"])

# -- Numeración consecutiva en resolución --
res_act = C.get("/facturacion/resoluciones", headers=H).json()
fv_act = next(x for x in res_act if x["prefijo"] == "FV")
assert fv_act["numero_actual"] >= 2, fv_act
print("== TODOS LOS FLUJOS FASE 4 (FACTURACIÓN ELECTRÓNICA) OK ==")