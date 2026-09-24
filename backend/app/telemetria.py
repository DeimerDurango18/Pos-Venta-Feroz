import threading
import time
from collections import defaultdict, deque

_tiempo_lento_ms = 2000
_historial_ms = 500

_lock = threading.Lock()
_arranque = time.time()
_total = 0
_por_estado = defaultdict(int)
_rutas = {}
_lentos = deque(maxlen=100)


def _clave_ruta(request):
    route = request.scope.get("route")
    if route and getattr(route, "path", None):
        return route.path
    return request.url.path or "/"


def registrar(metodo, ruta, status, ms):
    global _total
    with _lock:
        _total += 1
        _por_estado[status] += 1
        entrada = _rutas.setdefault((metodo, ruta), {"count": 0, "errores": 0, "tiempos": deque(maxlen=_historial_ms), "max_ms": 0})
        entrada["count"] += 1
        entrada["max_ms"] = max(entrada["max_ms"], ms)
        entrada["tiempos"].append(ms)
        if status >= 400:
            entrada["errores"] += 1
        if ms >= _tiempo_lento_ms:
            _lentos.appendleft({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "metodo": metodo, "ruta": ruta, "ms": ms, "status": status})


def resumen():
    with _lock:
        total = _total
        por_estado = dict(_por_estado)
        rutas = []
        for (metodo, ruta), e in _rutas.items():
            tiempos = sorted(e["tiempos"])
            p50 = tiempos[len(tiempos) // 2] if tiempos else 0
            p95 = tiempos[min(len(tiempos) - 1, int(len(tiempos) * 0.95))] if tiempos else 0
            avg = sum(tiempos) / len(tiempos) if tiempos else 0
            rutas.append({
                "metodo": metodo,
                "ruta": ruta,
                "count": e["count"],
                "avg_ms": round(avg, 1),
                "p50_ms": p50,
                "p95_ms": p95,
                "max_ms": e["max_ms"],
                "errores": e["errores"],
            })
        rutas.sort(key=lambda r: -r["count"])
        todos = sorted(
            ms
            for (_, _r), e in _rutas.items()
            for ms in e["tiempos"]
        )
        p50t = todos[len(todos) // 2] if todos else 0
        p95t = todos[min(len(todos) - 1, int(len(todos) * 0.95))] if todos else 0
        avgt = sum(todos) / len(todos) if todos else 0
        return {
            "uptime_seg": int(time.time() - _arranque),
            "total": total,
            "por_estado": por_estado,
            "resumen": {"count": len(todos), "p50_ms": p50t, "p95_ms": p95t, "avg_ms": round(avgt, 1), "max_ms": max(todos) if todos else 0},
            "umbral_lento_ms": _tiempo_lento_ms,
            "rutas": rutas,
            "lentos": list(_lentos),
        }


def reiniciar():
    global _total, _arranque
    with _lock:
        _total = 0
        _arranque = time.time()
        _por_estado.clear()
        _rutas.clear()
        _lentos.clear()