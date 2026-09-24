import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import text

from app.database import Base, SessionLocal, engine
from app.models import (
    Bodega,
    Caja,
    Configuracion,
    Empresa,
    Impuesto,
    ModeloNegocio,
    Permiso,
    Producto,
    Proveedor,
    PuntoVenta,
    Repartidor,
    ResolucionFacturacion,
    Rol,
    RutaEntrega,
    Sucursal,
    Ubicacion,
    Usuario,
    rol_permiso,
)
from app.security import hash_password
from app.routers.seguridad import BASE_CAJERO_PERMISOS, CATALOGO_PERMISOS


def _migrar(conn):
    """Aplica columnas nuevas sobre tablas existentes (create_all no altera).
    Soporta SQL Server."""
    columnas = [
        ("ventas", "saldo", "NUMERIC(12,2) DEFAULT 0"),
        ("ventas", "propina", "NUMERIC(12,2) DEFAULT 0"),
        ("productos", "impuesto", "NUMERIC(5,2) DEFAULT 0"),
        ("productos", "ficha_tecnica", "TEXT"),
        ("productos", "precio_institucional", "NUMERIC(12,2) DEFAULT 0"),
        ("productos", "margen_minimo", "NUMERIC(5,2) DEFAULT 0"),
        ("productos", "bloquear_venta_bajo_costo", "BOOLEAN DEFAULT FALSE"),
        ("promociones", "cliente_id", "INTEGER"),
        ("promociones", "cantidad_minima", "NUMERIC(12,3) DEFAULT 0"),
        ("conteos_fisicos", "tipo", "VARCHAR(30) DEFAULT 'fisico'"),
        ("usuarios", "debe_cambiar_password", "BOOLEAN DEFAULT FALSE"),
        ("empresas", "tipo_negocio", "VARCHAR(30) NOT NULL DEFAULT 'general'"),
        ("cajas", "es_principal", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("establecimientos", "modelo_negocio_id", "INTEGER"),
        ("comanda_detalle", "cortesia", "BOOLEAN DEFAULT FALSE"),
    ]
    dialecto = conn.dialect.name
    if not dialecto.startswith("mssql"):
        raise RuntimeError(f"Motor de base de datos no soportado: {dialecto}")
    mssql_tipos = {
        "BOOLEAN NOT NULL DEFAULT FALSE": "BIT NOT NULL DEFAULT 0",
        "BOOLEAN DEFAULT FALSE": "BIT DEFAULT 0",
        "TEXT": "NVARCHAR(MAX)",
        "INTEGER": "INT",
    }
    for tabla, col, tipo in columnas:
        for origen, destino in mssql_tipos.items():
            if tipo == origen:
                tipo = destino
                break
        existe = conn.execute(
            text(
                "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA=SCHEMA_NAME() AND TABLE_NAME=:t AND COLUMN_NAME=:c"
            ),
            {"t": tabla, "c": col},
        ).first()
        if not existe:
            conn.execute(text(f"ALTER TABLE {tabla} ADD {col} {tipo}"))


def _seed_modelos_negocio(db):
    from app.plan import MODULOS_TODOS

    if db.query(ModeloNegocio).count() > 0:
        return None
    todos = set(MODULOS_TODOS)
    modelos = [
        (1, "Restaurante", todos - {"apartados"}),
        (2, "Ventas / Ferretería", todos - {"restaurante", "domicilios", "apartados", "fidelizacion"}),
        (3, "Minimarket / Tienda", todos - {"restaurante", "domicilios", "apartados"}),
        (4, "Bar / Restobar", todos - {"apartados"}),
        (5, "Distribuidora / Mayorista", todos - {"restaurante", "domicilios", "fidelizacion"}),
        (6, "General / Completo", todos),
    ]
    for mid, nombre, modulos in modelos:
        db.add(
            ModeloNegocio(
                id=mid,
                nombre=nombre,
                descripcion=f"Modelo {mid}",
                modulos=json.dumps(sorted(modulos), ensure_ascii=False),
                activo=True,
            )
        )
    db.commit()
    print(f"Modelos de negocio creados ({len(modelos)}).")


def _seed_complementarios(db):
    """Datos complementarios: proveedor, impuestos, resolución, configs, bodega, repartidores, rutas."""
    emp = db.query(Empresa).order_by(Empresa.id).first()
    eid = emp.id if emp else 1
    if db.query(Proveedor).count() == 0:
        db.add(
            Proveedor(
                empresa_id=eid,
                nombre="Proveedor Demo S.A.S.",
                nit="901000000",
                contacto="Ventas",
                telefono="3180000000",
            )
        )
    if db.query(Impuesto).count() == 0:
        db.add(Impuesto(nombre="IVA 19%", tasa=19, activo=True))
        db.add(Impuesto(nombre="Exento", tasa=0, activo=True))
    if db.query(ResolucionFacturacion).count() == 0:
        db.add(
            ResolucionFacturacion(
                empresa_id=eid,
                resolucion="187600000001",
                prefijo="FV",
                tipo_documento="factura",
                rango_inicial=1,
                rango_final=100000,
                numero_actual=0,
                fecha_inicio=date.today(),
                fecha_vencimiento=date.today() + timedelta(days=365 * 5),
                activa=True,
            )
        )
    for clave, valor in (
        ("puntos_por_monto", "1000"),
        ("descuento_maximo_sin_autorizacion", "20000"),
    ):
        if not db.query(Configuracion).filter(Configuracion.clave == clave).first():
            db.add(Configuracion(clave=clave, valor=valor))
    for clave, valor in (
        ("pos.combos_consumen", "0"),
        ("pos.inventario_negativo", "0"),
        ("pos.meta_diaria", ""),
        ("pos.meta_mensual", ""),
        ("pos.cierres_correo", ""),
    ):
        if not db.query(Configuracion).filter(Configuracion.clave == clave).first():
            db.add(Configuracion(clave=clave, valor=valor))
    if db.query(Bodega).count() == 0:
        bodega = Bodega(
            empresa_id=eid,
            sucursal_id=1,
            nombre="Bodega Principal",
            codigo="BOD-001",
            direccion="Sucursal Principal",
            activa=True,
        )
        db.add(bodega)
        db.flush()
        db.add_all(
            [
                Ubicacion(bodega_id=bodega.id, nombre="Estantería A", codigo="EST-A"),
                Ubicacion(bodega_id=bodega.id, nombre="Estantería B", codigo="EST-B"),
            ]
        )
    if db.query(Repartidor).count() == 0:
        cajero = db.query(Usuario).filter(Usuario.username == "cajero").first()
        db.add_all(
            [
                Repartidor(
                    empresa_id=eid,
                    usuario_id=cajero.id if cajero else None,
                    nombre="Carlos Mendoza",
                    telefono="3181112233",
                    placa="RCY-123",
                    vehiculo="moto",
                    lat=4.6765,
                    lng=-74.0483,
                    disponible="disponible",
                    activo=1,
                ),
                Repartidor(
                    empresa_id=eid,
                    usuario_id=None,
                    nombre="Valentina Rojas",
                    telefono="3207654321",
                    placa="RWS-456",
                    vehiculo="bicicleta",
                    lat=4.6721,
                    lng=-74.0531,
                    disponible="disponible",
                    activo=1,
                ),
                Repartidor(
                    empresa_id=eid,
                    usuario_id=None,
                    nombre="Pedro Jiménez",
                    telefono="3109876543",
                    placa=None,
                    vehiculo="a pie",
                    lat=4.6802,
                    lng=-74.0445,
                    disponible="disponible",
                    activo=1,
                ),
            ]
        )
    if db.query(RutaEntrega).count() == 0:
        db.add_all(
            [
                RutaEntrega(empresa_id=eid, nombre="Zona Centro", tarifa=3000, detalle="Carrera 7 a Carrera 15, centro"),
                RutaEntrega(empresa_id=eid, nombre="Zona Norte", tarifa=5000, detalle="Calle 72 a Calle 100"),
                RutaEntrega(empresa_id=eid, nombre="Zona Sur", tarifa=7000, detalle="Avenida Villavicencio y alrededores"),
            ]
        )
    db.commit()
    print("Datos complementarios listos.")


def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        _migrar(conn)
    db = SessionLocal()
    try:
        _seed_modelos_negocio(db)
        if db.query(Empresa).count() == 0:
            forzar_cambio = os.environ.get("SEED_ADMIN_FORCE_CHANGE", "1") != "0"
            empresa = Empresa(
                nombre="Mi Empresa POS",
                nit="900000000",
                razon_social="Mi Empresa POS S.A.S.",
                regimen="simplificado",
            )
            db.add(empresa)
            db.flush()

            sucursal = Sucursal(
                empresa_id=empresa.id,
                nombre="Sucursal Principal",
                codigo="SUC-001",
                ciudad="Bogotá",
            )
            db.add(sucursal)
            db.flush()

            pv = PuntoVenta(
                sucursal_id=sucursal.id,
                nombre="Punto de Venta Principal",
                tipo="POS",
            )
            db.add(pv)
            db.flush()

            caja = Caja(
                punto_venta_id=pv.id,
                nombre="Caja 1",
                codigo="CAJA-001",
                saldo_inicial=50000,
            )
            db.add(caja)

            rol_admin = Rol(
                nombre="Administrador",
                descripcion="Acceso total al sistema",
                es_sistema=True,
            )
            db.add(rol_admin)
            db.flush()

            rol_cajero = Rol(
                nombre="Cajero",
                descripcion="Acceso a punto de venta",
                es_sistema=True,
            )
            db.add(rol_cajero)
            db.flush()

            admin_pass = os.environ.get("SEED_ADMIN_PASSWORD", "admin123")
            admin = Usuario(
                empresa_id=empresa.id,
                sucursal_id=sucursal.id,
                rol_id=rol_admin.id,
                nombre="Administrador",
                username="admin",
                email="admin@pos.com",
                password_hash=hash_password(admin_pass),
                activo=True,
                es_admin=True,
                vendedor=True,
                debe_cambiar_password=forzar_cambio,
            )
            db.add(admin)

            cajero_pass = os.environ.get("SEED_CAJERO_PASSWORD", "cajero123")
            cajero = Usuario(
                empresa_id=empresa.id,
                sucursal_id=sucursal.id,
                rol_id=rol_cajero.id,
                nombre="Cajero Demo",
                username="cajero",
                email="cajero@pos.com",
                password_hash=hash_password(cajero_pass),
                activo=True,
                es_admin=False,
                vendedor=True,
                debe_cambiar_password=forzar_cambio,
            )
            db.add(cajero)

            base_cajero = BASE_CAJERO_PERMISOS
            for modulo, accion, desc in CATALOGO_PERMISOS:
                permiso = db.query(Permiso).filter(Permiso.modulo == modulo, Permiso.accion == accion).first()
                if not permiso:
                    permiso = Permiso(modulo=modulo, accion=accion, descripcion=desc)
                    db.add(permiso)
                    db.flush()
                existe_admin = db.execute(
                    rol_permiso.select().where(
                        rol_permiso.c.rol_id == rol_admin.id, rol_permiso.c.permiso_id == permiso.id
                    )
                ).first()
                if not existe_admin:
                    db.execute(
                        rol_permiso.insert().values(rol_id=rol_admin.id, permiso_id=permiso.id)
                    )
            for permiso in db.query(Permiso).all():
                if (permiso.modulo, permiso.accion) in base_cajero:
                    existe = db.execute(
                        rol_permiso.select().where(
                            rol_permiso.c.rol_id == rol_cajero.id,
                            rol_permiso.c.permiso_id == permiso.id,
                        )
                    ).first()
                    if not existe:
                        db.execute(
                            rol_permiso.insert().values(rol_id=rol_cajero.id, permiso_id=permiso.id)
                        )

            db.commit()
            _seed_complementarios(db)
            print("Datos iniciales creados correctamente.")
            print("  - Empresa: Mi Empresa POS")
            print("  - Usuario admin (Administrador)")
            print("  - Usuario cajero (Cajero)")
            if forzar_cambio:
                print("  - IMPORTANTE: el sistema pedirá cambiar la contraseña en el primer ingreso.")
        else:
            print("La base de datos ya tiene datos. Revisando datos complementarios...")
            _seed_complementarios(db)
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
