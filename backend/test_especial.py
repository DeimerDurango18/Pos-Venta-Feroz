import random

from starlette.testclient import TestClient
from app.main import app

C = TestClient(app)


def login(user, pw):
    r = C.post("/auth/login", json={"username": user, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f'Bearer {r.json()["access_token"]}'}


H = login("admin", "admin123")
Hc = login("cajero", "cajero123")
print("login admin/cajero OK")


def crear_producto(precio=15000):
    r = C.post("/productos", headers=H, json={
        "empresa_id": 1, "nombre": f"Prod ESP {random.randint(1000, 9999)}",
        "sku": f"ESP{random.randint(10000, 99999)}",
        "precio_venta": precio, "precio_compra": 7000, "costo": 7000,
    })
    assert r.status_code == 201, r.text
    prod_id = r.json()["id"]
    r = C.post("/compras", headers=H, json={
        "empresa_id": 1, "sucursal_id": 1, "proveedor_id": 1, "tipo": "contado",
        "detalle": [{"producto_id": prod_id, "cantidad": 30, "costo_unitario": 7000}],
    })
    assert r.status_code == 201, r.text
    return prod_id


# ================= FIDELIZACIÓN (165-169) =================
r = C.post("/clientes", headers=H, params={"empresa_id": 1}, json={
    "nombre": f"Cliente Fid {random.randint(1000, 9999)}",
    "documento": str(random.randint(1000000000, 9999999999)), "tipo": "frecuente",
})
assert r.status_code == 201, r.text
cli = r.json()
print("cliente OK", cli["id"])

cupon_cod = f"CUP{random.randint(10000, 99999)}"
r = C.post("/fidelizacion/cupones", headers=H, json={
    "codigo": cupon_cod, "tipo": "porcentaje", "valor": 10, "usos_max": 3,
    "cliente_id": cli["id"], "descripcion": "10% prueba",
})
assert r.status_code == 201, r.text
r = C.post("/fidelizacion/cupones", headers=H, json={"codigo": cupon_cod, "tipo": "valor", "valor": 100})
assert r.status_code == 400, "debe rechazar código duplicado"
print("cupón OK + duplicado rechazado")

r = C.post("/fidelizacion/tarjetas-regalo", headers=H, json={"cliente_id": cli["id"], "codigo": f"TG{random.randint(10000, 99999)}", "saldo": 5000})
assert r.status_code == 201, r.text
tarjeta = r.json()
r = C.post("/fidelizacion/bonos", headers=H, json={"cliente_id": cli["id"], "codigo": f"BO{random.randint(10000, 99999)}", "valor_total": 10000})
assert r.status_code == 201, r.text
bono = r.json()
print("tarjeta/bono OK")

prod = crear_producto(15000)
# Venta con cupón + tarjeta de regalo: total (2*15000 - 10% = 27000); pagos 22000 efectivo + 5000 tarjeta
r = C.post("/ventas", headers=H, json={
    "empresa_id": 1, "sucursal_id": 1, "tipo": "contado", "cliente_id": cli["id"],
    "cupon_codigo": cupon_cod,
    "detalle": [{"producto_id": prod, "cantidad": 2}],
    "pagos": [{"medio": "efectivo", "monto": 22000}, {"medio": "tarjeta_regalo", "referencia": tarjeta["codigo"], "monto": 5000}],
})
assert r.status_code == 201, r.text
v = r.json()
assert abs(v["total"] - 27000) < 0.01, v
r = C.get(f"/fidelizacion/tarjetas-regalo", headers=H)
tg = next(t for t in r.json() if t["id"] == tarjeta["id"])
assert abs(tg["saldo"]) < 0.01 and tg["estado"] == "agotada", tg
r = C.get(f"/fidelizacion/puntos/historial/{cli['id']}", headers=H)
assert r.status_code == 200 and len(r.json()) >= 1, r.text
his = r.json()
lp = {"puntos": sum(m["delta"] for m in his)}
assert lp["puntos"] == 27, lp
print(f"venta con cupón/tarjeta/puntos OK: total {v['total']}, puntos {lp['puntos']}")

# ================= APARTADOS (390-394) =================
r = C.post("/apartados", headers=H, json={
    "cliente_id": cli["id"], "abono_inicial": 10000,
    "detalle": [{"producto_id": prod, "cantidad": 1, "precio": 15000}],
})
assert r.status_code == 201, r.text
ap1 = r.json()
assert ap1["estado"] == "abierto" and abs(ap1["pendiente"] - 5000) < 0.01, ap1
r = C.post(f"/apartados/{ap1['id']}/abonos", headers=H, json={"monto": 5000})
assert r.status_code == 201 and r.json()["estado"] == "pagado", r.text
r = C.post(f"/apartados/{ap1['id']}/liquidar", headers=H)
assert r.status_code == 201 and r.json()["estado"] == "liquidado", r.text
liq = r.json()
r = C.get("/facturacion/documentos", headers=H)
assert any(d["venta_id"] == liq["venta_id"] for d in r.json()), "liquidación debe auto-facturar"
print("apartados OK: abono+liquidación+auto-factura")

r = C.post("/apartados", headers=H, json={
    "cliente_id": cli["id"], "abono_inicial": 3000,
    "detalle": [{"producto_id": prod, "cantidad": 1, "precio": 15000}],
})
assert r.status_code == 201, r.text
ap_cancel = r.json()
r = C.post(f"/apartados/{ap_cancel['id']}/cancelar", headers=H)
assert r.status_code == 200 and r.json()["estado"] == "cancelado", r.text
print("apartado cancelado OK")

# ================= PEDIDOS (395-407) =================
r = C.post("/pedidos", headers=H, json={
    "cliente_id": cli["id"], "tipo": "mostrador", "nota": "prueba",
    "detalle": [{"producto_id": prod, "cantidad": 3}],
})
assert r.status_code == 201, r.text
ped = r.json()
assert ped["estado"] == "pendiente" and ped["numero"].startswith("PD-"), ped
for est in ("en_preparacion", "listo"):
    r = C.post(f"/pedidos/{ped['id']}/estado", headers=H, params={"estado": est})
    assert r.status_code == 200 and r.json()["estado"] == est, r.text

import requests as _r  # noqa - ver estado de stock antes de entregar

r = C.post(f"/pedidos/{ped['id']}/entregar", headers=H)
assert r.status_code == 200 and r.json()["estado"] == "entregado", r.text

r = C.post("/pedidos", headers=H, json={
    "cliente_id": cli["id"], "tipo": "domicilio", "direccion_entrega": "Calle 1 #2-3",
    "costo_domicilio": 3000, "repartidor_id": 1, "nota": "domicilio prueba",
    "detalle": [{"producto_id": prod, "cantidad": 1}],
})
assert r.status_code == 201, r.text
dom = r.json()
assert abs(dom["total"] - 18000) < 0.01 and dom["estado_domicilio"] == "pendiente", dom
r = C.post(f"/pedidos/{dom['id']}/despachar", headers=H, params={"repartidor_id": 1})
assert r.status_code == 200 and r.json()["estado_domicilio"] == "en_ruta", r.text
r = C.post(f"/pedidos/{dom['id']}/estado-domicilio", headers=H, params={"estado": "entregado"})
assert r.status_code == 200 and r.json()["estado_domicilio"] == "entregado", r.text
r = C.get("/pedidos/domicilios/resumen", headers=H)
assert r.status_code == 200 and r.json()["entregados"] >= 1, r.text
print("pedidos OK: mostrador entregado + domicilio (envío/entrega)")

# ================= RESTAURANTE (408-414) =================
r = C.post("/restaurante/salones", headers=H, json={"nombre": f"Salón {random.randint(10, 99)}"})
assert r.status_code == 201, r.text
salon_id = r.json()["id"]
r = C.post("/restaurante/mesas", headers=H, params={"salon_id": salon_id}, json={"nombre": "M1", "capacidad": 4})
assert r.status_code == 201, r.text
mesa_id = r.json()["id"]
r = C.post(f"/restaurante/mesas/{mesa_id}/ocupar", headers=H, params={"cliente_id": cli["id"], "invitados": 2})
assert r.status_code == 200 and r.json()["estado"] == "ocupada", r.text

r = C.post("/restaurante/comandas", headers=H, json={
    "mesa_id": mesa_id, "cliente_id": cli["id"], "mesero_id": 1,
    "detalle": [
        {"producto_id": prod, "cantidad": 1, "precio": 15000, "preparacion": "término medio"},
        {"producto_id": prod, "cantidad": 2, "precio": 15000, "preparacion": "crudo"},
    ],
})
assert r.status_code == 201, r.text
com = r.json()
assert com["numero"].startswith("CM-") and abs(com["total"] - 45000) < 0.01, com
r = C.post(f"/restaurante/comandas/{com['id']}/agregar", headers=H, json=[{"producto_id": prod, "cantidad": 1, "precio": 15000}])
assert r.status_code == 201 and abs(r.json()["total"] - 60000) < 0.01, r.text
linea_id = r.json()["detalle"][0]["id"]
r = C.post(f"/restaurante/comandas/{com['id']}/lineas/{linea_id}/servir", headers=H)
assert r.status_code == 200 and r.json()["entregado"] is True, r.text
r = C.post(f"/restaurante/comandas/{com['id']}/cerrar", headers=H)
assert r.status_code == 201 and r.json()["estado"] == "cerrada", r.text
r = C.get("/restaurante/mesas", headers=H)
mesa = next(m for m in r.json() if m["id"] == mesa_id)
assert mesa["estado"] == "disponible", mesa

r = C.post("/restaurante/reservas", headers=H, json={
    "mesa_id": mesa_id, "cliente": f"Reserva {random.randint(100, 999)}", "telefono": "3000000",
})
assert r.status_code == 201, r.text
print("restaurante OK: salon/mesa/comanda (servir+cerrar->venta)/reserva")

# ================= SEGURIDAD (348-352, 455-459) =================
r = C.post("/seguridad/permisos/sincronizar", headers=H)
assert r.status_code == 200, r.text
r = C.get("/seguridad/roles", headers=H)
roles = {x["nombre"]: x for x in r.json()}
assert len(roles["Administrador"]["permisos"]) == 26, roles["Administrador"]
assert any(p["modulo"] == "ventas" and p["accion"] == "crear" for p in roles["Cajero"]["permisos"])
assert not any(p["modulo"] == "ventas" and p["accion"] == "anular" for p in roles["Cajero"]["permisos"])
print("roles/permisos OK:", len(roles["Administrador"]["permisos"]), "admin |", len(roles["Cajero"]["permisos"]), "cajero")

# cajero SIN permiso -> 403
r = C.post(f"/ventas/{v['id']}/anular", headers=Hc)
assert r.status_code == 403, r.text
r = C.post("/devoluciones", headers=Hc, json={
    "empresa_id": 1, "sucursal_id": 1, "venta_id": v["id"], "tipo": "total",
    "detalle": [{"producto_id": prod, "cantidad": 1}],
})
assert r.status_code == 403, r.text
print("cajero bloqueado OK (anular/devolucion -> 403)")

# descuento > umbral con cajero -> 403 + autorización pendiente
precio_g = 15000
r = C.post("/ventas", headers=Hc, json={
    "empresa_id": 1, "sucursal_id": 1, "tipo": "contado", "cliente_id": cli["id"],
    "descuento_global": 50000,
    "detalle": [{"producto_id": prod, "cantidad": 4}],
    "pagos": [{"medio": "efectivo", "monto": 60000}],
})
assert r.status_code == 403, r.text
r = C.get("/seguridad/autorizaciones?estado=pendiente", headers=H)
assert any(a["modulo"] == "ventas" and a["accion"] == "descuento" for a in r.json()), r.json()
aut = next(a for a in r.json() if a["modulo"] == "ventas")
r = C.post(f"/seguridad/autorizaciones/{aut['id']}/aprobar", headers=H)
assert r.status_code == 200 and r.json()["estado"] == "aprobada", r.text
print("autorización de descuento OK (403 + solicitud + aprobación)")

# descuento pequeño con cajero -> OK
r = C.post("/ventas", headers=Hc, json={
    "empresa_id": 1, "sucursal_id": 1, "tipo": "contado", "cliente_id": cli["id"],
    "descuento_global": 5000,
    "detalle": [{"producto_id": prod, "cantidad": 1}],
    "pagos": [{"medio": "efectivo", "monto": 10000}],
})
assert r.status_code == 201, r.text
print("descuento bajo con cajero OK")

# admin anula una venta (tiene permiso)
r = C.post(f"/ventas/{v['id']}/anular", headers=H)
assert r.status_code == 200 and r.json()["estado"] == "anulada", r.text
print("anulación admin OK")

print("=== TODOS LOS FLUJOS FASE 5 (FIDELIDAD, APARTADOS, PEDIDOS, RESTAURANTE, SEGURIDAD) OK ===")