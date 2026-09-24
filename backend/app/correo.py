import json
import os
import re
import smtplib
import ssl
from email.message import EmailMessage

from .models import Configuracion


def correo_config(db):
    """Config SMTP desde la BD (pos.correo) con respaldo por variables de entorno."""
    cfg = {}
    fila = db.query(Configuracion).filter(Configuracion.clave == "pos.correo").first()
    if fila and fila.valor:
        try:
            cfg = json.loads(fila.valor) or {}
        except ValueError:
            cfg = {}
    env = {
        "servidor": os.environ.get("SMTP_HOST", ""),
        "puerto": os.environ.get("SMTP_PORT", ""),
        "usuario": os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "desde": os.environ.get("MAIL_FROM", ""),
        "tls": os.environ.get("SMTP_TLS", "1") != "0",
    }
    for k, v in env.items():
        if v not in (None, ""):
            cfg[k] = v
    return cfg


def url_publica(db):
    """URL pública del sistema para enlaces (pos.correo.url_publica) con respaldo env."""
    cfg = correo_config(db)
    return (cfg.get("url_publica") or os.environ.get("URL_PUBLICA") or "").strip()


def enviar_correo(db, para, asunto, html, texto_plano=None):
    """Envía un correo HTML por SMTP. Devuelve {'ok': bool, 'error': str|None}."""
    cfg = correo_config(db)
    servidor = (cfg.get("servidor") or "").strip()
    usuario = (cfg.get("usuario") or "").strip()
    desde = (cfg.get("desde") or usuario or "").strip()
    password = cfg.get("password") or ""
    if not servidor or not desde:
        return {"ok": False, "error": "SMTP no configurado"}
    try:
        puerto = int(cfg.get("puerto") or 587)
    except (TypeError, ValueError):
        puerto = 587
    tls = bool(cfg.get("tls", True))

    msg = EmailMessage()
    msg["From"] = desde
    msg["To"] = para
    msg["Subject"] = asunto
    msg.set_content(texto_plano or re.sub(r"<[^>]+>", " ", html).strip())
    msg.add_alternative(html, subtype="html")

    servidor_smtp = None
    try:
        if tls:
            servidor_smtp = smtplib.SMTP(servidor, puerto, timeout=20)
            servidor_smtp.starttls(context=ssl.create_default_context())
        else:
            servidor_smtp = smtplib.SMTP_SSL(servidor, puerto, timeout=20)
        if usuario and password:
            servidor_smtp.login(usuario, password)
        servidor_smtp.send_message(msg)
        servidor_smtp.quit()
        return {"ok": True, "error": None}
    except Exception as e:  # noqa: BLE001
        try:
            if servidor_smtp:
                servidor_smtp.close()
        except Exception:  # noqa: BLE001
            pass
        return {"ok": False, "error": str(e)}