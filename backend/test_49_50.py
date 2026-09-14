import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from fastapi.testclient import TestClient
from app.main import app

C = TestClient(app)
r = C.post("/auth/login", json={"username": "admin", "password": "admin123"})
H = {"Authorization": f"Bearer {r.json()['access_token']}"}

# 49 maneja_serie
r = C.post("/productos", headers=H, json={
    "empresa_id": 1, "nombre": "Prod Serie 21", "tipo": "unidad",
    "maneja_serie": True, "precio_venta": 500})
assert r.status_code == 201, r.text
pid = r.json()["id"]
assert r.json()["maneja_serie"] is True, r.json()
r = C.get(f"/productos/{pid}", headers=H)
assert r.status_code == 200 and r.json()["maneja_serie"] is True, r.text

# 50 imagen
r = C.post("/productos", headers=H, json={
    "empresa_id": 1, "nombre": "Prod Imagen 21", "tipo": "unidad",
    "imagen": "data:image/png;base64,aG9sYQ==", "precio_venta": 500})
assert r.status_code == 201, r.text
pid2 = r.json()["id"]
assert r.json()["imagen"] == "data:image/png;base64,aG9sYQ==", r.json()
r = C.get(f"/productos/{pid2}", headers=H)
assert r.status_code == 200 and r.json()["imagen"] == "data:image/png;base64,aG9sYQ==", r.text

# update por PUT
r = C.put(f"/productos/{pid2}", headers=H, json={"maneja_serie": True})
assert r.status_code == 200 and r.json()["maneja_serie"] is True, r.text

print("49 serie y 50 imagen: OK")