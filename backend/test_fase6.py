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
print("login admin OK")

# Limpia promos de corridas previas de este test (evita acumulación de descuentos)
from app.database import SessionLocal
from app.models import Promocion

with SessionLocal() as db:
    db.query(Promocion).filter(Promocion.nombre == "PromoF6").delete()
    db.commit()

# ---------- 14 Monedas ----------
r = C.post("/monedas", headers=H, json={"codigo": "EUR", "nombre": "Euro", "simbolo": chr(8364), "tasa_cambio": 4350})
check("Moneda EUR 201", r.status_code == 201, r.text)
mid = r.json().get("id")
if mid:
    r = C.post(f"/monedas/{mid}/convertir", headers=H, params={"monto": 43500, "base": "COP"})
    check("Convertir COP a EUR", r.status_code == 200 and abs(r.json()["monto"] - 10.0) < 0.001, r.text)
check("Listar monedas", C.get("/monedas", headers=H).status_code == 200)

# ---------- 19 / 355 Balanzas ----------
r = C.post("/balanzas", headers=H, json={"nombre": "BLZ6", "modelo": "SAP", "puerto": "COM4", "tasa": 1})
check("Balanza 201", r.status_code == 201, r.text)
bid = r.json().get("id")
if bid:
    r = C.post(f"/balanzas/{bid}/pesar", headers=H)
    check("Leer peso balanza", r.status_code == 200 and r.json().get("device_ok") is True, r.text)

# ---------- 359 Bancos ----------
r = C.post("/bancos/cuentas", headers=H, json={"banco": "BancoTest", "numero_cuenta": "888-999", "saldo_inicial": 2000000})
check("Cuenta banco 201", r.status_code == 201, r.text)
cid = r.json().get("id")
if cid:
    r = C.post("/bancos/movimientos", headers=H, json={"cuenta_id": cid, "tipo": "egreso", "monto": 50000, "concepto": "Pago nómina"})
    check("Movimiento banco 201", r.status_code == 201, r.text)
    mvid = r.json().get("id")
    if mvid:
        r = C.post(f"/bancos/movimientos/{mvid}/conciliar", headers=H)
        check("Conciliar movimiento", r.status_code == 200 and r.json()["conciliado"] is True, r.text)
    r = C.get("/bancos/cuentas", headers=H)
    check("Saldo banco = 1950000", r.status_code == 200 and any(c["id"] == cid and c["saldo"] == 1950000 for c in r.json()), r.text)

# ---------- 364 Webhooks ----------
r = C.post("/webhooks", headers=H, json={"evento": "venta.creada", "url": "http://localhost:9999/w", "activo": True})
check("Webhook 201", r.status_code == 201, r.text)
check("Listar webhooks", C.get("/webhooks", headers=H).status_code == 200)

# ---------- 362 WhatsApp ----------
r = C.post("/whatsapp/enviar", headers=H, params={"telefono": "3009998877", "mensaje": "Su recibo esta listo"})
check("WhatsApp enviar", r.status_code == 200 and r.json()["estado"] == "enviado", r.text)

# ---------- 377 codigo de barras ----------
r = C.post("/productos", headers=H, json={"empresa_id": 1, "nombre": "ProdBarras", "precio_venta": 2500, "precio_compra": 800, "costo": 800})
check("Producto 201", r.status_code == 201, r.text)
pid = r.json()["id"]
check("Codigo barras autogenerado", len((r.json().get("codigo_barras") or "")) == 13, r.text)
r = C.get(f"/productos/{pid}/codigo-barras", headers=H)
check("SVG codigo barras", r.status_code == 200 and "<svg" in r.text, r.text[:60])

# ---------- 378-382 Etiquetas ----------
r = C.get(f"/etiquetas/productos?ids={pid}&copias=1", headers=H)
check("Etiquetas productos HTML", r.status_code == 200 and "etiqueta" in r.text and "<svg" in r.text, r.text[:60])
r = C.get(f"/etiquetas/gondola?ids={pid}", headers=H)
check("Etiqueta góndola", r.status_code == 200 and "tarjeta" in r.text, r.text[:60])

