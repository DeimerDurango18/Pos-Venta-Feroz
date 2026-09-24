"""Panel de estado público del servicio para monitoreo y página de estado.

Devuelve solo datos operativos curados (nunca rutas internas, resúmenes
concurrentes ni secretos). Pensado para un health check externo y para la
página pública de estado del producto (Bloque 6.6 del plan de despliegue).
"""
from fastapi import APIRouter

from .. import telemetria
from ..dian import estado_integracion_dian

router = APIRouter(tags=["estado"])


@router.get("/estado")
def estado_servicio():
    """Estado operativo del servicio, sin datos sensibles ni de negocio."""
    tele = telemetria.resumen()
    dian = estado_integracion_dian(db=None)

    return {
        "ok": True,
        "servicio": "pos-api",
        "uptime_seg": tele["uptime_seg"],
        "requests": {
            "total": tele["total"],
            "p50_ms": tele["resumen"]["p50_ms"],
            "p95_ms": tele["resumen"]["p95_ms"],
            "lentos": len(tele["lentos"]),
        },
        "dian": {
            "modo": dian["modo"],
            "conector": dian["conector"],
            "puede_transmitir": dian["puede_transmitir"],
            "configurado": dian["configurado"],
        },
        "dependencias": {},
        "mensaje": "Servicio operativo",
    }