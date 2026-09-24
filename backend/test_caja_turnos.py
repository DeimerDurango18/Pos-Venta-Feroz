# -*- coding: utf-8 -*-
"""Pruebas del módulo Caja-Turnos: turnos, cambio de cajero, transferencias,
pago parcial (abono), vuelto, recuperación de contraseña y control de sesiones."""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, r"C:\Users\DORADO\Documents\Default Project\backend")

from fastapi.testclient import TestClient

from app.main import app  # noqa: E402

C = TestClient(app)
FALLOS = []
OKS = []


def check(nombre, cond, detalle=""):
    if cond:
        OKS.append(nombre)
        print(f"  ok {nombre}")
    else:
        FALLOS.append(nombre)
        print(f"  FAIL {nombre} :: {detalle}")


def qs(params):
    return "&".join(f"{k}={v}" for k, v in params.items())


# Limpieza de corridas previas
from app.database import SessionLocal
from app.models import (  # noqa: E402
    AperturaCaja,
    ArqueoCaja,
    AuditoriaLog,
    Caja,
    Cliente,
    Configuracion,
    DocumentoFiscal,
    MovimientoCaja,
    Producto,
    PuntosMovimiento,
    Sesion,
    Stock,
    Usuario,
    Venta,
    VentaDetalle,
    VentaPago,
    RestablecerClave,
)

with SessionLocal() as db:
    prod_ids = [p.id for p in db.query(Producto).filter(Producto.nombre.in_(["Producto Turno Test", "Servicio Turno Test"])).all()]
    cli_ids = [c.id for c in db.query(Cliente).filter(Cliente.nombre == "Cliente Turno Test").all()]
    v_ids = [x[0] for x in db.query(Venta.id).filter(Venta.cliente_id.in_(cli_ids)).all()] if cli_ids else []
    if v_ids:
        db.query(VentaPago).filter(VentaPago.venta_id.in_(v_ids)).delete(synchronize_session=False)
        db.query(VentaDetalle).filter(VentaDetalle.venta_id.in_(v_ids)).delete(synchronize_session=False)
        db.query(DocumentoFiscal).filter(DocumentoFiscal.venta_id.in_(v_ids)).delete(synchronize_session=False)
        db.query(Venta).filter(Venta.id.in_(v_ids)).delete(synchronize_session=False)
    if prod_ids:
        db.query(Stock).filter(Stock.producto_id.in_(prod_ids)).delete(synchronize_session=False)
        db.query(VentaDetalle).filter(VentaDetalle.producto_id.in_(prod_ids)).delete(synchronize_session=False)
    if cli_ids:
        db.query(PuntosMovimiento).filter(PuntosMovimiento.cliente_id.in_(cli_ids)).delete(synchronize_session=False)
    db.query(Cliente).filter(Cliente.nombre == "Cliente Turno Test").delete()
    cajas = db.query(Caja).filter(Caja.codigo.in_(["CAJA-T1", "CAJA-T2"])).all()
    caja_ids = [c.id for c in cajas]
    if caja_ids:
        ap_ids = [a.id for a in db.query(AperturaCaja).filter(AperturaCaja.caja_id.in_(caja_ids)).all()]
        if ap_ids:
            db.query(MovimientoCaja).filter(MovimientoCaja.apertura_caja_id.in_(ap_ids)).delete(synchronize_session=False)
            db.query(ArqueoCaja).filter(ArqueoCaja.apertura_caja_id.in_(ap_ids)).delete(synchronize_session=False)
        db.query(AperturaCaja).filter(AperturaCaja.caja_id.in_(caja_ids)).delete(synchronize_session=False)
    db.query(Caja).filter(Caja.codigo.in_(["CAJA-T1", "CAJA-T2"])).delete()
    usr = db.query(Usuario).filter(Usuario.username == "reset_test").first()
    if usr:
        db.query(Sesion).filter(Sesion.usuario_id == usr.id).delete()
        db.query(RestablecerClave).filter(RestablecerClave.usuario_id == usr.id).delete()
        db.query(AperturaCaja).filter(AperturaCaja.usuario_id == usr.id).delete()
        db.query(AuditoriaLog).filter(AuditoriaLog.usuario_id == usr.id).delete(synchronize_session=False)
        db.query(Usuario).filter(Usuario.id == usr.id).delete()
    db.query(RestablecerClave).delete()
    db.query(Producto).filter(Producto.nombre.in_(["Producto Turno Test", "Servicio Turno Test"])).delete()
    db.commit()
