"""Tests para nuevos items: 385 horario, 386 cantidad, 424 2x1/3x2, 317 dashboard inv val,
380 lotes-etiquetas, 423 por-vencer, 446 sugerir-reposicion, 433 cobranza,
169 fidelizacion, 391 apartados, 124 devoluciones, 439 comisiones vendedores."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from fastapi.testclient import TestClient
from app.main import app

from app.database import SessionLocal
from app.models import (
    Categoria, Cliente, Producto, Promocion, PromocionProducto,
    ReglaComision, Stock
)
from app.promos import calcular_promociones

C = TestClient(app)


def _login():
    r = C.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


H = _login()


def _request(method, url, **kw):
    return C.request(method, url, headers=H, **kw)


def setup_module():
    db = SessionLocal()
    db.query(Promocion).filter(Promocion.nombre.in_(["Horario test", "Cantidad test", "2x1 test"])).delete()
    cat = db.query(Categoria).filter(Categoria.nombre == "CatTest").first()
    if not cat:
        cat = Categoria(nombre="CatTest", activa=True)
        db.add(cat); db.commit(); db.refresh(cat)
    cli = db.query(Cliente).filter(Cliente.documento == "CLI-TEST-1").first()
    if not cli:
        cli = Cliente(nombre="Cli", documento="CLI-TEST-1", empresa_id=1)
        db.add(cli); db.commit(); db.refresh(cli)
    prod = db.query(Producto).filter(Producto.sku == "P1-TEST").first()
    if not prod:
        prod = Producto(nombre="Prod", sku="P1-TEST", precio_venta=10000, empresa_id=1, categoria_id=cat.id, stock_minimo=5, stock_maximo=20, punto_reorden=5)
        db.add(prod); db.commit(); db.refresh(prod)
    st = db.query(Stock).filter(Stock.producto_id == prod.id, Stock.sucursal_id == 1).first()
    if not st:
        st = Stock(producto_id=prod.id, sucursal_id=1, existencias=100, disponible=100)
        db.add(st); db.commit(); db.refresh(st)
    reg = db.query(ReglaComision).filter(ReglaComision.producto_id == prod.id).first()
    if not reg:
        reg = ReglaComision(empresa_id=1, producto_id=prod.id, porcentaje=5)
        db.add(reg); db.commit(); db.refresh(reg)
    db.close()


def teardown_module():
    db = SessionLocal()
    db.query(Promocion).filter(Promocion.nombre.in_(["Horario test", "Cantidad test", "2x1 test"])).delete()
    db.commit()
    db.close()


def assert200(r):
    assert r is not None and r.status_code == 200, f"expected 200 got {r.status_code if r else 'None'}: {r.text if r else ''}"


def assert201(r):
    assert r is not None and r.status_code == 201, f"expected 201 got {r.status_code if r else 'None'}"


# ---------- 124 devoluciones ----------
def test_124_devoluciones():
    assert200(_request("GET", "/devoluciones"))


# ---------- 391 apartados ----------
def test_391_apartados():
    assert200(_request("GET", "/apartados"))


# ---------- 439 comisiones vendedores ----------
def test_439_reglas_comision():
    assert200(_request("GET", "/vendedores/reglas-comision"))


# ---------- 169 fidelizacion ----------
def test_169_fidelizacion():
    assert200(_request("GET", "/fidelizacion/puntos"))
    assert200(_request("GET", "/fidelizacion/resumen"))


# ---------- 433 cobranza ----------
def test_433_cobranza():
    r = _request("GET", "/cartera/cobranza")
    assert200(r)
    j = r.json()
    assert "total_cartera" in j and "tramos" in j


# ---------- 385 promociones por horario ----------
def test_385_promo_horario():
    r = _request("POST", "/promociones", json={
        "nombre": "Horario test", "tipo": "porcentaje", "valor": 10,
        "hora_desde": "08:00", "hora_hasta": "20:00", "activa": True})
    assert201(r)
    pid = r.json()["id"]
    r = _request("GET", f"/promociones/{pid}")
    assert200(r)
    j = r.json()
    assert j["hora_desde"] == "08:00" and j["hora_hasta"] == "20:00"


# ---------- 386 promociones por cantidad ----------
def test_386_promo_cantidad_minima():
    r = _request("POST", "/promociones", json={
        "nombre": "Cantidad test", "tipo": "porcentaje", "valor": 10,
        "cantidad_minima": 5, "activa": True})
    assert201(r)
    pid = r.json()["id"]
    r = _request("GET", f"/promociones/{pid}")
    assert200(r)
    assert r.json()["cantidad_minima"] == 5


def test_386_calcular_descuento_por_cantidad():
    db = SessionLocal()
    try:
        cat = db.query(Categoria).first()
        prod = db.query(Producto).first()
        assert cat and prod
        prom = db.query(Promocion).filter(Promocion.nombre == "Cantidad test").first()
        assert prom, "promo no creada"
        assert prom.cantidad_minima == 5
        # desactivar otras promociones para aislar el cálculo
        for p in db.query(Promocion).filter(Promocion.id != prom.id, Promocion.activa == True).all():
            p.activa = False
        db.commit()
        # cantidad 3 < 5 -> sin descuento
        d3 = calcular_promociones(db, [{"producto_id": prod.id, "cantidad": 3, "precio": 100}], None)
        assert d3 == 0, f"esperado 0 con cantidad 3, got {d3}"
        # cantidad 6 >= 5 -> 10% de 600 = 60
        d6 = calcular_promociones(db, [{"producto_id": prod.id, "cantidad": 6, "precio": 100}], None)
        assert d6 == 60, f"esperado 60 con cantidad 6, got {d6}"
    finally:
        db.close()


# ---------- 424 2x1 ----------
def test_424_promo_2x1():
    r = _request("POST", "/promociones", json={
        "nombre": "2x1 test", "tipo": "2x1", "activa": True})
    assert201(r)
    pid = r.json()["id"]
    r = _request("GET", f"/promociones/{pid}")
    assert200(r)
    assert r.json()["tipo"] == "2x1"


# ---------- 317 inventario valorizado dashboard ----------
def test_317_dashboard_inventario_valorizado():
    assert200(_request("GET", "/reportes/dashboard"))
    r = _request("GET", "/reportes/dashboard")
    j = r.json()
    assert "inventario_valorizado" in j


# ---------- 380 lotes-etiquetas ----------
def test_380_lotes_etiquetas():
    r = _request("GET", "/reportes/lotes-etiquetas")
    assert200(r)
    j = r.json()
    assert "total_lotes" in j and "etiquetas" in j


# ---------- 423 por-vencer ----------
def test_423_por_vencer():
    r = _request("GET", "/reportes/por-vencer")
    assert200(r)
    j = r.json()
    assert "vencidos" in j and "lotes" in j


# ---------- 446 sugerir reposicion ----------
def test_446_sugerir_reposicion():
    r = _request("GET", "/inventario/sugerir-reposicion")
    assert200(r)
    j = r.json()
    assert "total" in j and "sugerencias" in j


if __name__ == "__main__":
    setup_module()
    tests = [
        test_124_devoluciones,
        test_391_apartados,
        test_439_reglas_comision,
        test_169_fidelizacion,
        test_433_cobranza,
        test_385_promo_horario,
        test_386_promo_cantidad_minima,
        test_386_calcular_descuento_por_cantidad,
        test_424_promo_2x1,
        test_317_dashboard_inventario_valorizado,
        test_380_lotes_etiquetas,
        test_423_por_vencer,
        test_446_sugerir_reposicion,
    ]
    for t in tests:
        t()
        print(f"  ✓ {t.__name__}")
    teardown_module()
    print(f"\n========== TEST NUEVOS: {len(tests)} OK · 0 FALLO ==========")
    print("OK")
