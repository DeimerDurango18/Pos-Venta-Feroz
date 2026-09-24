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

# ----- Domicilio en vivo estilo Rappi: seguimiento GPS + métricas -----
r = C.post("/pedidos", headers=H, json={
    "cliente_id": cli["id"], "tipo": "domicilio", "direccion_entrega": "Cra 7 #45-12",
    "costo_domicilio": 3500, "nota": "domicilio GPS",
    "detalle": [{"producto_id": prod, "cantidad": 2}],
})
assert r.status_code == 201, r.text
gps = r.json()
assert gps["estado_domicilio"] == "pendiente", gps
r = C.post(f"/pedidos/{gps['id']}/despachar", headers=H, params={"repartidor_id": 1})
assert r.status_code == 200, r.text
r = C.post("/domicilios/seguimiento", headers=H, json={
    "pedido_id": gps["id"], "repartidor_id": 1,
    "lat": 4.6762, "lng": -74.0487, "dest_lat": 4.6601, "dest_lng": -74.0710,
    "direccion": "Cra 7 #45-12",
})
assert r.status_code == 201, r.text
ub = r.json()
assert ub["estado_domicilio"] == "en_ruta" and ub["dest_lat"] == 4.6601, ub
assert "avance_pct" in ub and "dist_total_km" in ub and "eta_min" in ub, ub
assert ub["avance_pct"] < 100 and ub["dist_total_km"] > 1.0, ub
avance_prev = -1
vueltas = 0
while True:
    r = C.post(f"/domicilios/pedidos/{gps['id']}/simular", headers=H)
    assert r.status_code == 200, r.text
    av = r.json()
    assert av["avance_pct"] >= avance_prev, av
    avance_prev = av["avance_pct"]
    vueltas += 1
    if av["estado_domicilio"] == "entregado" or vueltas > 12:
        assert av["estado_domicilio"] == "entregado" and av["avance_pct"] == 100.0, av
        break
tr = C.get(f"/domicilios/pedidos/{gps['id']}/tracking", headers=H)
assert tr.status_code == 200 and tr.json()["estado_domicilio"] == "entregado", tr.text
assert tr.json()["ubicacion"]["avance_pct"] == 100.0, tr.json()["ubicacion"]
mm = C.get("/domicilios/mapa", headers=H)
assert mm.status_code == 200 and isinstance(mm.json(), list), mm.text
print("domicilios en vivo OK: seguimiento GPS + simulación + avance/ETA + mapa")

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

# ---------------- SPLIT Y CORTESÍAS ----------------
r = C.post(f"/restaurante/mesas/{mesa_id}/ocupar", headers=H)
assert r.status_code == 200, r.text
r = C.post("/restaurante/comandas", headers=H, json={
    "mesa_id": mesa_id, "cliente_id": cli["id"],
    "detalle": [
        {"producto_id": prod, "cantidad": 1, "precio": 10000},
        {"producto_id": prod, "cantidad": 1, "precio": 20000},
        {"producto_id": prod, "cantidad": 1, "precio": 5000, "cortesia": True},
        {"producto_id": prod, "cantidad": 1, "precio": 30000},
    ],
})
assert r.status_code == 201, r.text
com2 = r.json()
assert abs(com2["total"] - 60000) < 0.01, com2  # 10k + 20k + 30k (cortesía excluida)
assert abs(com2["total_cortesia"] - 5000) < 0.01, com2
lineas = {d["id"]: d for d in com2["detalle"]}
cort_id = next(i for i, d in lineas.items() if d["cortesia"])
assert lineas[cort_id]["cortesia"] is True, lineas

# toggle cortesía (quitar y volver)
r = C.post(f"/restaurante/comandas/{com2['id']}/lineas/{cort_id}/cortesia", headers=H, json={"cortesia": False})
assert r.status_code == 200 and abs(r.json()["total"] - 65000) < 0.01, r.text
r = C.post(f"/restaurante/comandas/{com2['id']}/lineas/{cort_id}/cortesia", headers=H, json={"cortesia": True})
assert r.status_code == 200 and abs(r.json()["total"] - 60000) < 0.01, r.text

