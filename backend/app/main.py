from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import get_session
from .models import Empresa, ErrorLog, Usuario
from .plan import RUTA_MODULO, calcular_modulos

import jwt as pyjwt

from .routers import (
    acuerdos,
    apartados,
    auth,
    caja,
    cartera,
    compras,
    configuracion,
    devoluciones,
    domicilios,
    etiquetas,
    facturacion,
    fidelizacion,
    importar,
    integraciones,
    inventario,
    offline,
    organizacion,
    pagos,
    pantalla,
    pedidos,
    personas,
    produccion,
    productos,
    promociones,
    publico,
    recetas,
    reportes,
    restaurante,
    seguridad,
    sistema,
    usuarios,
    vendedores,
    ventas,
)

app = FastAPI(
    title="POS - Sistema de Punto de Venta",
    description="API del núcleo funcional del sistema POS (MVP)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def exigir_cambio_de_password(request: Request, call_next):
    """Bloquea el acceso a la app mientras el usuario tenga password pendiente de cambio
    o el negocio no tenga habilitado el módulo de la ruta solicitada."""
    publicos = ("/", "/docs", "/redoc", "/openapi.json", "/favicon.ico")
    if request.url.path.startswith("/auth/") or request.url.path in publicos:
        return await call_next(request)
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        try:
            payload = pyjwt.decode(
                header[7:].strip(),
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
            db = get_session()
            try:
                usuario = db.get(Usuario, int(payload.get("sub")))
                if not usuario or not usuario.activo:
                    return await call_next(request)
                if usuario.debe_cambiar_password:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Debe cambiar la contraseña"},
                    )
                modulo = next(
                    (m for prefijo, m in RUTA_MODULO.items() if request.url.path.startswith(prefijo)),
                    None,
                )
                if modulo:
                    empresa = db.get(Empresa, usuario.empresa_id)
                    if not empresa:
                        empresa = db.query(Empresa).first()
                    if empresa and modulo not in calcular_modulos(empresa, db):
                        return JSONResponse(
                            status_code=403,
                            content={"detail": f"Módulo '{modulo}' no habilitado para este negocio"},
                        )
            finally:
                db.close()
        except Exception:
            pass
    return await call_next(request)


@app.get("/")
def root():
    return {"message": "POS API funcionando", "docs": "/docs"}


app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(organizacion.router)
app.include_router(pagos.router)
app.include_router(offline.router)
app.include_router(pantalla.router)
app.include_router(productos.router)
app.include_router(inventario.router)
app.include_router(personas.router)
app.include_router(ventas.router)
app.include_router(caja.router)
app.include_router(compras.router)
app.include_router(cartera.router)
app.include_router(devoluciones.router)
app.include_router(facturacion.router)
app.include_router(fidelizacion.router)
app.include_router(apartados.router)
app.include_router(pedidos.router)
app.include_router(restaurante.router)
app.include_router(domicilios.router)
app.include_router(seguridad.router)
app.include_router(configuracion.router)
app.include_router(promociones.router)
app.include_router(vendedores.router)
app.include_router(importar.router)
app.include_router(reportes.router)
app.include_router(produccion.router)
app.include_router(recetas.router)
app.include_router(acuerdos.router)
app.include_router(etiquetas.router)
app.include_router(integraciones.router)
app.include_router(sistema.router)
app.include_router(publico.router)


@app.on_event("startup")
def _arrancar_servicios():
    from .wa import iniciar_scheduler

    iniciar_scheduler()


@app.exception_handler(Exception)
async def error_global_handler(request: Request, exc: Exception):
    try:
        db = get_session()
        db.add(
            ErrorLog(
                modulo=(request.url.path or "/").split("/")[1] if request.url.path else None,
                endpoint=str(request.url.path),
                metodo=request.method,
                mensaje=str(exc)[:2000],
                resuelto=False,
            )
        )
        db.commit()
    except Exception:
        pass
    finally:
        db.close()
    from fastapi.responses import JSONResponse

    detalle = f"Error interno: {exc}" if settings.DEBUG else "Error interno del servidor"
    return JSONResponse(status_code=500, content={"detail": detalle})