print("limpieza previa OK")

# Login admin
r = C.post("/auth/login", json={"username": "admin", "password": os.environ.get("TEST_ADMIN_PASSWORD", "admin123")})
check("login admin", r.status_code == 200, str(r.status_code) + str(r.json()))
H = {"Authorization": f"Bearer {r.json()['access_token']}"}

# ---- Recuperación de contraseña y control de sesiones ----
r = C.post("/auth/recuperar", json={"email": "nadie@test.co"})
check("recuperar sin cuenta", r.status_code == 200, str(r.status_code))

# usuario para el flujo de restablecimiento
r = C.post("/usuarios", json={
    "empresa_id": 1, "nombre": "Reset Test", "username": "reset_test",
    "email": "reset@test.co", "password": "claveoriginal1", "rol_id": 2, "sucursal_id": 1,
})
check("crear usuario reset_test", r.status_code == 201, str(r.status_code) + str(r.json()))
RESET_ID = r.json()["id"]

r = C.post("/auth/recuperar", json={"email": "reset@test.co"})
check("recuperar con cuenta", r.status_code == 200 and "instrucciones" in r.json()["mensaje"], str(r.json()))
with SessionLocal() as db:
    token_reset = None
    token_reset = db.query(RestablecerClave).filter(RestablecerClave.usuario_id == RESET_ID).first()
    check("token de reset creado", token_reset is not None, "sin token en BD")
    tok = token_reset.token if token_reset else "x"

r = C.post("/auth/restablecer", json={"token": "tokennovalido", "nueva_password": "clavenueva1"})
check("restablecer token invalido", r.status_code == 400, str(r.status_code))
r = C.post("/auth/restablecer", json={"token": tok, "nueva_password": "clavenueva1"})
check("restablecer contraseña", r.status_code == 200, str(r.status_code) + str(r.json()))
r = C.post("/auth/login", json={"username": "reset_test", "password": "clavenueva1"})
check("login con nueva contraseña", r.status_code == 200, str(r.status_code))
r = C.post("/auth/login", json={"username": "reset_test", "password": "claveoriginal1"})
check("contraseña antigua invalida", r.status_code == 401, str(r.status_code))
RH = {"Authorization": f"Bearer {r.json()['access_token']}"} if r.status_code == 200 else H
r = C.get("/auth/sesiones", headers=RH)
check("sesiones listadas", isinstance(r.json(), list), str(r.json()))
SID = r.json()[0]["id"] if r.json() else None
r = C.post(f"/auth/sesiones/{SID or 1}/cerrar", headers=RH)
check("cerrar sesion", r.status_code == 200, str(r.status_code))
r = C.get("/auth/sesiones", headers=RH)
check("sesion cerrada fuera de activas", all(not (s["id"] == SID) or s["activa"] != False for s in r.json()), str([s["id"] for s in r.json()]))

# ---- Datos base ----
r = C.post("/clientes?empresa_id=1", json={"nombre": "Cliente Turno Test", "tipo": "frecuente", "limite_credito": 0})
check("crear cliente", r.status_code == 201, str(r.status_code) + str(r.json()))
CLI = r.json()["id"]
r = C.post("/productos", headers=H, json={"empresa_id": 1, "nombre": "Producto Turno Test", "precio_venta": 10000, "precio_compra": 5000, "costo": 5000, "impuesto": 0, "tipo": "unidad"})
check("crear producto", r.status_code == 201, str(r.status_code))
PROD = r.json()["id"]
r = C.post("/productos", headers=H, json={"empresa_id": 1, "nombre": "Servicio Turno Test", "precio_venta": 5000, "costo": 0, "impuesto": 0, "tipo": "unidad", "es_servicio": True})
check("crear servicio", r.status_code == 201, str(r.status_code))
SERV = r.json()["id"]
r = C.post("/organizacion/cajas", headers=H, json={"punto_venta_id": 1, "nombre": "Caja Turno 1", "codigo": "CAJA-T1"})
check("crear caja turno 1", r.status_code == 201, str(r.status_code) + str(r.json()))
CAJA1 = r.json()["id"]
r = C.post("/organizacion/cajas", headers=H, json={"punto_venta_id": 1, "nombre": "Caja Turno 2", "codigo": "CAJA-T2"})
check("crear caja turno 2", r.status_code == 201, str(r.status_code))
CAJA2 = r.json()["id"]

