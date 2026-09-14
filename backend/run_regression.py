import subprocess, sys, os
env = dict(os.environ)
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONPATH"] = "."
suites = [("avanzado_inventario", "test_avanzado_inventario.py")]
suites += [(s, f"test_{s}.py") for s in ["caja_turnos", "especial", "fase2", "fase3", "fase4", "fase6", "offline", "pagos_tarjeta", "recetas", "ventas"]]
failed = []
for name, fname in suites:
    r = subprocess.run([sys.executable, fname], capture_output=True, text=True, env=env)
    status = "PASS" if r.returncode == 0 else "FAIL"
    if r.returncode != 0:
        failed.append(name)
        print(f"{name}: FAIL")
        print(f"  stderr tail: {r.stderr[-300:]}")
    else:
        print(f"{name}: PASS")
print("EXIT:", 1 if failed else 0)
print("FAILED:", failed)