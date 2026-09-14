"""Direccionamiento a la base de datos editable desde el aplicativo.

La dirección NO puede vivir dentro de la propia base de datos (la app la
necesita antes de poder conectarse). Se guarda en un archivo JSON dentro de
un volumen montado en el servidor principal. Si el archivo no existe, se usa
el valor de entorno configurado (DATABASE_URL).
"""
import json
import os
from urllib.parse import quote_plus

from sqlalchemy.engine import make_url

from .config import settings

RUTA = os.environ.get("DIRECCIONAMIENTO_FILE", "/app/datos/direccionamiento.json")


def leer() -> dict:
    try:
        with open(RUTA, encoding="utf-8") as f:
            dato = json.load(f)
        return dato if isinstance(dato, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def guardar(dato: dict) -> None:
    directorio = os.path.dirname(RUTA)
    if directorio:
        os.makedirs(directorio, exist_ok=True)
    with open(RUTA, "w", encoding="utf-8") as f:
        json.dump(dato, f, ensure_ascii=False, indent=2)


def _normalizar(d: dict) -> dict:
    return {
        "dialecto": (d.get("dialecto") or "mssql").lower(),
        "host": str(d.get("host") or "localhost").strip() or "localhost",
        "puerto": int(d.get("puerto") or 1433),
        "base": str(d.get("base") or "posdb").strip() or "posdb",
        "usuario": str(d.get("usuario") or "sa").strip() or "sa",
        "password": str(d.get("password") or ""),
        "driver": str(d.get("driver") or "ODBC Driver 18 for SQL Server").strip()
        or "ODBC Driver 18 for SQL Server",
    }


def url_desde_dato(d: dict) -> str:
    d = _normalizar(d)
    dialecto = d["dialecto"]
    if dialecto not in ("mssql", "sqlserver"):
        raise ValueError(f"Motor de base de datos no soportado: {dialecto}")
    return (
        f"mssql+pyodbc://{quote_plus(d['usuario'])}:"
        f"{quote_plus(d['password'])}@{d['host']}:{d['puerto']}/{quote_plus(d['base'])}"
        f"?driver={quote_plus(d['driver'])}&TrustServerCertificate=yes"
    )


def url_efectiva() -> str:
    """URL que debe usar la app: el archivo de direccionamiento si existe, si no el entorno."""
    dato = leer()
    if dato and dato.get("host") and dato.get("base") and dato.get("usuario"):
        try:
            return url_desde_dato(dato)
        except Exception:
            pass
    return settings.database_url()


def usuario_guardado(datos: dict) -> str:
    """Cuando el usuario no se indica, se conserva el guardado o el de la conexión actual."""
    prev = leer()
    if prev and str(prev.get("host")) == str(datos.get("host")) and str(prev.get("base")) == str(datos.get("base")):
        return str(prev.get("usuario") or "")
    try:
        url = make_url(url_efectiva())
        if (url.host or "") == str(datos.get("host")) and (url.database or "") == str(datos.get("base")):
            return url.username or ""
    except Exception:
        pass
    return "sa"


def password_guardado_o_heredado(datos: dict) -> str:
    """Cuando el usuario no escribe contraseña, se conserva la guardada/actual."""
    prev = leer()
    if prev and all(
        str(prev.get(k)) == str(datos.get(k))
        for k in ("host", "puerto", "base", "usuario")
        if k in datos
    ):
        return prev.get("password") or ""
    try:
        url = make_url(url_efectiva())
        coincide = (
            (url.host or "") == str(datos.get("host"))
            and (url.port or 0) == int(datos.get("puerto") or 0)
            and (url.database or "") == str(datos.get("base"))
            and (url.username or "") == str(datos.get("usuario"))
        )
        if coincide:
            return url.password or ""
    except Exception:
        pass
    return ""
