import json, os, re, urllib.request

with urllib.request.urlopen("http://127.0.0.1:28743/openapi.json", timeout=20) as r:
    spec = json.load(r)

paths = spec["paths"]
src_dir = r"C:\Users\DORADO\Documents\Default Project\frontend\src"
sources = []
for root, _, files in os.walk(src_dir):
    for f in files:
        if f.endswith((".js", ".jsx", ".ts")):
            p = os.path.join(root, f)
            with open(p, encoding="utf-8", errors="ignore") as fh:
                sources.append(fh.read())
all_src = "\n".join(sources)


def used_by_frontend(path):
    segs = []
    for part in path.strip("/").split("/"):
        if part.startswith("{"):
            segs.append(r"\$?\{[^/]{0,60}")
        else:
            segs.append(re.escape(part))
    pat = re.compile("/" + "/".join(segs) + r'(?=["\'`),;?\s]|$)')
    return bool(pat.search(all_src))


orphans = []
for path, methods in paths.items():
    for m in methods:
        if m.upper() not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            continue
        if not used_by_frontend(path):
            orphans.append((m.upper(), path))

# Rutas que el frontend construye con variables dinámicas (verificadas manualmente):
#  - Compras.jsx: /compras/ordenes/${id}/${accion}  (accion = aprobar|cancelar|recibir)
#  - Configuracion.jsx: /configuracion/dispositivos/${bloque} (PUT)
#  - Productos.jsx: /etiquetas/${tipo} (gondola|productos)
#  - Facturacion.jsx: accion() -> /facturacion/{id}/enviar|consultar|reintentar|anular|correo|whatsapp
#  - Inventario.jsx: /inventario/lotes/${tipo}, /inventario/transito/${id}/${accion}
#  - Seguridad.jsx: /seguridad/autorizaciones + resolver(${autorizacion_id}, ${accion})
#  - Sistema.jsx: /sistema/errores
DINAMICAS_VERIFICADAS = {
    ("POST", "/compras/ordenes/{orden_id}/aprobar"),
    ("POST", "/compras/ordenes/{orden_id}/cancelar"),
    ("POST", "/compras/ordenes/{orden_id}/recibir"),
    ("PUT", "/configuracion/dispositivos/cajon"),
    ("PUT", "/configuracion/dispositivos/correo"),
    ("PUT", "/configuracion/dispositivos/factura"),
    ("PUT", "/configuracion/dispositivos/impresoras"),
    ("PUT", "/configuracion/dispositivos/lector"),
    ("PUT", "/configuracion/dispositivos/terminal"),
    ("GET", "/etiquetas/gondola"),
    ("GET", "/etiquetas/productos"),
    ("POST", "/facturacion/{doc_id}/anular"),
    ("POST", "/facturacion/{doc_id}/consultar"),
    ("POST", "/facturacion/{doc_id}/correo"),
    ("POST", "/facturacion/{doc_id}/enviar"),
    ("POST", "/facturacion/{doc_id}/reintentar"),
    ("POST", "/facturacion/{doc_id}/whatsapp"),
    ("POST", "/inventario/lotes/salida"),
    ("POST", "/inventario/lotes/stock"),
    ("POST", "/inventario/transito/{transferencia_id}/cancelar"),
    ("POST", "/inventario/transito/{transferencia_id}/recibir"),
    ("GET", "/seguridad/autorizaciones"),
    ("POST", "/seguridad/autorizaciones/{autorizacion_id}/aprobar"),
    ("POST", "/seguridad/autorizaciones/{autorizacion_id}/rechazar"),
    ("GET", "/sistema/errores"),
}
reales = [(m, p) for m, p in orphans if (m, p) not in DINAMICAS_VERIFICADAS]
dinamicas = [(m, p) for m, p in orphans if (m, p) in DINAMICAS_VERIFICADAS]

total = sum(1 for v in paths.values() for m in v if m.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE"))
print(f"Total rutas: {total}, Huérfanas reales: {len(reales)}, Dinámicas verificadas: {len(dinamicas)}")
import collections
grupos = collections.defaultdict(list)
for m, p in reales:
    grupos[p.strip("/").split("/")[0]].append(f"{m:6} {p}")
for g, items in sorted(grupos.items()):
    print(f"\n# {g} ({len(items)})")
    for i in sorted(items):
        print("  " + i)
if dinamicas and not reales:
    print("\n(las únicas huérfanas pendientes son dinámicas ya cableadas — reporte limpio)")