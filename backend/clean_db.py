from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
def run(sql):
    try:
        db.execute(text(sql)); db.commit()
        return True
    except Exception as e:
        print(f"  skip: {sql[:50]} -> {type(e).__name__}")
        db.rollback()
        return False

def bd_ids():
    return db.execute(text("SELECT id FROM bodegas WHERE sucursal_id IN (SELECT id FROM sucursales WHERE codigo LIKE 'SUC-AI-%')")).scalars().all()
def suc_ids():
    return db.execute(text("SELECT id FROM sucursales WHERE codigo LIKE 'SUC-AI-%'")).scalars().all()

def inlist(ids):
    return "(" + ",".join(str(i) for i in ids) + ")"

bd = bd_ids(); sc = suc_ids()
print("bodegas SUC-AI:", bd, "sucursales SUC-AI:", sc)

if bd:
    run(f"DELETE FROM ubicaciones WHERE bodega_id IN {inlist(bd)}")
    run(f"DELETE FROM inventario_transito WHERE origen_bodega_id IN {inlist(bd)} OR destino_bodega_id IN {inlist(bd)}")
    run(f"DELETE FROM stock_bodega WHERE bodega_id IN {inlist(bd)}")
    run(f"DELETE FROM bodegas WHERE id IN {inlist(bd)}")

if sc:
    run(f"DELETE FROM stock WHERE sucursal_id IN {inlist(sc)}")
    run(f"DELETE FROM movimientos_inventario WHERE sucursal_id IN {inlist(sc)}")
    run("DELETE FROM sucursales WHERE codigo LIKE 'SUC-AI-%'")

print("sucursales:", db.execute(text("SELECT COUNT(*) FROM sucursales")).scalar())
print("bodegas:", db.execute(text("SELECT COUNT(*) FROM bodegas")).scalar())
print("stock:", db.execute(text("SELECT COUNT(*) FROM stock")).scalar())
db.close()