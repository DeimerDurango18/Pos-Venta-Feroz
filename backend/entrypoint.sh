#!/bin/sh
set -e

echo "Esperando SQL Server en ${DB_HOST}:${DB_PORT}..."
python - <<'PY'
import os, sys, time
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.direccionamiento import url_efectiva

url = make_url(url_efectiva())
servidor = url.set(database="master")

for i in range(90):
    try:
        eng = create_engine(servidor, connect_args={"timeout": 3})
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
        print("SQL Server accesible.")
        break
    except Exception as e:
        if i % 5 == 0:
            print("esperando SQL Server...", str(e)[:140])
        time.sleep(2)
else:
    print("No se pudo conectar a SQL Server.")
    exit(1)

dbname = url.database or "posdb"
c = eng.connect().execution_options(isolation_level="AUTOCOMMIT")
with c:
    c.execute(text(f"IF DB_ID('{dbname}') IS NULL EXEC('CREATE DATABASE {dbname}')"))
print(f"Base de datos '{dbname}' lista.")
PY

echo "Ejecutando init_db.py (crear tablas + datos iniciales)..."
python init_db.py

echo "Preparando esquema con Alembic..."
python - <<'PY'
import subprocess
import sys
from sqlalchemy import text
from app.database import engine

# Base creada por create_all (instalaciones existentes): sellar la baseline.
# Base gestionada por Alembic (tiene alembic_version): aplicar migraciones pendientes.
with engine.connect() as c:
    existe = c.execute(
        text("SELECT 1 FROM sys.tables WHERE name='alembic_version' AND schema_id = SCHEMA_ID('dbo')")
    ).first()
cmd = ["alembic", "stamp", "head"] if not existe else ["alembic", "upgrade", "head"]
print("Ejecutando:", " ".join(cmd))
sys.exit(subprocess.call(cmd))
PY

echo "Iniciando API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000