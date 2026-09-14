"""Validación por lotes: items 36-40 (tipos de producto), 105 ordenes compra, 115 gastos compra,
122 direccion cliente, 195-198 DIAN, 202-203 correo/whatsapp, 216 autorizacion devoluciones,
274 vencidos, 343 historial precios/auditoria, 350 restricciones usuario, 376 codigos barras,
449 rotacion, 450 rentabilidad."""
import sys, time
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Categoria, Cliente, Lote, Producto, Stock

C = TestClient(app)


def _login(u="admin", p="admin123"):
    r = C.post("/auth/login", json={"username": u, "password": p})
    assert r.status_code == 200, f"login {u} failed: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


H = _login()
Hc = _login("cajero", "cajero123")


def _r(method, url, h=None, **kw):
    return C.request(method, url, headers=h or H, **kw)


def ok(r, code=200):
    assert r is not None and r.status_code == code, f"expected {code} got {r.status_code}: {r.text if r else 'None'}"
    return r.json()


def setup_module():
    db = SessionLocal()
    cat = db.query(Categoria).filter(Categoria.nombre == "Cat21").first()
    if not cat:
        cat = Categoria(nombre="Cat21", activa=True)
        db.add(cat); db.commit(); db.refresh(cat)
    prod = db.query(Producto).filter(Producto.sku == "P21-TEST").first()
    if not prod:
        prod = Producto(nombre="Prod21", sku="P21-TEST", tipo="unidad", precio_venta=10000,
                        costo=5000, empresa_id=1, categoria_id=cat.id, impuesto=0)
        db.add(prod); db.commit(); db.refresh(prod)
    else:
        prod.precio_venta = 10000
        db.commit()
    if not db.query(Stock).filter(Stock.producto_id == prod.id, Stock.sucursal_id == 1).first():
        db.add(Stock(producto_id=prod.id, sucursal_id=1, existencias=500, disponible=500))
        db.commit()
    if not db.query(Lote).filter(Lote.codigo == "L21-VENC").first():
        db.add(Lote(producto_id=prod.id, codigo="L21-VENC", vencimiento=date.today() - timedelta(days=5), cantidad=10))
        db.commit()
    db.close()


def _producto_id():
    db = SessionLocal()
    p = db.query(Producto).filter(Producto.sku == "P21-TEST").first()
    db.close()
    return p.id


def _crear_venta(cliente_id=None, cantidad=1, precio=None, h=None, sucursal=1, descuento=0):
    det = {"producto_id": _producto_id(), "cantidad": cantidad}
    if precio is not None:
        det["precio"] = precio
    total = (precio if precio is not None else 10000) * cantidad - descuento
    body = {"empresa_id": 1, "sucursal_id": sucursal, "tipo": "contado",
            "detalle": [det],
            "pagos": [{"medio": "efectivo", "monto": total}]}
    if cliente_id:
        body["cliente_id"] = cliente_id
    if descuento:
        body["descuento_global"] = descuento
    return _r("POST", "/ventas", h=h, json=body)


# ---------- 36-40 tipos de producto ----------
def test_36_40_tipos_producto():
    tipos = {"36": "unidad", "37": "volumen", "38": "longitud", "39": "caja", "40": "paquete"}
    for n, t in tipos.items():
        r = ok(_r("POST", "/productos", json={
            "empresa_id": 1, "nombre": f"Prod tipo {t} {n}", "tipo": t, "precio_venta": 1000}), 201)
        pid = r["id"]
        r2 = _r("GET", f"/productos/{pid}")
        assert r2.status_code == 200 and r2.json()["tipo"] == t, f"tipo {t} no persistió"


# ---------- 105 solicitudes de compra ----------
def test_105_ordenes_compra():
    r = ok(_r("POST", "/compras/ordenes", json={
        "empresa_id": 1, "sucursal_id": 1, "proveedor_id": 1,
        "detalle": [{"producto_id": _producto_id(), "cantidad": 2, "costo_unitario": 5000}]}), 201)
    oid = r["id"]
    assert r["estado"] == "solicitada", r
    r = ok(_r("GET", "/compras/ordenes?estado=solicitada"))
    assert any(o["id"] == oid for o in r)
    r = ok(_r("POST", f"/compras/ordenes/{oid}/aprobar"))
    assert r["estado"] == "aprobada"


# ---------- 115 gastos de compra ----------
def test_115_gastos_compra():
    r = ok(_r("POST", "/compras", json={
        "empresa_id": 1, "sucursal_id": 1, "proveedor_id": 1, "tipo": "contado",
        "otros_costos": 1500,
        "detalle": [{"producto_id": _producto_id(), "cantidad": 1, "costo_unitario": 5000}]}), 201)
    assert r["otros_costos"] == 1500, r
    assert r["total"] == 6500, f"total no incluye otros_costos: {r['total']}"


# ---------- 122 direcciones de clientes ----------
def test_122_direccion_cliente():
    r = ok(_r("POST", "/clientes?empresa_id=1", json={
        "nombre": "Cliente Dir 21", "documento": "CLI-21-DIR", "telefono": "3001112233",
        "direccion": "Calle 21 #5-10", "ciudad": "Bogota"}), 201)
    cid = r["id"]
    assert r["direccion"] == "Calle 21 #5-10", r
    r2 = _r("GET", f"/clientes/{cid}").json()
    assert r2["direccion"] == "Calle 21 #5-10"