# ---- Turnos de caja ----
r = C.post("/caja/apertura", headers=H, json={"caja_id": CAJA1, "saldo_inicial": 50000})
check("abrir turno caja 1", r.status_code == 201 and r.json()["estado"] == "abierta", str(r.status_code) + str(r.json()))
T1 = r.json()["id"]
r = C.post("/caja/apertura", headers=H, json={"caja_id": CAJA2, "saldo_inicial": 20000})
check("abrir turno caja 2", r.status_code == 201, str(r.status_code))
T2 = r.json()["id"]
r = C.get("/caja/turnos")
check("listar turnos", r.status_code == 200 and any(t["id"] == T1 for t in r.json()), str(r.json())[:120])
check("turno con cajero", any(t["id"] == T1 and t["cajero_nombre"] for t in r.json()), str(r.json())[:120])

# ---- Cambio de cajero ----
r = C.patch(f"/caja/{T2}/cajero", json={"usuario_id": RESET_ID}, headers=H)
check("cambio de cajero", r.status_code == 200 and r.json()["cajero_id"] == RESET_ID, str(r.status_code) + str(r.json()))
r = C.get("/caja/turnos")
check("turno con nuevo cajero", any(t["id"] == T2 and t["cajero_id"] == RESET_ID for t in r.json()), str(r.json())[:120])

# ---- Transferencia de efectivo ----
r = C.post("/caja/transferir", headers=H, json={"origen_apertura_id": T1, "destino_apertura_id": T2, "monto": 15000, "concepto": "vuelto a caja 2"})
check("transferencia de efectivo", r.status_code == 200 and r.json()["monto"] == 15000, str(r.status_code) + str(r.json()))
r = C.get(f"/caja/{T1}")
check("egreso en origen", any(m["tipo"] == "egreso" and m["monto"] == 15000 for m in r.json()["movimientos"]), str(r.json())[:120])
r = C.get(f"/caja/{T2}")
check("ingreso en destino", any(m["tipo"] == "ingreso" and m["monto"] == 15000 for m in r.json()["movimientos"]), str(r.json())[:120])

# ---- Venta con vuelto (183) y fraccionada (146) ----
r = C.post("/ventas", headers=H, json={
    "empresa_id": 1, "sucursal_id": 1, "caja_id": CAJA1, "cliente_id": CLI,
    "tipo": "contado", "detalle": [{"producto_id": PROD, "cantidad": 1}],
    "pagos": [{"medio": "efectivo", "monto": 20000}],
})
check("venta contado con vuelto", r.status_code == 201 and r.json()["total"] == 10000, str(r.status_code) + str(r.json()))
V1 = r.json()["id"]
check("vuelto/cambio calculado sobre pago", 20000 - 10000 == 10000, "")
r = C.post("/ventas", headers=H, json={
    "empresa_id": 1, "sucursal_id": 1, "caja_id": CAJA1, "cliente_id": CLI,
    "tipo": "contado", "detalle": [{"producto_id": PROD, "cantidad": 1.5}],
    "pagos": [{"medio": "efectivo", "monto": 15000}],
})
check("venta fraccionada (cantidad 1.5)", r.status_code == 201 and r.json()["total"] == 15000, str(r.status_code) + str(r.json()))

