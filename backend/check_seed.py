from app.database import engine
from sqlalchemy import text

def q(conn, sql):
    try:
        return conn.execute(text(sql)).fetchall()
    except Exception as e:
        return f"ERR {type(e).__name__}"

with engine.connect() as conn:
    r = q(conn, "SELECT id, nombre, activo FROM proveedores ORDER BY id LIMIT 3")
    print("proveedores:", r)
    conn.rollback()
    r = q(conn, "SELECT id, nombre FROM clientes ORDER BY id LIMIT 2")
    print("clientes:", r)
    conn.rollback()
    r = q(conn, "SELECT id, prefijo, activa, empresa_id FROM resoluciones_facturacion ORDER BY id LIMIT 5")
    print("resoluciones:", r)
    conn.rollback()
    r = q(conn, "SELECT id, codigo FROM sucursales ORDER BY id LIMIT 5")
    print("sucursales:", r)
    conn.rollback()
    r = q(conn, "SELECT id, nombre, activo, empresa_id FROM categorias ORDER BY id LIMIT 3")
    print("categorias:", r)
    conn.rollback()
    r = q(conn, "SELECT id, nombre, precio_venta, activo, empresa_id FROM productos ORDER BY id LIMIT 3")
    print("productos:", r)