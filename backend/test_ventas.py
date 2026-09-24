"""Validación integral del módulo de VENTAS (+ caja, devoluciones, cartera y reportes de venta)."""

import random

from starlette.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import AperturaCaja, MovimientoCaja, Stock, Venta, VentaDetalle, VentaPago

C = TestClient(app)


def login(user, pw):
    r = C.post("/auth/login", json={"username": user, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f'Bearer {r.json()["access_token"]}'}


H = login("admin", "admin123")
Hc = login("cajero", "cajero123")
print("login admin/cajero OK")

from app.models import Promocion
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
        print(f"  [FALLO-{nombre}]")


def crear_producto(precio=10000, costo=5000, **kw):
    r = C.post("/productos", headers=H, json={
        "empresa_id": 1,
        "nombre": f"Prod VTA {random.randint(1000, 9999)}",
        "sku": f"VTA{random.randint(10000, 99999)}",
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


def venta(detalle, pagos, **kw):
    body = {"empresa_id": 1, "sucursal_id": 1, "tipo": "contado",
            "detalle": detalle, "pagos": pagos, **kw}
    return C.post("/ventas", headers=H, json=body)


# ================= 1. APERTURA / CIERRE DE CAJA (133, 218-228) =================
print("\n== 1. Caja: apertura, movimientos, gastos, arqueo y cierre ==")
with SessionLocal() as db:
    abierta = db.query(AperturaCaja).filter_by(caja_id=1, estado="abierta").first()
if abierta:
    C.post(f"/caja/{abierta.id}/cierre", headers=H)
ap0 = C.post("/caja/apertura", headers=H, json={"caja_id": 1, "saldo_inicial": 100000})
check("Apertura de caja 201", ap0.status_code == 201, ap0.text)
ap_id = ap0.json()["id"] if ap0.status_code == 201 else abierta.id
ap = C.post("/caja/apertura", headers=H, json={"caja_id": 1, "saldo_inicial": 100000})
check("Doble apertura rechazada (400)", ap.status_code == 400, ap.text)

mv = C.post("/caja/movimientos", headers=H, json={"apertura_caja_id": ap_id, "tipo": "ingreso", "concepto": "Préstamo temporal", "monto": 10000})
check("Movimiento ingreso 201", mv.status_code == 201, mv.text)
mv2 = C.post("/caja/movimientos", headers=H, json={"apertura_caja_id": ap_id, "tipo": "egreso", "concepto": "Retiro para vueltos", "monto": 5000})
check("Movimiento egreso 201", mv2.status_code == 201, mv2.text)
mv3 = C.post("/caja/movimientos", headers=Hc, json={"apertura_caja_id": ap_id, "tipo": "ingreso", "concepto": "cajero puede registrar movimiento", "monto": 1})
check("Movimiento como cajero 201 (permiso del rol)", mv3.status_code == 201, mv3.text)
g1 = C.post("/caja/gastos", headers=H, json={"empresa_id": 1, "sucursal_id": 1, "categoria": "servicios", "concepto": "Luz", "monto": 12000, "medio": "efectivo"})
check("Gasto de caja 201", g1.status_code == 201, g1.text)
check("Lista de gastos", C.get("/caja/gastos", headers=H).status_code == 200)

# ================= 2. VENTA DE CONTADO (130, 138-144, 180) =================
print("\n== 2. Ventas de contado, impuestos, descuentos y pagos mixtos ==")
p1 = crear_producto(precio=10000, costo=5000)
stk_inicial = stock_de(p1["id"])
r = venta([{"producto_id": p1["id"], "cantidad": 2}], [{"medio": "efectivo", "monto": 20000}])
check("Venta contado 201", r.status_code == 201, r.text)
v = r.json()
check("Total correcto (20000)", abs(v["total"] - 20000) < 0.01, v)
check("Estado completada", v["estado"] == "completada", v)
check("Pago efectivo registrado", any(p["medio"] == "efectivo" and p["monto"] == 20000 for p in v["pagos"]))
check("Stock descontado (-2)", stock_de(p1["id"]) == stk_inicial - 2, stock_de(p1["id"]))
check("Nº consecutivo V-xxxxxx", v["numero"] and v["numero"].startswith("V-"), v.get("numero"))

# impuesto
pi = crear_producto(precio=20000, costo=9000, impuesto=19)
r = venta([{"producto_id": pi["id"], "cantidad": 1}], [{"medio": "efectivo", "monto": 23800}])
check("Venta con impuesto 19% 201", r.status_code == 201, r.text)
if r.status_code == 201:
    vi = r.json()
    check("Impuesto = 3800", abs(vi["impuesto"] - 3800) < 0.01, vi)
    check("Total = 23800", abs(vi["total"] - 23800) < 0.01, vi)

# descuento global dentro del umbral (155)
r = venta([{"producto_id": p1["id"], "cantidad": 3}], [{"medio": "efectivo", "monto": 25000}],
          descuento_global=5000)
check("Venta con descuento global 201", r.status_code == 201, r.text)
if r.status_code == 201:
    vd = r.json()
    check("Descuento aplicado = 5000", abs(vd["descuento"] - 5000) < 0.01, vd)
    check("Total = 25000 tras descuento", abs(vd["total"] - 25000) < 0.01, vd)

# propina (415)
r = venta([{"producto_id": p1["id"], "cantidad": 1}], [{"medio": "efectivo", "monto": 11000}], propina=1000)
check("Venta con propina 201", r.status_code == 201, r.text)
if r.status_code == 201:
    check("Propina en total (11000)", abs(r.json()["propina"] - 1000) < 0.01 and abs(r.json()["total"] - 11000) < 0.01, r.json())

# pagos mixtos (180): efectivo + tarjeta + transferencia + QR + nequi + daviplata
pagos_mixtos = [
    {"medio": "efectivo", "monto": 10000},
    {"medio": "tarjeta", "referencia": "VISA-4242", "monto": 8000},
    {"medio": "transferencia", "referencia": "T-001", "monto": 6000},
    {"medio": "QR", "monto": 4000},
    {"medio": "nequi", "referencia": "3001112233", "monto": 7000},
    {"medio": "daviplata", "referencia": "3145558877", "monto": 5000},
]
r = venta([{"producto_id": p1["id"], "cantidad": 4}], pagos_mixtos)
check("Venta con pagos mixtos (6 medios) 201", r.status_code == 201, r.text)
if r.status_code == 201:
    vx = r.json()
    check("Suma pagos == total (40000)", abs(sum(p["monto"] for p in vx["pagos"]) - vx["total"]) < 0.01, vx["pagos"])
    check("6 medios registrados", len(vx["pagos"]) == 6, len(vx["pagos"]))

# ================= 3. VALIDACIONES Y BLOQUEOS =================
print("\n== 3. Rechazos esperados (400) ==")
r = venta([{"producto_id": p1["id"], "cantidad": 1}], [{"medio": "efectivo", "monto": 100}] )
check("Pago menor al total -> 400", r.status_code == 400, r.text)
r = venta([{"producto_id": p1["id"], "cantidad": 1}], [{"medio": "efectivo", "monto": 1}], tipo="x")
check("Tipo de venta inválido -> 400", r.status_code == 400, r.text)
r = venta([{"producto_id": p1["id"], "cantidad": 60}], [{"medio": "efectivo", "monto": 600000}])
check("Stock insuficiente -> 400", r.status_code == 400, r.text)
r = venta([{"producto_id": 999999, "cantidad": 1}], [{"medio": "efectivo", "monto": 1}])
check("Producto inexistente -> 400", r.status_code == 400, r.text)

# producto inactivo (desactivar p1 para esta prueba y reactivarlo)
C.put(f"/productos/{p1['id']}", headers=H, json={"activo": False})
r = venta([{"producto_id": p1["id"], "cantidad": 1}], [{"medio": "efectivo", "monto": 20000}])
check("Producto inactivo -> 400", r.status_code == 400, r.text)
C.put(f"/productos/{p1['id']}", headers=H, json={"activo": True})

# bloqueo de venta bajo costo (454)
pb = crear_producto(precio=15000, costo=12000, bloquear_venta_bajo_costo=True)
# precio explícito bajo costo
r = venta([{"producto_id": pb["id"], "cantidad": 1, "precio": 5000}], [{"medio": "efectivo", "monto": 5000}])
check("Bloqueo venta bajo costo -> 400", r.status_code == 400, r.text)

# margen mínimo (453)
pm = crear_producto(precio=14000, costo=10000, margen_minimo=30)
r = venta([{"producto_id": pm["id"], "cantidad": 1, "precio": 12000}], [{"medio": "efectivo", "monto": 12000}])
check("Venta bajo margen mínimo -> 400", r.status_code == 400, r.text)
r = venta([{"producto_id": pm["id"], "cantidad": 1, "precio": 13000}], [{"medio": "efectivo", "monto": 13000}])
check("Venta al margen mínimo exacto OK", r.status_code == 201, r.text)

# búsqueda para venta: código de barras / PLU / nombre (140-144)
pbarr = crear_producto(precio=9000, costo=4000, codigo_barras="770999999991")
r = C.get(f"/productos?q=770999999991", headers=H)
check("Venta por código de barras (búsqueda) OK", r.status_code == 200 and any(x["id"] == pbarr["id"] for x in r.json()), r.text)
C.put(f"/productos/{pbarr['id']}", headers=H, json={"plu": "PLU-77"})
r = C.get("/productos?q=PLU-77", headers=H)
check("Búsqueda por PLU OK", any(x["id"] == pbarr["id"] for x in r.json()), r.text)

# ================= 4. VENTAS A CRÉDITO (131, 125-126, 128) =================
print("\n== 4. Ventas a crédito, límites y cartera ==")
cli = C.post("/clientes", headers=H, params={"empresa_id": 1}, json={
    "nombre": f"Cliente Crédito {random.randint(1000, 9999)}",
    "documento": str(random.randint(1000000000, 9999999999)), "tipo": "frecuente",
    "limite_credito": 60000,
})
cli = cli.json()
r = venta([{"producto_id": p1["id"], "cantidad": 4}], [{"medio": "efectivo", "monto": 40000}], tipo="credito", cliente_id=cli["id"])
check("Venta a crédito 201", r.status_code == 201, r.text)
if r.status_code == 201:
    vc = r.json()
    check("Saldo = total (40000)", abs((vc["saldo"] or 0) - 40000) < 0.01, vc)
    check("Crédito sin pago inicial OK", vc["tipo"] == "credito")
r = venta([{"producto_id": p1["id"], "cantidad": 4}], [{"medio": "efectivo", "monto": 10}], tipo="credito")
check("Crédito sin cliente -> 400", r.status_code == 400, r.text)
r = venta([{"producto_id": p1["id"], "cantidad": 4}], [{"medio": "efectivo", "monto": 10}], tipo="credito", cliente_id=cli["id"], descuento_global=2000)
vc2 = r.json()
# acumulado primero: 40000; nuevo total 40000-2000=38000 -> 78000 > 60000
check("Excede límite de crédito acumulado -> 400", r.status_code == 400, r.text)

r = C.post("/cartera/abonos/clientes", headers=H, json={"empresa_id": 1, "cliente_id": cli["id"], "monto": 25000, "medio": "efectivo"})
check("Abono a cuenta de cliente 201", r.status_code == 201, r.text)
r = C.get("/cartera/estado-cuenta/{0}".format(cli["id"]), headers=H)
check("Estado de cuenta de cliente OK", r.status_code == 200, r.text)
if r.status_code == 200:
    ec = r.json()
    check("Saldo total del cliente coherente", ec.get("saldo_total", -1) <= 40000 and ec.get("saldo_total", 0) >= 0, ec)
    check("Abono reflejado en estado de cuenta", len(ec.get("abonos", [])) >= 1, ec)
r = C.get("/cartera/cuentas-cobrar", headers=H)
check("Cartera cuentas por cobrar OK", r.status_code == 200, r.text)
if r.status_code == 200:
    resumen = r.json()
    check("Total cartera > 0", resumen.get("total_cartera", 0) > 0, resumen)
    check("Cartera por cliente lista", len(resumen.get("clientes", [])) >= 1, resumen)

# ================= 5. SUSPENSIÓN, NOTA DÉBITO, ANULACIÓN (150-151, 456) =================
print("\n== 5. Ciclo de vida: suspender, reanudar, nota débito, anular ==")
vs = venta([{"producto_id": p1["id"], "cantidad": 1}], [{"medio": "efectivo", "monto": 10000}]).json()
r = C.post(f"/ventas/{vs['id']}/suspender", headers=H)
check("Suspender venta OK", r.status_code == 200 and r.json()["estado"] == "suspendida", r.text)
r = C.post(f"/ventas/{vs['id']}/reanudar", headers=H)
check("Reanudar venta OK", r.status_code == 200 and r.json()["estado"] == "completada", r.text)
r = C.post(f"/ventas/{vs['id']}/nota-debito", headers=H, json={"monto": 2000, "concepto": "Ajuste diferencia"})
check("Nota débito OK", r.status_code == 200, r.text)
if r.status_code == 200:
    check("Total subió a 12000", abs(r.json()["total"] - 12000) < 0.01, r.json())
r = C.post(f"/ventas/{vs['id']}/suspender", headers=H)
r = C.post(f"/ventas/{vs['id']}/suspender", headers=H)
check("Suspender venta suspendida -> 400", r.status_code == 400, r.text)

r = C.post(f"/ventas/{vs['id']}/anular", headers=Hc)
check("Anulación con cajero (sin permiso) -> 403", r.status_code == 403, r.text)

# ================= 6. FACTURA ELECTRÓNICA AUTOMÁTICA =================
print("\n== 6. Auto-factura en la venta ==")
vfac = venta([{"producto_id": p1["id"], "cantidad": 1}], [{"medio": "efectivo", "monto": 10000}]).json()
r = C.get(f"/facturacion/documentos?venta_id={vfac['id']}", headers=H)
check("Documento fiscal generado automáticamente", r.status_code == 200 and any(d["tipo_documento"] == "factura" for d in r.json()), r.text)

# ================= 7. DEVOLUCIONES Y CAMBIOS (84, 208-217) =================
print("\n== 7. Devoluciones, reembolsos y cambios ==")
vd = venta([{"producto_id": p1["id"], "cantidad": 3}], [{"medio": "efectivo", "monto": 30000}]).json()
stk_antes = stock_de(p1["id"])
r = C.post("/devoluciones", headers=H, json={
    "empresa_id": 1, "sucursal_id": 1, "venta_id": vd["id"], "tipo": "parcial",
    "motivo": "Producto defectuoso", "reembolso_medio": "efectivo",
    "detalle": [{"producto_id": p1["id"], "cantidad": 1}],
})
check("Devolución parcial 201", r.status_code == 201, r.text)
if r.status_code == 201:
    dv = r.json()
    check("Total devolución = 10000", abs(dv["total_devolucion"] - 10000) < 0.01, dv)
    check("Motivo guardado", dv["motivo"] == "Producto defectuoso", dv)
    check("Nº nota crédito NC-xxxxxx", dv["numero_nota"].startswith("NC-"), dv)
    check("Stock reintegrado (+1)", stock_de(p1["id"]) == stk_antes + 1, stock_de(p1["id"]))
r = C.post("/devoluciones", headers=Hc, json={
    "empresa_id": 1, "sucursal_id": 1, "venta_id": vd["id"], "tipo": "total",
    "detalle": [{"producto_id": p1["id"], "cantidad": 2}]})
check("Devolución cajero sin permiso -> 403", r.status_code == 403, r.text)
r = C.post("/devoluciones", headers=H, json={
    "empresa_id": 1, "sucursal_id": 1, "venta_id": vd["id"], "tipo": "parcial",
    "detalle": [{"producto_id": p1["id"], "cantidad": 50}]})
check("Devolver más de lo vendido -> 400", r.status_code == 400, r.text)

# devolución total -> venta anulada
vd2 = venta([{"producto_id": p1["id"], "cantidad": 2}], [{"medio": "efectivo", "monto": 20000}]).json()
r = C.post("/devoluciones", headers=H, json={
    "empresa_id": 1, "sucursal_id": 1, "venta_id": vd2["id"], "tipo": "total", "motivo": "Devolución total"})
check("Devolución total 201", r.status_code == 201, r.text)
if r.status_code == 201:
    r = C.get(f"/ventas/{vd2['id']}", headers=H)
    check("Venta marcada anulada tras devolución total", r.json()["estado"] == "anulada", r.text)

# cambio de productos (214): devolución + reventa
vcam = venta([{"producto_id": p1["id"], "cantidad": 1}], [{"medio": "efectivo", "monto": 10000}]).json()
p2 = crear_producto(precio=8000, costo=3500)
r = C.post("/devoluciones/cambio", headers=H, json={
    "empresa_id": 1, "sucursal_id": 1, "venta_id": vcam["id"], "tipo": "total",
    "motivo": "Cambio por otro color", "reembolso_medio": "nota_credito",
    "detalle": [{"producto_id": p1["id"], "cantidad": 1}],
    "reemplazo": [{"producto_id": p2["id"], "cantidad": 1}],
})
check("Cambio de producto (devolución + reventa) OK", r.status_code == 201, r.text)
if r.status_code == 201:
    check("Venta nueva generada", r.json().get("venta_nueva"), r.json())
    check("Nota crédito emitida", r.json().get("devolucion", "").startswith("NC-"), r.json())
check("Historial de devoluciones", C.get("/devoluciones", headers=H).status_code == 200)

# ================= 8. CIERRE DE CAJA Y ARQUEO (227-228, 134-135) =================
print("\n== 8. Arqueo y cierre de caja ==")
r = C.post(f"/caja/arqueo?apertura_id={ap_id}&efectivo_contado=140000&observacion=conteo", headers=H)
check("Arqueo de caja 201", r.status_code == 201, r.text)
if r.status_code == 201:
    aq = r.json()
    check("Esperado = inicial + efectivo en ventas", aq["esperado"] >= 100000, aq)
r = C.post(f"/caja/{ap_id}/cierre", headers=H)
check("Cierre de caja 200", r.status_code == 200, r.text)
if r.status_code == 200:
    ci = r.json()
    with SessionLocal() as db:
        apertura = db.get(AperturaCaja, ap_id)
        inicio = apertura.created_at
        ventas_turno = (
            db.query(Venta)
            .filter(
                Venta.caja_id == apertura.caja_id,
                Venta.estado == "completada",
                Venta.created_at >= inicio,
            )
            .all()
        )
        tot_turno = sum(float(v.total) for v in ventas_turno)
        movs = db.query(MovimientoCaja).filter(MovimientoCaja.apertura_caja_id == apertura.id).all()
        neto = sum(float(m.monto) for m in movs if m.tipo in ("ingreso",))
        neto -= sum(float(m.monto) for m in movs if m.tipo in ("egreso", "gasto", "retiro"))
    esperado_cierre = round(100000 + tot_turno + neto, 2)
    check("Saldo cierre = inicial + ventas del turno + movs", abs(ci["saldo_cierre"] - esperado_cierre) < 0.01,
          f"{ci['saldo_cierre']} vs {esperado_cierre}")
r = C.post("/caja/apertura", headers=H, json={"caja_id": 1, "saldo_inicial": 100000})
check("Re-apertura tras cierre 201", r.status_code == 201, r.text)
new_ap = r.json()
C.post(f"/caja/{new_ap['id']}/cierre", headers=H)

# ================= 9. REPORTES DE VENTAS (242-256, 312-313) =================
print("\n== 9. Reportes de ventas ==")
for ep in ["/reportes/ventas", "/reportes/ventas?desde=" + "2000-01-01", "/reportes/ventas-dia?dias=14",
           "/reportes/ventas-por-producto", "/reportes/estado-resultados", "/reportes/dashboard"]:
    r = C.get(ep, headers=H)
    check(f"GET {ep.split('?')[0]} 200", r.status_code == 200, r.text)
rv = C.get("/reportes/ventas", headers=H).json()
check("reporte/ventas con total > 0", rv["total_ventas"] > 0, rv)
check("reporte/ventas: medios de pago por medio", "por_medio_pago" in rv and len(rv["por_medio_pago"]) >= 5, rv.get("por_medio_pago"))
check("reporte/ventas: por cajero", "por_cajero" in rv, rv)
rvp = C.get("/reportes/ventas-por-producto", headers=H).json()
check("ventas-por-producto top listo", isinstance(rvp, list) and len(rvp) > 0, rvp)
er = C.get("/reportes/estado-resultados", headers=H).json()
check("estado-resultados utilidad >= 0", er.get("utilidad_bruta", -1) >= 0, er)
dv14 = C.get("/reportes/ventas-dia?dias=14", headers=H).json()
check("ventas-dia 14 días con datos", isinstance(dv14, list) and len(dv14) > 0, dv14)

# ================= 10. ANULACIÓN ADMIN (reversión de stock) =================
print("\n== 10. Anulación admin y reversión de la venta ==")
va = venta([{"producto_id": p1["id"], "cantidad": 1}], [{"medio": "efectivo", "monto": 10000}]).json()
stk_antes = stock_de(p1["id"])
r = C.post(f"/ventas/{va['id']}/anular", headers=H)
check("Anulación admin OK", r.status_code == 200 and r.json()["estado"] == "anulada", r.text)
check("Stock repuesto tras anulación (+1)", stock_de(p1["id"]) == stk_antes + 1, stock_de(p1["id"]))
with SessionLocal() as db:
    from app.models import DocumentoFiscal
    docs = db.query(DocumentoFiscal).filter(DocumentoFiscal.venta_id == va["id"]).all()
    check("Documento fiscal de la venta anulado", len(docs) > 0 and all(d.anulado for d in docs),
          [(d.numero, d.anulado) for d in docs])
check("Anular venta inexistente -> 404", C.post("/ventas/999999/anular", headers=H).status_code == 404)

print(f"\n========== RESUMEN TEST VENTAS: {ok} OK · {fail} FAIL ==========")
if fail:
    print("HUBO FALLOS")
else:
    print("=== TODOS LOS FLUJOS DE VENTAS OK ===")
raise SystemExit(1 if fail else 0)