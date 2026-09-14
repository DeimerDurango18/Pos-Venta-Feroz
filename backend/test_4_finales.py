import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from fastapi.testclient import TestClient

from app.main import app

C = TestClient(app)

FALLOS = []


def ok(path, metodo="GET", token=None, json=None, esperado=None, params=None):
    h = {"Authorization": token} if token else {}
    r = C.request(metodo, path, headers=h, json=json, params=params)
    if esperado is not None and r.status_code != esperado:
        raise AssertionError(f"{metodo} {path} -> {r.status_code} (esperado {esperado}): {r.text}")
    return r


LOGIN = {"username": "admin", "password": "admin123"}
H = {"Authorization": f"Bearer {C.post('/auth/login', json=LOGIN).json()['access_token']}"}


def t(name, fn):
    try:
        fn()
        print(f"  OK {name}")
    except AssertionError as e:
        FALLOS.append((name, str(e)))
        print(f"  FALLO {name}: {e}")


def _verificar_prod(producto_id, **kwargs):
    r = ok(f"/productos/{producto_id}", token=H["Authorization"])
    assert r.status_code == 200, r.text
    for k, v in kwargs.items():
        assert r.json().get(k) == v, f"{k}={r.json().get(k)} esperado {v}"


def test_ficha_tecnica():
    r = ok(
        "/productos",
        "POST",
        token=H["Authorization"],
        json={
            "empresa_id": 1,
            "nombre": "Prod Ficha 51",
            "tipo": "unidad",
            "precio_venta": 10000,
            "ficha_tecnica": "Material: acero, Peso: 2kg",
        },
        esperado=201,
    )
    pid = r.json()["id"]
    _verificar_prod(pid, ficha_tecnica="Material: acero, Peso: 2kg")
    r = ok(f"/productos/{pid}", "PUT", token=H["Authorization"], json={"ficha_tecnica": "V2: fibra"})
    assert r.json()["ficha_tecnica"] == "V2: fibra", r.text
    _verificar_prod(pid, ficha_tecnica="V2: fibra")


def test_precios_competencia():
    r = ok(
        "/productos",
        "POST",
        token=H["Authorization"],
        json={"empresa_id": 1, "nombre": "Prod Comp 451", "tipo": "unidad", "precio_venta": 8000},
        esperado=201,
    )
    pid = r.json()["id"]
    ok(
        f"/productos/{pid}/precios-competencia",
        "POST",
        token=H["Authorization"],
        json={"competidor": "Exito", "precio": 8200, "fecha": str(date.today()), "notas": "Precio góndola"},
        esperado=201,
    )
    ok(
        f"/productos/{pid}/precios-competencia",
        "POST",
        token=H["Authorization"],
        json={"competidor": "Jumbo", "precio": 7950},
        esperado=201,
    )
    r = ok(f"/productos/{pid}/precios-competencia", token=H["Authorization"])
    assert len(r.json()) == 2, r.text
    assert {x["competidor"] for x in r.json()} == {"Exito", "Jumbo"}
    pc_id = next(x["id"] for x in r.json() if x["competidor"] == "Jumbo")
    ok(f"/productos/precios-competencia/{pc_id}", "DELETE", token=H["Authorization"], esperado=204)
    r = ok(f"/productos/{pid}/precios-competencia", token=H["Authorization"])
    assert len(r.json()) == 1 and r.json()[0]["competidor"] == "Exito", r.text


def test_lista_institucional():
    # producto con precio venta alto pero institucional menor
    r = ok(
        "/productos",
        "POST",
        token=H["Authorization"],
        json={"empresa_id": 1, "nombre": "Prod Inst 430", "tipo": "unidad", "precio_venta": 20000, "precio_institucional": 15000},
        esperado=201,
    )
    pid = r.json()["id"]
    assert r.json()["precio_institucional"] == 15000.0, r.text
    # cliente institucional
    r = ok(
        "/clientes",
        "POST",
        params={"empresa_id": 1},
        token=H["Authorization"],
        json={
            "nombre": "Hospital Central",
            "tipo": "institucional",
            "documento": "900111222",
            "email": "compras@hospital.co",
        },
        esperado=201,
    )
    cid = r.json()["id"]
    ok(
        f"/productos/{pid}",
        "PUT",
        token=H["Authorization"],
        json={"stock_minimo": 1},
    )
    ok(
        "/productos",
        "POST",
        token=H["Authorization"],
        json={"empresa_id": 1, "nombre": "PROV-INST", "tipo": "unidad"},
    )
    # stock
    st = C.get("/inventario").json() if False else None
    # pequeña venta sin precio explícito -> debe usar precio_institucional (15000)
    r = ok(
        "/ventas",
        "POST",
        token=H["Authorization"],
        json={
            "empresa_id": 1,
            "sucursal_id": 1,
            "cliente_id": cid,
            "tipo": "contado",
            "detalle": [{"producto_id": pid, "cantidad": 1}],
            "pagos": [{"medio": "efectivo", "monto": 15000}],
        },
    )
    assert r.status_code in (200, 201), r.text
    assert float(r.json()["total"]) == 15000.0, r.text
    assert float(r.json()["detalle"][0]["precio"]) == 15000.0, r.text


def test_registro_errores():
    # simular un error -> se registra
    r = ok(
        "/sistema/errores/simular",
        "POST",
        token=H["Authorization"],
        json={"modulo": "test346", "mensaje": "fallo simulado"},
        esperado=201,
    )
    assert r.json()["mensaje"] == "fallo simulado", r.text
    r = ok("/sistema/errores", token=H["Authorization"])
    assert any(x["modulo"] == "test346" for x in r.json()), r.text
    err = r.json()[0]
    # marcar como resuelto
    ok(f"/sistema/errores/{err['id']}/resolver", "PATCH", token=H["Authorization"], esperado=200)
    r = ok("/sistema/errores", token=H["Authorization"])
    assert any(x["id"] == err["id"] and x["resuelto"] for x in r.json()), r.text
    # filtro por modulo
    r = ok("/sistema/errores", params={"modulo": "test346"}, token=H["Authorization"])
    assert len(r.json()) >= 1 and all(x["modulo"] == "test346" for x in r.json()), r.text


t("51 Ficha técnica", test_ficha_tecnica)
t("346 Registro de errores", test_registro_errores)
t("430 Lista institucional", test_lista_institucional)
t("451 Precios de competencia", test_precios_competencia)

print("========== 4 FINALES: %d OK · %d FALLO ==========" % (4 - len(FALLOS), len(FALLOS)))
sys.exit(1 if FALLOS else 0)