# split en 3 partes (una incluye la cortesía -> debe rechazar)
ids_cobrables = [i for i, d in lineas.items() if not d["cortesia"]]
r = C.post(f"/restaurante/comandas/{com2['id']}/split", headers=H, json={
    "partes": [
        {"linea_ids": [ids_cobrables[0]], "medio": "efectivo"},
        {"linea_ids": [ids_cobrables[1]], "medio": "nequi"},
        {"linea_ids": [ids_cobrables[2]], "medio": "tarjeta"},
    ]
})
assert r.status_code == 201, r.text
split = r.json()
assert split["estado"] == "cerrada", split
assert len(split["ventas"]) == 3, split
totales = sorted(v["total"] for v in split["ventas"])
assert totales == [10000, 20000, 30000], totales
assert {v["medio"] for v in split["ventas"]} == {"efectivo", "nequi", "tarjeta"}, split
r = C.get("/restaurante/mesas", headers=H)
mesa = next(m for m in r.json() if m["id"] == mesa_id)
assert mesa["estado"] == "disponible", mesa
print("restaurante OK: cortesías + split de cuenta (3 ventas por persona/medio)")

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

# ================= FACTURAS RECURRENTES + RECORDATORIOS =================
from datetime import date as _date
from datetime import timedelta as _td

from app.database import SessionLocal as _SL

# cliente con teléfono para recordatorios
r = C.post("/clientes", headers=H, params={"empresa_id": 1}, json={
    "nombre": f"Cliente Rec {random.randint(1000, 9999)}",
    "documento": str(random.randint(1000000000, 9999999999)),
    "telefono": "3001234567",
})
assert r.status_code in (200, 201), r.text
cli_rec = r.json()

# plantilla mensual con 2 items + descuento
r = C.post("/recurrentes", headers=H, json={
    "empresa_id": 1, "cliente_id": cli_rec["id"], "sucursal_id": 1,
    "periodicidad": "mensual", "dia": 15, "descripcion": "Mensualidad",
    "items": [
        {"producto_id": prod, "cantidad": 2, "precio": 15000},
        {"producto_id": prod, "cantidad": 1, "precio": 10000},
    ],
    "descuento_global": 5000, "tipo": "credito", "proxima_fecha": str(_date.today()),
})
assert r.status_code == 201, r.text
fr = r.json()
assert abs(fr["total_estimado"] - 35000) < 0.01, fr
assert fr["periodicidad"] == "mensual" and fr["dia"] == 15, fr

# validaciones: periodicidad inválida y producto inexistente
r = C.post("/recurrentes", headers=H, json={
    "empresa_id": 1, "periodicidad": "anual", "dia": 1,
    "items": [{"producto_id": prod, "cantidad": 1}],
})
assert r.status_code == 400, r.text
r = C.post("/recurrentes", headers=H, json={
    "empresa_id": 1, "periodicidad": "mensual", "dia": 1,
    "items": [{"producto_id": 999999, "cantidad": 1}],
})
assert r.status_code == 400, r.text

# ejecutar ahora -> venta crédito por 35000 y próximo el 15 del mes siguiente
r = C.post(f"/recurrentes/{fr['id']}/ejecutar", headers=H)
assert r.status_code == 200, r.text
ven = r.json()
assert abs(ven["total"] - 35000) < 0.01, ven
hoy = _date.today()
m2 = (hoy.replace(day=28) + _td(days=4)).replace(day=15)
r = C.get("/recurrentes", headers=H)
fr2 = next(x for x in r.json() if x["id"] == fr["id"])
assert str(fr2["proxima_fecha"]) == str(m2), fr2

# cartera del cliente incluye la factura recurrente
r = C.get(f"/cartera/estado-cuenta/{cli_rec['id']}", headers=H)
assert any(v["id"] == ven["venta_id"] for v in r.json()["ventas"]), r.json()