# ---------- 195-198 DIAN ----------
def test_195_198_198_196_dian():
    v = ok(_crear_venta(), 201)
    vid = v["id"]
    docs = ok(_r("GET", f"/facturacion/documentos?venta_id={vid}"))
    assert docs, "la venta no tiene documento fiscal"
    doc = docs[0]["id"]
    assert docs[0]["cufe"], "documento sin CUFE"
    # 196 enviar
    r = ok(_r("POST", f"/facturacion/{doc}/enviar"))
    assert r["estado_dian"] == "enviado"
    # 197 consulta estado
    r = ok(_r("POST", f"/facturacion/{doc}/consultar"))
    assert r["estado_dian"] == "aprobado"
    r = ok(_r("GET", "/facturacion/documentos"))
    assert any(d["id"] == doc and d["estado_dian"] == "aprobado" for d in r)
    # 198 rechazo + reintento
    r = ok(_r("POST", f"/facturacion/{doc}/rechazar", params={"motivo": "Dato invalido (test)"}))
    assert r["estado_dian"] == "rechazado"
    r = ok(_r("POST", f"/facturacion/{doc}/reintentar"))
    assert r["estado_dian"] == "enviado"


# ---------- 202 correo / 203 whatsapp ----------
def test_202_203_correo_whatsapp():
    v = ok(_crear_venta(cliente_id=1), 201)
    docs = ok(_r("GET", f"/facturacion/documentos?venta_id={v['id']}"))
    assert docs, "la venta no tiene documento fiscal"
    doc = docs[0]["id"]
    r = ok(_r("POST", f"/facturacion/{doc}/correo"))
    assert "destinatario" in r or "ok" in r, r
    r = ok(_r("POST", f"/facturacion/{doc}/whatsapp"))
    assert "telefono" in r or "url" in r or "ok" in r, r


# ---------- 216 autorización de devoluciones ----------
def test_216_devolucion_autorizacion():
    v = ok(_crear_venta(), 201)
    vid = v["id"]
    body = {"empresa_id": 1, "sucursal_id": 1, "venta_id": vid, "tipo": "total",
            "detalle": [{"producto_id": _producto_id(), "cantidad": 1}]}
    r = _r("POST", "/devoluciones", h=Hc, json=body)
    assert r.status_code == 403, f"cajero sin permiso debería recibir 403: {r.status_code}"
    ok(_r("POST", "/devoluciones", json=body), 201)


# ---------- 274 productos vencidos ----------
def test_274_vencidos():
    r = ok(_r("GET", "/reportes/por-vencer"))
    assert "vencidos" in r, "por-vencer sin vencidos"
    r = ok(_r("GET", "/inventario/por-lote"))
    assert any(l.get("codigo") == "L21-VENC" and l.get("estado") == "vencido" for l in r)


# ---------- 343 historial de cambios ----------
def test_343_historial():
    pid = _producto_id()
    r = ok(_r("PUT", f"/productos/{pid}", json={"precio_venta": 12000}))
    assert r["precio_venta"] == 12000
    ok(_r("PUT", f"/productos/{pid}", json={"precio_venta": 10000}))
    r = ok(_r("GET", f"/productos/{pid}/precios"))
    assert len(r) >= 1, "historial de precios vacío"
    r = ok(_r("GET", "/reportes/auditoria"))
    assert len(r) >= 1


# ---------- 350 restricciones por usuario ----------
def test_350_restricciones_usuario():
    r = ok(_r("GET", "/seguridad/mi-permisos"))
    assert len(r) >= 1
    v = ok(_crear_venta(), 201)
    r = _r("POST", f"/ventas/{v['id']}/anular", h=Hc)
    assert r.status_code == 403, "cajero no debería anular"


# ---------- 376 códigos de barras ----------
def test_376_codigos_barras():
    pid = _producto_id()
    r = _r("GET", f"/productos/{pid}/codigo-barras")
    assert r.status_code == 200, f"{r.status_code}"
    assert "svg" in r.text.lower() or "barcode" in r.text.lower() or "cid" in r.text.lower()


# ---------- 449 análisis rotación ----------
def test_449_rotacion():
    r = ok(_r("GET", "/reportes/rotacion"))
    assert isinstance(r, list)


# ---------- 450 análisis rentabilidad ----------
def test_450_rentabilidad():
    r = ok(_r("GET", "/reportes/productos-mas-rentables"))
    assert isinstance(r, list)
    r = ok(_r("GET", "/reportes/estado-resultados"))
    assert isinstance(r, dict)


if __name__ == "__main__":
    setup_module()
    tests = [test_36_40_tipos_producto, test_105_ordenes_compra, test_115_gastos_compra,
             test_122_direccion_cliente, test_195_198_198_196_dian, test_202_203_correo_whatsapp,
             test_216_devolucion_autorizacion, test_274_vencidos, test_343_historial,
             test_350_restricciones_usuario, test_376_codigos_barras, test_449_rotacion,
             test_450_rentabilidad]
    fails = 0
    for t in tests:
        try:
            t()
            print(f"  OK {t.__name__}")
        except Exception as e:
            fails += 1
            print(f"  FAIL {t.__name__}: {e}")
    print(f"\n========== VALIDACION 21: {len(tests) - fails} OK · {fails} FALLO ==========")
    sys.exit(1 if fails else 0)