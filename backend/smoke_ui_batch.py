import os, json, urllib.request, urllib.parse, random, string

BASE = "http://127.0.0.1:28743"
TOKEN = None


def call(method, path, body=None, expect_ok=True):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            err = json.loads(raw)
        except Exception:
            err = raw
        if expect_ok:
            print(f"  FAIL {method} {path} -> {e.code}: {err}")
            raise
        return e.code, err


def main():
    global TOKEN
    st, r = call("POST", "/auth/login", {"username": "admin", "password": "admin123"})
    TOKEN = r["access_token"]
    print("OK login admin")

    suf = "-UI" + "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    print(f"== Organizacion (sufijo {suf}) ==")
    st, empresas = call("GET", "/organizacion/empresas")
    print(f"  GET empresas -> {len(empresas)}")
    st, emp = call("POST", "/organizacion/empresas", {"nombre": "Empresa UI" + suf, "nit": "9090" + suf, "razon_social": "Razon prueba", "regimen": "simplificado"})
    print(f"  POST empresa {emp['id']} {emp['nombre']} activa={emp['activa']}")
    st, emp2 = call("PUT", f"/organizacion/empresas/{emp['id']}", {"telefono": "5551234", "direccion": "Calle 1"})
    print(f"  PUT empresa -> telefono={emp2['telefono']} dir={emp2['direccion']}")
    st, suc = call("POST", "/organizacion/sucursales", {"empresa_id": emp["id"], "nombre": "Sucursal UI" + suf, "ciudad": "Bogota"})
    print(f"  POST sucursal {suc['id']} {suc['nombre']} activa={suc['activa']}")
    st, suc2 = call("PUT", f"/organizacion/sucursales/{suc['id']}", {"telefono": "555111"})
    print(f"  PUT sucursal -> telefono={suc2['telefono']}")
    st, pv = call("POST", "/organizacion/puntos-venta", {"sucursal_id": suc["id"], "nombre": "PV UI" + suf, "tipo": "Principal"})
    print(f"  POST punto-venta {pv['id']} {pv['nombre']} activo={pv['activo']}")
    st, caja = call("POST", "/organizacion/cajas", {"punto_venta_id": pv["id"], "nombre": "Caja UI" + suf, "codigo": "C" + suf, "saldo_inicial": 10000})
    print(f"  POST caja {caja['id']} {caja['nombre']} saldo_inicial={caja['saldo_inicial']} activa={caja['activa']}")
    st, cajas = call("GET", "/organizacion/cajas")
    print(f"  GET cajas -> {len(cajas)}")

    print("== Vendedores ==")
    st, vend = call("GET", "/vendedores")
    print(f"  GET vendedores -> {len(vend)}")
    if vend:
        vid = vend[0]["id"]
        st, meta = call("POST", "/vendedores/metas", {"vendedor_id": vid, "periodo": "2026-09", "meta_ventas": 5000000, "meta_utilidad": 1000000})
        print(f"  POST meta -> vendedor_id={meta['vendedor_id']} periodo={meta['periodo']} ventas={meta['meta_ventas']}")
        st, regla = call("POST", "/vendedores/reglas-comision", {"empresa_id": 1, "vendedor_id": vid, "producto_id": None, "porcentaje": 3.5})
        print(f"  POST regla -> id={regla['id']} vendedor_id={regla['vendedor_id']} pct={regla['porcentaje']}")
        st, reglas = call("GET", "/vendedores/reglas-comision")
        print(f"  GET reglas -> {len(reglas)}")
    else:
        print("  SKIP metas/reglas (sin vendedores)")

    print("== Facturacion detalle/rechazo ==")
    st, docs = call("GET", "/facturacion/documentos")
    print(f"  GET documentos -> {len(docs)}")
    if docs:
        st, det = call("GET", f"/facturacion/documentos/{docs[0]['id']}")
        print(f"  GET doc {det['id']} {det['numero']} estado={det['estado_dian']} cufe={'SI' if det.get('cufe') else 'no'}")
        target = next((d for d in docs if d["estado_dian"] in ("pendiente", "enviado") and not d["anulado"]), docs[0])
        st, rec = call("POST", f"/facturacion/{target['id']}/rechazar?motivo={urllib.parse.quote('Prueba UI smNul')}")
        print(f"  POST rechazar {rec['numero']} -> estado={rec['estado_dian']} motivo={rec.get('motivo_rechazo')}")
        st, ret = call("POST", f"/facturacion/{target['id']}/reintentar")
        print(f"  POST reintentar -> estado={ret.get('estado_dian')}")

    print("== Proveedores PUT ==")
    st, prov = call("GET", "/proveedores")
    if prov:
        p = prov[0]
        st, up = call("PUT", f"/proveedores/{p['id']}", {"contacto": p.get("contacto") or "Contacto UI", "ciudad": p.get("ciudad") or "Bogota", "activo": True})
        print(f"  PUT proveedor {up['id']} {up['nombre']} ciudad={up.get('ciudad')} activo={up.get('activo')}")
    else:
        print("  SKIP proveedores (vacio)")

    print("== Bloque 2: Devoluciones/Cartera/Compras/Promos/Fidelizacion ==")
    st, devs = call("GET", "/devoluciones")
    print(f"  GET devoluciones -> {len(devs)}")
    if devs:
        st, det = call("GET", f"/devoluciones/{devs[0]['id']}")
        print(f"  GET devolucion {det['id']} estado={det['estado']} total={det['total_devolucion']} detalle={len(det['detalle'])}")
    st, ventas = call("GET", "/ventas")
    completadas = [v for v in ventas if v.get("estado") == "completada"]
    if completadas:
        v = completadas[0]
        reemplazo = []
        if v.get("detalle"):
            d = v["detalle"][0]
            reemplazo.append({"producto_id": d["producto_id"], "cantidad": 1})
        else:
            reemplazo.append({"producto_id": v["id"] if False else 1, "cantidad": 1})
        st, camb = call("POST", "/devoluciones/cambio", {"empresa_id": 1, "sucursal_id": 1, "venta_id": v["id"], "tipo": "total", "motivo": "Cambio smoke UI", "reembolso_medio": "nota_credito", "detalle": None, "reemplazo": reemplazo})
        print(f"  POST cambio venta {v['id']} -> devolucion={camb.get('devolucion')} venta_nueva={camb.get('venta_nueva')}")
    else:
        print("  SKIP cambio (sin ventas completadas)")

    st, cob = call("GET", "/cartera/cobranza")
    print(f"  GET cobranza -> total={cob['total_cartera']} tramos={[t['tramo'] for t in cob['tramos']]}")

    st, cp = call("GET", "/compras/cuentas-pagar")
    print(f"  GET compras/cuentas-pagar -> {len(cp)}")
    st, compras = call("GET", "/compras")
    if compras:
        st, cdet = call("GET", f"/compras/{compras[0]['id']}")
        print(f"  GET compra/{compras[0]['id']} -> {cdet['numero']} detalle={len(cdet['detalle'])} total={cdet['total']}")
        st, opp = call("POST", "/compras/ordenes", {"empresa_id": 1, "sucursal_id": 1, "proveedor_id": cdet["proveedor_id"], "detalle": [{"producto_id": d["producto_id"], "cantidad": 1, "costo_unitario": d["costo_unitario"] or 1} for d in cdet["detalle"][:1]]})
        print(f"  POST orden UI -> {opp.get('id')} estado={opp.get('estado')}")
        st, op_a = call("POST", f"/compras/ordenes/{opp['id']}/aprobar")
        print(f"  aprobar orden -> {op_a.get('estado')}")
        st, op_r = call("POST", f"/compras/ordenes/{opp['id']}/recibir")
        print(f"  recibir orden -> {op_r.get('estado')}")
    else:
        print("  SKIP detalle compra / orden")

    st, promos = call("GET", "/promociones")
    if promos:
        p0 = promos[0]
        st, pup = call("PUT", f"/promociones/{p0['id']}", {"empresa_id": 1, "nombre": p0["nombre"] + " (UI)", "tipo": p0["tipo"], "valor": p0["valor"], "aplica_a": p0["aplica_a"], "desde": p0.get("desde"), "hasta": p0.get("hasta"), "descripcion": p0.get("descripcion") or "Editada desde UI", "productos": [{"producto_id": x["producto_id"]} for x in (p0.get("productos") or [])]})
        print(f"  PUT promocion {pup['id']} nombre={pup['nombre']}")
    else:
        print("  SKIP PUT promocion (vacio)")

    st, clientes_l = call("GET", "/clientes")
    if clientes_l:
        cid = clientes_l[0]["id"]
        st, bono = call("POST", "/fidelizacion/bonos", {"cliente_id": cid, "codigo": "BUI" + suf, "valor_total": 10000, "motivo": "smoke"})
        print(f"  POST bono -> {bono.get('id')} saldo={bono.get('saldo')}")
        st, cb = call("POST", f"/fidelizacion/bonos/{bono['id']}/consumir?monto=4000")
        print(f"  consumir bono -> saldo={cb['saldo']}")
        st, tarj = call("POST", "/fidelizacion/tarjetas-regalo", {"cliente_id": cid, "codigo": "TUI" + suf, "saldo": 20000})
        print(f"  POST tarjeta -> {tarj.get('id')} saldo={tarj.get('saldo')}")
        st, ct = call("POST", f"/fidelizacion/tarjetas-regalo/{tarj['id']}/consumir?monto=5000")
        print(f"  consumir tarjeta -> saldo={ct['saldo']}")
    else:
        print("  SKIP bonos/tarjetas (sin clientes)")

    print("== Lote 3: Seguridad/Auth/Usuarios ==")
    st, roles = call("GET", "/seguridad/roles")
    print(f"  GET roles -> {len(roles)}")
    st, mperm = call("GET", "/seguridad/mi-permisos")
    print(f"  GET mi-permisos -> es_admin={mperm.get('es_admin')} permisos={len(mperm.get('permisos') or [])}")
    st, perms = call("GET", "/seguridad/permisos")
    print(f"  GET permisos -> {len(perms)}")
    st, ses = call("GET", "/auth/sesiones")
    print(f"  GET sesiones -> {len(ses)}")
    st, verific = call("GET", "/seguridad/verificar/ventas/crear")
    print(f"  verificar ventas/crear -> permitido={verific.get('permitido')}")
    st, usrs = call("GET", "/usuarios")
    if usrs:
        st, usr = call("POST", "/usuarios", {"empresa_id": 1, "nombre": "Usuario UI" + suf, "username": "ui" + suf.lower(), "email": "ui" + suf.lower() + "@test.co", "password": "ui12345", "rol_id": roles[0]["id"] if roles else None, "vendedor": True})
        print(f"  POST usuario -> {usr.get('id')} {usr.get('username')}")
        st, usr_up = call("PUT", f"/usuarios/{usr['id']}", {"nombre": "Usuario UI edit", "activo": True})
        print(f"  PUT usuario -> nombre={usr_up.get('nombre')}")
        if ses:
            st, cierre = call("POST", f"/auth/sesiones/{ses[0]['id']}/cerrar")
            print(f"  cerrar sesion {ses[0]['id']} -> {'ok' if isinstance(cierre, dict) else cierre}")
    else:
        print("  SKIP usuarios")

    print("== Lote 4: Ventas/Apartados/Restaurante/Offline/Domicilios ==")
    st, ventas = call("GET", "/ventas")
    if ventas:
        v0 = ventas[0]
        st, vdet = call("GET", f"/ventas/{v0['id']}")
        print(f"  GET /ventas/{v0['id']} -> {vdet['numero']} saldo={vdet.get('saldo')} pagos={len(vdet.get('pagos') or [])}")
        if vdet.get("estado") == "credito" and float(vdet.get("saldo") or 0) > 0:
            st, abono = call("POST", f"/ventas/{v0['id']}/pagos", {"medio": "efectivo", "monto": 1000})
            print(f"  POST abono -> medio={abono.get('medio')} monto={abono.get('monto')}")
        else:
            print("  SKIP abono (venta no es credito con saldo)")
    st, aparts = call("GET", "/apartados")
    if aparts:
        st, apt = call("GET", f"/apartados/{aparts[0]['id']}")
        print(f"  GET apartado/{aparts[0]['id']} -> estado={apt.get('estado')} abonado={apt.get('abonado')} detalle={len(apt.get('detalle') or [])}")
    else:
        print("  SKIP apartados")
    st, comandas = call("GET", "/restaurante/comandas")
    if comandas:
        st, cmd = call("GET", f"/restaurante/comandas/{comandas[0]['id']}")
        print(f"  GET comanda/{comandas[0]['id']} -> estado={cmd.get('estado')} mesa={cmd.get('mesa_id')} detalle={len(cmd.get('detalle') or [])}")
    else:
        print("  SKIP comandas")
    st, pends = call("GET", "/offline/pendientes")
    print(f"  GET offline/pendientes -> {len(pends)}")
    if pends:
        st, sinc = call("POST", f"/offline/pendientes/{pends[0]['id']}/sincronizar")
        print(f"  POST sincronizar {pends[0]['id']} -> {sinc if isinstance(sinc, dict) else 'ok'}")
    st, rutas = call("GET", "/domicilios/rutas")
    print(f"  GET domicilios/rutas -> {len(rutas)}")
    st, ruta = call("POST", "/domicilios/rutas", {"empresa_id": 1, "sucursal_id": 1, "nombre": "Ruta UI" + suf, "tarifa": 3000})
    print(f"  POST ruta -> {ruta.get('id')} {ruta.get('nombre')} tarifa={ruta.get('tarifa')}")
    st, reps = call("GET", "/domicilios/repartidores")
    if not reps:
        st, rep = call("POST", "/domicilios/repartidores", {"empresa_id": 1, "sucursal_id": 1, "nombre": "Repartidor UI" + suf, "telefono": "3001234567", "vehiculo": "moto"})
        print(f"  POST repartidor -> {rep.get('id')} {rep.get('nombre')} {rep.get('vehiculo')}")
        reps = [rep]
    if reps:
        rid = reps[0]["id"]
        st, rep_est = call("POST", f"/domicilios/repartidores/{rid}/estado?disponible=disponible")
        print(f"  estado repartidor -> disponible={rep_est.get('disponible')}")
        st, rep_gps = call("GET", f"/domicilios/repartidores/{rid}/gps")
        print(f"  GET gps repartidor -> {rep_gps}")
    st, orders = call("GET", "/pedidos")
    print(f"  GET pedidos -> {len(orders)}")
    if orders:
        o0 = orders[0]
        st, otr = call("GET", f"/domicilios/pedidos/{o0['id']}/tracking")
        print(f"  GET tracking pedido {o0['id']} -> {len(otr) if isinstance(otr, list) else otr}")
        st, ogps = call("POST", f"/domicilios/pedidos/{o0['id']}/gps", {"lat": 4.710989, "lng": -74.072092})
        print(f"  POST gps pedido -> {ogps if isinstance(ogps, dict) else 'ok'}")
        st, odet = call("GET", f"/pedidos/{o0['id']}")
        print(f"  GET /pedidos/{o0['id']} -> estado={odet.get('estado')} repartidor_id={odet.get('repartidor_id')}")

    print("== Lote 5: Inventario/Productos/Cartera-Acuerdos/Reportes/Integraciones ==")
    st, prod = call("GET", "/productos")
    if prod:
        pid = prod[0]["id"]
        st, costo = call("POST", f"/productos/{pid}/costear", body={})
        print(f"  POST costear {pid} -> costo_anterior={costo.get('costo_anterior')} costo_calculado={costo.get('costo_calculado')} margen={costo.get('margen_pct')}")
    st, stk = call("GET", "/inventario/stock")
    print(f"  GET inventario -> {len(stk)}")
    if stk:
        pin = stk[0]
        st, detal = call("GET", f"/inventario/producto/{pin['producto_id']}?sucursal_id=1")
        print(f"  GET inv producto/{pin['producto_id']} -> sucursales={len(detal) if isinstance(detal, list) else detal}")
        st, ajuste = call("POST", "/inventario/ajustar", {"producto_id": pin["producto_id"], "sucursal_id": 1, "existencias": float(pin.get("existencias") or 0), "motivo": "Ajuste smoke UI"})
        print(f"  POST ajustar -> {'ok' if isinstance(ajuste, dict) and 'producto_id' in ajuste else ajuste}")
        if len(stk) > 1:
            st, trf = call("POST", "/inventario/transferir", {"producto_id": pin["producto_id"], "origen_sucursal_id": 1, "destino_sucursal_id": 2, "cantidad": 1, "motivo": "Transferencia smoke UI"})
            print(f"  POST transferir -> {trf if isinstance(trf, dict) else 'ok'}")
    st, acuerdos = call("GET", "/acuerdos-pago")
    if acuerdos:
        st, ac = call("GET", f"/acuerdos-pago/{acuerdos[0]['id']}")
        print(f"  GET acuerdos-pago/{acuerdos[0]['id']} -> estado={ac.get('estado')} cuotas={len(ac.get('cuotas') or [])}")
    else:
        print("  SKIP acuerdos-pago")
    st, r1 = call("GET", "/reportes/compras-por-sucursal")
    print(f"  GET compras-por-sucursal -> {len(r1)}")
    st, r2 = call("GET", "/reportes/inventario-por-sucursal")
    print(f"  GET inventario-por-sucursal -> {len(r2)}")
    st, r3 = call("GET", "/reportes/inventario-por-bodega")
    print(f"  GET inventario-por-bodega -> {len(r3)}")
    st, r4 = call("GET", "/reportes/proveedores-principales?limite=5")
    print(f"  GET proveedores-principales -> {len(r4)}")
    st, r5 = call("GET", "/reportes/productos-por-proveedor")
    print(f"  GET productos-por-proveedor -> {len(r5)}")
    st, provl = call("GET", "/proveedores")
    if provl:
        prov_id = provl[0]["id"]
        st, r6 = call("GET", f"/reportes/precios-proveedor/{prov_id}")
        print(f"  GET precios-proveedor/{prov_id} -> {len(r6)}")
        st, r7 = call("GET", f"/reportes/proveedores-historial/{prov_id}")
        print(f"  GET proveedores-historial/{prov_id} -> compras={r7.get('numero_compras')} deuda={r7.get('deuda_pendiente')}")
    st, tasas = call("POST", "/monedas", {"empresa_id": 1, "codigo": "USDT", "nombre": "Tether UI" + suf, "simbolo": "₮", "tasa_cambio": 4100, "activa": True})
    print(f"  POST moneda -> {tasas.get('id')} {tasas.get('codigo')} tasa={tasas.get('tasa_cambio')}")
    st, tasu = call("PUT", f"/monedas/{tasas['id']}", {"empresa_id": 1, "codigo": tasas["codigo"], "tasa_cambio": 4200, "activa": True})
    print(f"  PUT moneda -> tasa={tasu.get('tasa_cambio')}")
    st, trains = call("GET", "/pagos/tarjeta")
    print(f"  GET pagos/tarjeta -> {len(trains)}")
    st, docx = call("GET", "/facturacion/documentos")
    if docx:
        d0 = next((d for d in docx if not d["anulado"]), docx[0])
        st, en = call("POST", f"/facturacion/{d0['id']}/enviar")
        print(f"  enviar documento {d0['id']} -> estado={en.get('estado_dian')}")
        st, co = call("POST", f"/facturacion/{d0['id']}/consultar")
        print(f"  consultar documento -> estado={co.get('estado_dian')}")
    else:
        print("  SKIP facturacion acciones")

    print("SMOKE OK")


if __name__ == "__main__":
    main()