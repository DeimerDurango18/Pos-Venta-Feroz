from app.database import SessionLocal, engine
from sqlalchemy import text

with engine.connect() as conn:
    r = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE '%factur%' OR tablename LIKE '%resolucion%' ORDER BY 1")).fetchall()
    print("fact tables:", [x[0] for x in r])
    r = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1")).fetchall()
    print("all tables:", [x[0] for x in r])