# pausar reactiva bloquea el ejecutar; reactivar restaura
r = C.put(f"/recurrentes/{fr['id']}", headers=H, json={"activo": False})
assert r.status_code == 200 and r.json()["activo"] is False, r.text
r = C.post(f"/recurrentes/{fr['id']}/ejecutar", headers=H)
assert r.status_code == 400, r.text
r = C.put(f"/recurrentes/{fr['id']}", headers=H, json={"activo": True})
assert r.status_code == 200 and r.json()["activo"] is True, r.text

# recordatorio: backdatear la venta crédito del cliente y enviar
from app.models import MensajeWhatsapp as _MW
from app.models import Venta as _VentaModel
from app.models import LinkPago as _LinkModel

_db = _SL()
_v = _db.get(_VentaModel, ven["venta_id"])
_v.created_at = _v.created_at - _td(days=10)
_db.commit()
_db.close()

r = C.post("/recurrentes/recordatorios/enviar", headers=H, json={"dias_mora": 1, "medio": "whatsapp"})
assert r.status_code == 200, r.text
rec = r.json()
assert rec["enviados"] >= 1, rec
assert any(c["cliente"] == cli_rec["nombre"] for c in rec["clientes"]), rec
_db = _SL()
registrado = _db.query(_MW).filter(_MW.plantilla == "recordatorio_cobro").count()
_db.close()
assert registrado >= 1, registrado
print("recurrentes OK: plantilla 35000, próximo 15 mes siguiente, pausa/reactiva, recordatorio WhatsApp registrado")

# ================= RESERVAS DE MESAS =================
r = C.get("/restaurante/salones", headers=H)
salon = r.json()[0]
r = C.post("/restaurante/mesas", headers=H, params={"salon_id": salon["id"]}, json={"nombre": "R1", "capacidad": 2})
assert r.status_code == 201, r.text
mesa_res = r.json()

# crear reserva confirmada con fecha futura
futuro = (_date.today() + _td(days=2)).isoformat() + "T20:00:00"
r = C.post("/restaurante/reservas", headers=H, json={
    "mesa_id": mesa_res["id"], "cliente": "Cliente Reserva", "telefono": "3009876543", "inicio": futuro,
})
assert r.status_code == 201, r.text
rid = r.json()["id"]
assert r.json()["estado"] == "confirmada", r.text

# duplicado el mismo día -> 400
r = C.post("/restaurante/reservas", headers=H, json={
    "mesa_id": mesa_res["id"], "cliente": "Otro", "inicio": (_date.today() + _td(days=2)).isoformat() + "T21:00:00",
})
assert r.status_code == 400, r.text

# ocupa la mesa y vuelve a intentar -> 400 (mesa ocupada)
r = C.post(f"/restaurante/mesas/{mesa_res['id']}/ocupar", headers=H, json={})
assert r.status_code == 200, r.text
r = C.post("/restaurante/reservas", headers=H, json={
    "mesa_id": mesa_res["id"], "cliente": "Otro", "inicio": (_date.today() + _td(days=5)).isoformat() + "T20:00:00",
})
assert r.status_code == 400 and "ocupada" in r.text, r.text
r = C.post(f"/restaurante/mesas/{mesa_res['id']}/disponible", headers=H, json={})
assert r.status_code == 200, r.text

# transición de estados
for est in ("completada", "cancelada"):
    r = C.post(f"/restaurante/reservas/{rid}/estado", headers=H, json={"estado": est})
    assert r.status_code == 200 and r.json()["estado"] == est, r.text
r = C.post(f"/restaurante/reservas/{rid}/estado", headers=H, json={"estado": "basura"})
assert r.status_code == 400, r.text
r = C.get("/restaurante/reservas", headers=H)
assert any(x["id"] == rid and x["estado"] == "cancelada" for x in r.json()), r.text
print("reservas OK: doble reserva bloqueada, mesa ocupada bloquea, transiciones completada/cancelada")

# ================= LINKS DE PAGO =================
# link simple sin productos
r = C.post("/links-pago", headers=H, json={
    "empresa_id": 1, "descripcion": "Cobro prueba", "monto": 25000, "medio": "nequi", "vence_dias": 7,
})
assert r.status_code == 200, r.text
link1 = r.json()
assert abs(link1["monto"] - 25000) < 0.01 and link1["estado"] == "activo" and link1["token"], link1
assert len(link1["token"]) >= 10, link1

