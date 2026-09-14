from starlette.testclient import TestClient
from app.main import app

client = TestClient(app)
r = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
assert r.status_code == 200, r.text
h = {"Authorization": f'Bearer {r.json()["access_token"]}'}
print("login OK")

# Crear un producto con impuesto
r = client.post(
    "/productos",
    headers=h,
    json={
        "empresa_id": 1,
        "nombre": "Producto Gravado",
        "codigo_barras": "7702004100102",
        "precio_venta": 11900,
        "precio_compra": 7000,
        "costo": 7000,
        "impuesto": 19,
    },
)
assert r.status_code == 201, r.text
prod = r.json()
print("producto OK", prod["id"], "impuesto:", prod["impuesto"])

# Compra directa credito -> entra inventario y genera cuentas por pagar
r = client.post(
    "/compras",
    headers=h,
    json={
        "empresa_id": 1,
        "sucursal_id": 1,
        "proveedor_id": 1,
        "tipo": "credito",
        "detalle": [{"producto_id": prod["id"], "cantidad": 10, "costo_unitario": 7000}],
    },
)
assert r.status_code == 201, r.text
compra = r.json()
print("compra credito OK", compra["numero"], "total:", compra["total"], "estado:", compra["estado"])

# Verificar stock y costo promedio
r = client.get(f"/inventario/stock?producto_id={prod['id']}&sucursal_id=1", headers=h)
# listar stock
r = client.get("/inventario/stock?producto_id=" + str(prod["id"]), headers=h)
assert r.status_code == 200, r.text
r = client.get("/productos/" + str(prod["id"]), headers=h)
print("costo actualizado:", r.json()["costo"])

# Cuentas por pagar
r = client.get("/compras/cuentas-pagar", headers=h)
assert r.status_code == 200, r.text
cuentas = r.json()
print("cuentas por pagar:", len(cuentas), "saldo:", cuentas[0]["saldo"] if cuentas else "n/a")

# Abono a proveedor
if cuentas:
    cid = cuentas[0]["id"]
    r = client.post(
        f"/compras/cuentas-pagar/{cid}/abonos",
        headers=h,
        json={"cuenta_id": cid, "monto": 50000, "medio": "transferencia"},
    )
    assert r.status_code == 201, r.text
    print("abono proveedor OK")

# Crear cliente con limite de credito
r = client.post(
    "/clientes?empresa_id=1",
    headers=h,
    json={"nombre": "Cliente Credito", "tipo_documento": "CC", "documento": "22119988", "tipo": "frecuente", "limite_credito": 500000},
)
assert r.status_code == 201, r.text
cli = r.json()
print("cliente OK", cli["id"])

# Venta a credito
r = client.post(
    "/ventas",
    headers=h,
    json={
        "empresa_id": 1,
        "sucursal_id": 1,
        "cliente_id": cli["id"],
        "tipo": "credito",
        "detalle": [{"producto_id": prod["id"], "cantidad": 2}],
        "pagos": [],
    },
)
assert r.status_code == 201, r.text
venta_c = r.json()
print("venta credito OK", venta_c["numero"], "total:", venta_c["total"], "saldo:", venta_c["saldo"], "impuesto:", venta_c["impuesto"])

# Abono cliente
r = client.post(
    "/cartera/abonos/clientes",
    headers=h,
    json={"empresa_id": 1, "cliente_id": cli["id"], "venta_id": venta_c["id"], "monto": 5000, "medio": "efectivo"},
)
assert r.status_code == 201, r.text
print("abono cliente OK")

# Cartera
r = client.get("/cartera/cuentas-cobrar", headers=h)
assert r.status_code == 200, r.text
print("cartera CxC:", r.json()["total_cartera"])

r = client.get(f"/cartera/estado-cuenta/{cli['id']}", headers=h)
assert r.status_code == 200, r.text
print("estado cuenta OK, saldo:", r.json()["saldo_total"])

# Orden de compra y recepcion
r = client.post(
    "/compras/ordenes",
    headers=h,
    json={"empresa_id": 1, "sucursal_id": 1, "proveedor_id": 1, "detalle": [{"producto_id": prod["id"], "cantidad": 5, "costo_unitario": 6800}]},
)
assert r.status_code == 201, r.text
orden = r.json()
print("orden OK", orden["numero"])
r = client.post(f"/compras/ordenes/{orden['id']}/aprobar", headers=h)
assert r.status_code == 200, r.text
r = client.post(f"/compras/ordenes/{orden['id']}/recibir", headers=h)
assert r.status_code == 200, r.text
print("recepcion orden OK -> estado:", r.json()["estado"])

# Devolucion parcial de la venta a credito
r = client.post(
    "/devoluciones",
    headers=h,
    json={"empresa_id": 1, "sucursal_id": 1, "venta_id": venta_c["id"], "tipo": "parcial", "motivo": "Cliente devolvio 1 unidad", "detalle": [{"producto_id": prod["id"], "cantidad": 1}]},
)
assert r.status_code == 201, r.text
dev = r.json()
print("devolucion parcial OK", dev["numero_nota"], "total:", dev["total_devolucion"])

# Anular una venta contado que no existe, y crear+anular una contado
r = client.post(
    "/ventas",
    headers=h,
    json={"empresa_id": 1, "sucursal_id": 1, "tipo": "contado", "detalle": [{"producto_id": prod["id"], "cantidad": 1}], "pagos": [{"medio": "efectivo", "monto": float(prod["precio_venta"]) * 1.19 + 1}]},
)
assert r.status_code == 201, r.text
vc = r.json()
r = client.post(f"/ventas/{vc['id']}/anular", headers=h)
assert r.status_code == 200, r.text
print("anulacion OK:", r.json()["estado"])

# Configuracion e impuestos
r = client.put("/configuracion/general/nombre-negocio?valor=Mi%20Tienda", headers=h)
assert r.status_code == 200, r.text
r = client.get("/configuracion/impuestos", headers=h)
assert r.status_code == 200, r.text
print("impuestos:", [(i["nombre"], i["tasa"]) for i in r.json()])

# Reportes nuevos
for ruta in ["/reportes/compras", "/reportes/estado-resultados", "/reportes/cartera"]:
    rr = client.get(ruta, headers=h)
    assert rr.status_code == 200, rr.text
    print(ruta, "OK", rr.json())

print("=== TODOS LOS FLUJOS OK ===")