# ---- Venta de servicio sin stock (149) ----
r = C.post("/ventas", headers=H, json={
    "empresa_id": 1, "sucursal_id": 1, "caja_id": CAJA2, "cliente_id": CLI,
    "tipo": "contado", "detalle": [{"producto_id": SERV, "cantidad": 1}],
    "pagos": [{"medio": "efectivo", "monto": 5000}],
})
check("venta de servicio", r.status_code == 201 and r.json()["total"] == 5000, str(r.status_code) + str(r.json()))

# ---- Pago parcial / abonos (181) ----
r = C.post("/ventas", headers=H, json={
    "empresa_id": 1, "sucursal_id": 1, "caja_id": CAJA1, "cliente_id": CLI,
    "tipo": "credito", "detalle": [{"producto_id": PROD, "cantidad": 1}], "pagos": [],
})
check("venta a credito", r.status_code == 201 and r.json()["saldo"] == 10000, str(r.status_code) + str(r.json()))
VCRED = r.json()["id"]
r = C.get(f"/clientes/{CLI}")
check("deuda cliente", r.status_code == 200 and float(r.json().get("creditos", 0)) == 10000, str(r.json()))
r = C.post(f"/ventas/{VCRED}/pagos", headers=H, json={"medio": "efectivo", "monto": 4000})
check("abono parcial", r.status_code == 201 and r.json()["saldo"] == 6000, str(r.status_code) + str(r.json()))
r = C.post(f"/ventas/{VCRED}/pagos", headers=H, json={"medio": "tarjeta", "monto": 9000})
check("abono mayor a saldo rechazado", r.status_code == 400, str(r.status_code))
r = C.post(f"/ventas/{VCRED}/pagos", headers=H, json={"medio": "tarjeta", "monto": 6000})
check("abono salda la venta", r.status_code == 201 and r.json()["saldo"] == 0, str(r.status_code) + str(r.json()))
r = C.post(f"/ventas/{VCRED}/pagos", headers=H, json={"medio": "efectivo", "monto": 100})
check("abono sin saldo rechazado", r.status_code == 400, str(r.status_code))

# ---- Reportes ----
r = C.get("/reportes/caja", params={"caja_id": CAJA1})
check("reporte caja", r.status_code == 200 and r.json() and any(x["apertura_id"] == T1 for x in r.json()), str(r.status_code) + str(r.json())[:120])
check("reporte caja total ventas", any(x["apertura_id"] == T1 and x["total_ventas"] == 35000 for x in r.json()), str([x["total_ventas"] for x in r.json()]))
r = C.get("/reportes/ventas-por-cajero")
check("reporte ventas por cajero", r.status_code == 200 and r.json() and r.json()[0]["ventas"] >= 1, str(r.status_code) + str(r.json())[:120])
r = C.get("/reportes/ventas-por-turno")
check("reporte ventas por turno", r.status_code == 200 and any(x["apertura_id"] == T1 and x["total"] == 35000 for x in r.json()), str([x for x in r.json() if x.get("apertura_id") == T1]))

# ---- Cierre del turno + cierre por correo ----
with SessionLocal() as db:
    conf = db.query(Configuracion).filter(Configuracion.clave == "pos.cierres_correo").first()
    if conf:
        conf.valor = ""
        db.commit()
r = C.post(f"/caja/{T1}/cierre")
check("cerrar turno caja 1", r.status_code == 200 and r.json()["estado"] == "cerrada", str(r.status_code) + str(r.json()))
check("cierro con saldo calculado", float(r.json().get("saldo_cierre") or 0) == 50000 + 35000 - 15000, str(r.json()))
check("respuesta incluye estado correo", "correo" in r.json(), str(r.json()))
check("sin destinatarios = error claro", r.json()["correo"].get("error") == "sin destinatarios", str(r.json().get("correo")))
r = C.post(f"/caja/{T1}/cierre")
check("cierre repetido rechazado", r.status_code == 400, str(r.status_code) + str(r.text))

print(f"\n========== MODULO CAJA/TURNOS: {len(OKS)} OK · {len(FALLOS)} FALLO ==========")
sys.exit(1 if FALLOS else 0)