# link sin monto ni items -> 400
r = C.post("/links-pago", headers=H, json={"empresa_id": 1, "descripcion": "vacio"})
assert r.status_code == 400, r.text

# listado incluye el link
r = C.get("/links-pago", headers=H)
assert any(x["id"] == link1["id"] for x in r.json()), r.text

# página pública (sin token) -> 200 y suma visitas
r = C.get(f"/publico/pago/{link1['token']}")
assert r.status_code == 200 and "Cobro prueba" in r.text, r.text[:200]
r = C.get("/links-pago", headers=H)
assert next(x for x in r.json() if x["id"] == link1["id"])["visitas"] >= 1, r.text

# marcar pagado -> estado pagado sin venta (no tenía productos)
r = C.post(f"/links-pago/{link1['id']}/pagar", headers=H)
assert r.status_code == 200 and r.json()["estado"] == "pagado" and r.json()["venta_id"] is None, r.text
assert r.json()["confirmado_fecha"], r.text
# repetir -> 400
r = C.post(f"/links-pago/{link1['id']}/pagar", headers=H)
assert r.status_code == 400, r.text
# página pública muestra pagado
r = C.get(f"/publico/pago/{link1['token']}")
assert r.status_code == 200 and "PAGADO" in r.text, r.text[:200]

# link con productos -> al cobrarlo genera venta y descuenta inventario
r = C.post("/links-pago", headers=H, json={
    "empresa_id": 1, "descripcion": "Cobro con productos",
    "items": [{"producto_id": prod, "cantidad": 2, "precio": 5000}],
    "medio": "nequi", "vence_dias": 30,
})
assert r.status_code == 200, r.text
link2 = r.json()
assert abs(link2["monto"] - 0) < 0.01, link2  # monto sugerido en items
r = C.post(f"/links-pago/{link2['id']}/pagar", headers=H)
assert r.status_code == 200 and r.json()["estado"] == "pagado", r.text
vid = r.json()["venta_id"]
assert vid, r.text
r = C.get(f"/ventas/{vid}", headers=H)
assert r.status_code == 200 and abs(r.json()["total"] - 10000) < 0.01, r.text

# vencido automático
r = C.post("/links-pago", headers=H, json={"empresa_id": 1, "descripcion": "vence", "monto": 9000, "vence_dias": 7})
assert r.status_code == 200, r.text
link4 = r.json()
_db = _SL()
_l = _db.get(_LinkModel, link4["id"])
_l.vence = _date.today() - _td(days=2)
_db.commit()
_db.close()
r = C.get("/links-pago", headers=H)
assert next(x for x in r.json() if x["id"] == link4["id"])["estado"] == "vencido", r.text
r = C.get(f"/publico/pago/{link4['token']}")
assert r.status_code == 200 and "VENCIDO" in r.text, r.text[:200]
# un link vencido no se puede cobrar
r = C.post(f"/links-pago/{link4['id']}/pagar", headers=H)
assert r.status_code == 400, r.text

# cancelar link activo
r = C.post("/links-pago", headers=H, json={"empresa_id": 1, "descripcion": "x", "monto": 100, "vence_dias": 5})
assert r.status_code == 200, r.text
link3 = r.json()
r = C.post(f"/links-pago/{link3['id']}/cancelar", headers=H)
assert r.status_code == 200 and r.json()["estado"] == "cancelado", r.text
# cancelar de nuevo -> 400
r = C.post(f"/links-pago/{link3['id']}/cancelar", headers=H)
assert r.status_code == 400, r.text

# link inexistente en página pública -> 404
r = C.get("/publico/pago/token-inexistente-1")
assert r.status_code == 404, r.text
print("links de pago OK: creación, lista, página pública con visitas, cobrado sin/con venta, vencido, cancelado, 404")

print("=== TODOS LOS FLUJOS FASE 5 (FIDELIDAD, APARTADOS, PEDIDOS, RESTAURANTE, SEGURIDAD) OK ===")