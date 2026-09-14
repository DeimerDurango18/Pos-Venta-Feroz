from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, declarative_base

from . import direccionamiento as dirmod


def _crear(url):
    return create_engine(url, pool_pre_ping=True)


engine = _crear(dirmod.url_efectiva())
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session():
    return SessionLocal()


def get_engine():
    return engine


def reconectar(url: str) -> dict:
    """Conecta a una nueva URL y, si es válida, la adopta como conexión activa."""
    global engine, SessionLocal
    nuevo = _crear(url)
    with nuevo.connect() as c:
        c.execute(text("SELECT 1"))
    viejo = engine
    engine = nuevo
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    try:
        viejo.dispose()
    except Exception:
        pass
    u = make_url(url)
    return {
        "razon": "ok",
        "dialecto": nuevo.dialect.name or "desconocido",
        "host": u.host,
        "puerto": u.port or 0,
        "base": u.database or "",
        "usuario": u.username or "",
    }