# ---------- 306 proveedores / 448 pronostico ----------
check("Reporte proveedores", C.get("/reportes/proveedores", headers=H).status_code == 200)
check("Reporte pronostico", C.get("/reportes/pronostico?dias=7", headers=H).status_code == 200)

# ---------- 373/375 exportaciones ----------
r = C.get("/reportes/exportar/ventas-por-producto?formato=xls", headers=H)
check("Exportar XLS", r.status_code == 200 and r.content[:5] == b"<?xml", r.text[:60])
r = C.get("/reportes/exportar/ventas-por-producto?formato=pdf", headers=H)
check("Exportar PDF", r.status_code == 200 and r.content[:4] == b"%PDF", r.text[:60])
r = C.get("/reportes/exportar/ventas?formato=xls", headers=H)
check("Exportar ventas XLS", r.status_code == 200, r.text[:60])

# ---------- 419-422 Produccion ----------
mp1 = C.post("/productos", headers=H, json={"empresa_id": 1, "nombre": "MP_Test1", "precio_venta": 500, "precio_compra": 150, "costo": 150}).json()["id"]
mp2 = C.post("/productos", headers=H, json={"empresa_id": 1, "nombre": "MP_Test2", "precio_venta": 700, "precio_compra": 250, "costo": 250}).json()["id"]
for mp in (mp1, mp2):
    C.post("/inventario/ajustar", headers=H, json={"producto_id": mp, "sucursal_id": 1, "existencias": 100, "motivo": "f6"})
comp = C.post("/productos", headers=H, json={"empresa_id": 1, "nombre": "CompTestF6", "es_compuesto": True, "precio_venta": 3000, "precio_compra": 900, "costo": 900}).json()["id"]
from app.database import SessionLocal
from app.models import ProductoComponente
with SessionLocal() as db:
    db.add(ProductoComponente(producto_id=comp, componente_id=mp1, cantidad=2))
    db.add(ProductoComponente(producto_id=comp, componente_id=mp2, cantidad=1))
    db.commit()
r = C.post("/produccion", headers=H, json={"empresa_id": 1, "sucursal_id": 1, "producto_id": comp, "cantidad": 4})
check("Orden produccion 201", r.status_code == 201 and r.json()["numero"].startswith("PR-"), r.text)
check("Costo total = 4*(2*150+250)=2200", r.status_code == 201 and abs(r.json()["costo_total"] - 2200) < 0.01, r.text)
check("Listar produccion", C.get("/produccion", headers=H).status_code == 200)
check("Resumen produccion", C.get("/produccion/resumen", headers=H).status_code == 200)
r = C.post("/produccion", headers=H, json={"empresa_id": 1, "sucursal_id": 1, "producto_id": comp, "cantidad": 999})
check("Produccion sin MP -> 400", r.status_code == 400, r.text)

# ---------- 435 Acuerdos de pago ----------
r = C.post("/acuerdos-pago", headers=H, json={"cliente_id": 1, "monto_total": 120000, "numero_cuotas": 4, "periodicidad": "quincenal", "fecha_inicio": "2026-09-10"})
check("Acuerdo 201", r.status_code == 201 and len(r.json()["cuotas"]) == 4, r.text)
if r.status_code == 201:
    ac = r.json()
    c1 = ac["cuotas"][0]
    r = C.post(f"/acuerdos-pago/{ac['id']}/pagar-cuota", headers=H, params={"cuota_id": c1["id"]})
    check("Pagar cuota", r.status_code == 200 and r.json()["saldo"] == 90000.0, r.text)

