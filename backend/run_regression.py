"""Regresión integral. SIEMPRE recrea y siembra posdb_test desde cero al iniciar."""
import os
import subprocess
import sys

base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base)

os.environ["DB_NAME"] = "posdb_test"
os.environ["PYTHONIOENCODING"] = "utf-8"

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.config import settings  # noqa: E402
from app.direccionamiento import url_efectiva  # noqa: E402

env = dict(os.environ)
env["PYTHONPATH"] = base


def py(args, capture=False):
    if capture:
        return subprocess.run([sys.executable, "-X", "utf8", *args], capture_output=True, text=True, env=env)
    return subprocess.run([sys.executable, "-X", "utf8", *args], env=env)


print("=== Preparando posdb_test (limpia) ===")
url = make_url(url_efectiva())
master = url.set(database="master")
eng = create_engine(master)
with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
    c.execute(text("IF DB_ID('posdb_test') IS NOT NULL ALTER DATABASE posdb_test SET SINGLE_USER WITH ROLLBACK IMMEDIATE"))
    c.execute(text("IF DB_ID('posdb_test') IS NOT NULL DROP DATABASE posdb_test"))
    c.execute(text("CREATE DATABASE posdb_test"))
print("posdb_test recreada")

r = py(["init_db.py"])
if r.returncode != 0:
    print("init_db.py falló")
    sys.exit(1)
r = py(["-c", "from app.database import SessionLocal; from app.models import Usuario; db=SessionLocal(); db.query(Usuario).update({Usuario.debe_cambiar_password: False}); db.commit(); db.close(); print('seed ok')"])
if r.returncode != 0:
    print("seed falló")
    sys.exit(1)

print("\n=== Ejecutando suites ===")
suites = [("avanzado_inventario", "test_avanzado_inventario.py")]
suites += [(s, f"test_{s}.py") for s in ["caja_turnos", "cotizaciones", "especial", "fase2", "fase3", "fase4", "fase6", "offline", "pagos_tarjeta", "recetas", "ventas"]]
failed = []
for name, fname in suites:
    r = subprocess.run([sys.executable, "-X", "utf8", fname], capture_output=True, text=True, env=env)
    status = "PASS" if r.returncode == 0 else "FAIL"
    if r.returncode != 0:
        failed.append(name)
        print(f"{name}: FAIL")
        print(f"  stderr tail: {(r.stderr or '')[-300:]}")
    else:
        print(f"{name}: PASS")
print("\nEXIT:", 1 if failed else 0)
print("FAILED:", failed)