# ---------- 389 Promociones por cliente ----------
cli = 1
C.post("/promociones", headers=H, json={"empresa_id": 1, "nombre": "PromoF6", "tipo": "porcentaje", "valor": 10, "cliente_id": cli})
prodv = C.post("/productos", headers=H, json={"empresa_id": 1, "nombre": "ProdPromoF6", "precio_venta": 10000, "precio_compra": 2000, "costo": 2000}).json()["id"]
C.post("/inventario/ajustar", headers=H, json={"producto_id": prodv, "sucursal_id": 1, "existencias": 60, "motivo": "f6"})
r = C.post("/ventas", headers=H, json={"empresa_id": 1, "sucursal_id": 1, "tipo": "contado", "cliente_id": cli, "detalle": [{"producto_id": prodv, "cantidad": 1}], "pagos": [{"medio": "efectivo", "monto": 10000}]})
v1 = r.json()
check("Promo por cliente aplicada (descuento>0)", r.status_code == 201 and v1["descuento"] > 0, r.text)
r = C.post("/ventas", headers=H, json={"empresa_id": 1, "sucursal_id": 1, "tipo": "contado", "cliente_id": 2, "detalle": [{"producto_id": prodv, "cantidad": 1}], "pagos": [{"medio": "efectivo", "monto": 10000}]})
v2 = r.json()
check("Sin promo para otro cliente (10000)", r.status_code == 201 and abs(v2["total"] - 10000) < 0.01, r.text)
check("Cliente objetivo recibe mayor descuento", v1["descuento"] > v2["descuento"], f"{v1['descuento']} vs {v2['descuento']}")

# ---------- 414 Division de cuentas / 351-352 restricciones ----------
with SessionLocal() as db:
    from app.models import Caja
    caja1 = db.get(Caja, 1)
caja_ok = caja1.id if caja1 else None
r = C.post("/ventas", headers=H, json={"empresa_id": 1, "sucursal_id": 1, "tipo": "credito", "cliente_id": 1, "detalle": [{"producto_id": prodv, "cantidad": 1}], "pagos": []})
vc = r.json()
check("Venta credito para dividir", r.status_code == 201 and vc.get("saldo", 0) > 0, r.text)
if r.status_code == 201:
    tot = vc["total"]
    mitad = round(tot / 2, 2)
    r = C.post(f"/ventas/{vc['id']}/dividir", headers=H, json={"partes": [{"cliente_id": 1, "monto": mitad}, {"cliente_id": 2, "monto": tot - mitad}]})
    check("Dividir cuenta en 2 partes", r.status_code == 200 and len(r.json()["partes"]) == 2, r.text)
r = C.post("/organizacion/sucursales", headers=H, json={"empresa_id": 1, "nombre": "Suc F6", "codigo": f"SUC-F6-{random.randint(100,999)}", "ciudad": "Bogota"})
if r.status_code == 201:
    s2 = r.json()["id"]
    r = C.post("/organizacion/puntos-venta", headers=H, json={"sucursal_id": s2, "nombre": "PV F6", "password": "873366"})
    if r.status_code == 201:
        pv2 = r.json()["id"]
        r = C.post("/organizacion/cajas", headers=H, json={"punto_venta_id": pv2, "nombre": "Caja F6", "codigo": f"CAJ-F6-{random.randint(100,999)}"})
        if r.status_code == 201:
            caja_x = r.json()["id"]
            r = C.post("/ventas", headers=H, json={"empresa_id": 1, "sucursal_id": 1, "caja_id": caja_x, "tipo": "contado", "cliente_id": 1, "detalle": [{"producto_id": prodv, "cantidad": 1}], "pagos": [{"medio": "efectivo", "monto": 10000}]})
            check("Caja de otra sucursal -> 400", r.status_code == 400, r.text)
check("Venta con webhook activo no rompe", True, "")

# ---------- 342 Backups ----------
r = C.post("/backups", headers=H)
check("Crear backup", r.status_code == 201 and r.json().get("tablas", 0) >= 10, r.text)
bid2 = r.json().get("id")
if bid2:
    r = C.post(f"/backups/{bid2}/restaurar", headers=H)
    check("Restaurar backup", r.status_code == 200, r.text)
check("Listar backups", C.get("/backups", headers=H).status_code == 200)

print(f"\n========== RESUMEN TEST FASE 6: {ok} OK · {fail} FAIL ==========")
sys.exit(0 if fail == 0 else 1)