# Sistema POS - Punto de Venta

Sistema de punto de venta con catálogo de productos, inventario, ventas/POS, caja, clientes/proveedores, compras, cartera (cuentas por cobrar/pagar), devoluciones, impuestos, reportes y dashboard.

## Stack

- **Backend**: Python 3.13 + FastAPI + SQLAlchemy 2 + SQL Server
- **Frontend**: React 18 + Vite
- **Base de datos**: SQL Server 2022 (Docker)

## Requisitos previos

- [Docker](https://www.docker.com/) (para SQL Server)
- Python 3.11+ (probado con 3.13)
- Node.js 18+ (probado con 24)

## Estructura

```
.
├── docker-compose.yml        # SQL Server 2022 en Docker (puerto host 26433) + túnel Cloudflare
├── backend/
│   ├── app/
│   │   ├── main.py           # Aplicación FastAPI y registro de routers
│   │   ├── config.py         # Configuración (DATABASE_URL, JWT)
│   │   ├── database.py       # Engine, SessionLocal, Base
│   │   ├── security.py       # Password hashing (bcrypt) + JWT
│   │   ├── deps.py           # Dependencias de autenticación
│   │   ├── models/           # Modelos SQLAlchemy
│   │   ├── schemas/          # Schemas Pydantic
│   │   └── routers/          # Endpoints por dominio
│   ├── init_db.py            # Crea tablas y datos iniciales (seed)
│   └── requirements.txt
└── frontend/
    └── src/                  # App React (páginas y componentes)
```

## Puesta en marcha

### 1. Levantar la base de datos

```bash
docker compose up -d
```

SQL Server queda disponible en `localhost:26433` (usuario `sa`, bd `posdb`; la contraseña se define en el `.env` del proyecto). Las tablas, migraciones y datos iniciales se aplican automáticamente al levantar el backend (`backend/entrypoint.sh` + `backend/init_db.py`).

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
python init_db.py        # crea tablas + datos iniciales
uvicorn app.main:app --reload --port 28743
```

- API: http://localhost:28743
- Documentación interactiva (Swagger): http://localhost:28743/docs

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

- App: http://localhost:5173
- El servidor Vite redirige `/api/*` al backend en el puerto 28743.

## Usuarios iniciales

| Usuario  | Contraseña | Rol            |
|----------|-----------|----------------|
| `admin`  | `admin123` | Administrador |
| `cajero` | `cajero123`| Cajero        |

## Módulos implementados

- **Autenticación**: login JWT, sesiones, `/auth/me`.
- **Organización**: empresas, sucursales, puntos de venta, cajas (CRUD).
- **Productos**: catálogo con búsqueda por nombre/código/SKU/PLU, categorías, marcas, presentaciones, precios (compra/venta/mayorista/minorista), tasa de impuesto por producto, stock mínimo/máximo/seguridad, activación.
- **Inventario**: existencias por sucursal, movimientos (entrada/salida/ajuste), kardex, stock disponible/reservado, transferencias entre sucursales, ajuste manual.
- **Personas**: clientes (ocasional/frecuente/mayorista, límite de crédito), proveedores.
- **Punto de venta (POS)**: catálogo de productos, carrito, venta contado/crédito, descuentos, impuesto automático, saldo por cobrar en crédito, múltiples medios de pago (efectivo, tarjeta, transferencia, QR, Nequi, Daviplata), control de stock al vender.
- **Pagos con tarjeta (simulador de pasarela)**: el POS autoriza el pago con tarjeta antes de confirmar la venta (`POST /pagos/tarjeta/autorizar`, código de aprobación APRxxxxxx + tarjeta enmascarada), guarda el código como referencia del pago, **confirma (captura)** al registrarse la venta y **reversa** automáticamente si la venta falla; montos inválidos/excesivos se rechazan y toda la operación queda registrada (`GET /pagos/tarjeta`). El ticket/factura imprime la columna **Aprobación**. Arquitectura preparada para reemplazar el simulador por una pasarela real (Stripe/ePayco/Datafast) sin tocar el flujo del POS.
- **Caja**: apertura/cierre, movimientos de caja (ingreso/egreso/gasto/retiro), arqueo con diferencias (sobrantes/faltantes), gastos.
- **Compras**: compras directas (contado/crédito) con costo promedio y entrada a inventario automática, órdenes de compra (crear/aprobar/cancelar/recibir), cuentas por pagar y abonos a proveedores.
- **Cartera**: cuentas por cobrar (ventas a crédito), abonos de clientes, estado de cuenta por cliente, cuentas por pagar.
- **Devoluciones**: notas crédito (NC-xxxxxx) totales o parciales, reintegro de inventario y de impuesto, reembolso, anulación de ventas (V-xxxxxx → anulada) con **reversión completa**: repone inventario y anula automáticamente los documentos fiscales emitidos (factura/notas) de la venta.
- **Configuración**: impuestos (tasa y activo), parámetros generales clave/valor.
- **Reportes**: totales de venta, utilidad bruta, ticket promedio, ventas por producto, productos agotados, ventas por día, compras, estado de resultados, resumen de cartera, compras sugeridas por punto de reorden, alertas (bajo inventario, vencimientos, cartera), ranking de vendedores con comisiones y metas, auditoría de eventos, dashboard con KPI. Los reportes de ventas filtran por **período** (`desde`/`hasta`, validando formato) y desglosan por **sucursal, caja, cajero, cliente, categoría, marca, método de pago, hora del día, mes y año** (nuevos `/reportes/ventas-por-*`).
- **Promociones**: 2x1, 3x2, porcentaje y valor; alcance general/producto; vigencia por fechas y horario; activar/desactivar; descuento de promoción aplicado automáticamente en ventas.
- **Ventas avanzadas**: propina en el total, suspensión/reanudación de ventas, bloqueo de venta por debajo del costo o del margen mínimo, historial de precios por producto, nota débito.
- **Compras avanzadas**: devoluciones a proveedor (DCP-xxxxxx con reintegro de stock y CxP), estado de cuenta por proveedor, cotizaciones de proveedor (CT-xxxxxx) con aprobación.
- **Inventario avanzado**: mermas/dañados/vencidos, conteo físico (CF-xxxxxx) por producto con ajustes automáticos al liquidar.
- **Importar/Exportar CSV**: productos, clientes, proveedores e inventario (descarga y carga masiva).
- **Vendedores**: marcado de usuarios como vendedor, metas mensuales, reglas de comisión y comisión calculada por ventas.
- **Facturación electrónica (DIAN)**: resoluciones con prefijos y rangos (FV/NC/ND), consecutivo automático, documentos fiscales, QR, PDF y ticket térmico. Genera **UBL 2.1** real (facturas/notas/correcciones) con **CUFE SHA-384** en minúsculas conforme a la reglamentación vigente y firma las notas correctivas con UFA. El estado de conexión se consulta en `/facturacion/integracion/estado`. Con `DIAN_MOCK_TRANSMISSION=true` (desarrollo/demo) el envío, consulta y rechazo se simulan con un servidor DIAN ficticio **sin transmitir nada a la DIAN real**; al deshabilitarlo, el envío queda bloqueado de forma segura hasta contar con habilitación, certificado, software registrado y pruebas aprobadas.
- **Fidelización**: cupones con vigencia/uso (valor o %) y **validación previa en el POS sin consumir el cupón** (`POST /fidelizacion/cupones/validar`, devuelve el descuento estimado y respeta el cliente/empresa del cupón), bonos, tarjetas de regalo (saldo, consumo, recargas), puntos por consumo (`puntos_por_monto` config) con historial y ajustes; los medios fidelidad se consumen como forma de pago en la venta, aplican su descuento al total y suman puntos automáticamente.
- **Ventas por apartado**: creación con abono inicial, líneas y separación de mercancía, abonos parciales, liquidación que genera venta + factura electrónica automática, cancelación y resumen por estado.
- **Pedidos y domicilios**: pedidos de cliente (mostrador/domicilio) con estados (pendiente → en preparación → listo → entregado/cancelado), costo de domicilio y repartidor, despacho y estado del domicilio (en ruta → entregado), descarga de stock al entregar, resumen por estado.
- **Repartidores y GPS**: CRUD de repartidores (vehículo, placa, disponibilidad), rutas/zonas de entrega con tarifas, seguimiento GPS por pedido (ubicación repartidor + destino), **mapa de seguimiento en vivo** (Leaflet/OSM) con marcadores, simulación de avance en ruta, historial de eventos por pedido (`/domicilios/*`).
- **Restaurante**: salones y mesas (ocupar/liberar, capacidad), comandas por mesa (líneas con preparación, servir por línea, cierre que genera venta + factura), reservas de mesas y resumen de seguridad, y **pantalla de cocina KDS** con tickets de líneas por preparar y auto-refresco.
- **Seguridad (RBAC)**: catálogo de 26 permisos por módulo/acción (sincronizable y asignable a roles), permisos del usuario actual y verificación `modulo/accion`. Las operaciones sensibles (anulación de ventas, devoluciones/cambios, ajustes de inventario/mermas/liquidación de conteos y movimientos/arqueo de caja/gastos) **escalan a autorización**: si el usuario no tiene el permiso, se registra una solicitud pendiente (`/seguridad/autorizaciones`) y se bloquea con 403; el administrador aprueba o rechaza desde seguridad o mediante el flujo de descuentos que superan el umbral (`descuento_maximo_sin_autorizacion`).
- **Producción y transformación**: productos compuestos con materias primas (`ProductoComponente`), órdenes de producción (`PR-xxxxxx`) que consumen MP, generan el terminado y registran su costo; resumen de producción, materias primas consumidas y **desperdicios** (mermas). Restringido por inventario/ajustar.
- **Acuerdos de pago**: acuerdos por cliente con cuotas prorrateadas y vencimientos por periodicidad (semanal/quincenal/mensual), seguimiento de abonos/saldo y pago de cuotas que descuenta la cartera del cliente.
- **Códigos de barras y etiquetas**: generación automática de **EAN-13** (con dígito verificador), SVG del código por producto, impresión de etiquetas de precios (`/etiquetas/productos`, copias, precio mayorista, vencimiento por lote) y etiquetas de **góndola/estante** (`/etiquetas/gondola`).
- **Reportes nuevos y exportación**: reporte de **proveedores** y **pronóstico de demanda** a 7 días (promedio móvil); exportación a **Excel** (SpreadsheetML) y **PDF** (reportlab) de ventas y ventas por producto.
- **Promociones por cliente**: alcance de promociones restringido a un cliente específico (`cliente_id`), aplicado automáticamente en la venta según el cliente del documento.
- **Integraciones**: monedas (tasa de cambio y conversión), balanzas electrónicas (configuración y lectura de peso simulada), bancos (cuentas con saldo, movimientos y conciliación), webhooks por evento (fire-and-forget), WhatsApp (envío registrado), y **backups/restauración** de 12 tablas núcleo (`/backups`).
- **Restricciones y división de cuentas**: restricción de venta por **sucursal** (usuario) y por **caja** (el punto de venta de la caja debe pertenecer a la sucursal), y **división de una venta a crédito** entre varios clientes (`POST /ventas/{id}/dividir`).
- **Operación offline y sincronización**: catálogo/stock/clientes descargables (`GET /offline/catalogo`) para operar sin conexión, **cola de operaciones pendientes** (`POST /offline/pendientes`, ventas bajo cliente_uuid idempotente), **sincronización** que replica las ventas registradas offline como ventas reales en el servidor (`POST /offline/sincronizar`, con estado por operación y errores), y **novedades** incremental por fecha (`GET /offline/novedades?desde=`). Página **Offline** en la UI con indicador en línea/sin conexión.
- **Pantalla de cliente**: el POS publica en tiempo real (debounce 600ms) el ticket en curso —ítems, descuento, propina y total— (`POST /pantalla`, lectura pública `GET /pantalla`) y abre una **vista de pantalla de cliente** (`GET /pantalla/vista`) separada para el comprador, con auto-refresco cada 2s.

## Endpoints principales

```
POST /auth/login                 Iniciar sesión
GET  /auth/me                    Usuario actual
GET/POST /organizacion/...       Empresas, sucursales, puntos de venta, cajas
GET/POST /productos/...          Catálogo, categorías, marcas, presentaciones
GET/POST /inventario/...         Stock, movimientos, ajustes, transferencias
GET/POST /clientes, /proveedores Clientes y proveedores
GET/POST /ventas                 Crear y listar ventas
POST /ventas/{id}/anular         Anular una venta
POST /caja/apertura, /cierre     Apertura y cierre de caja
POST /caja/movimientos, /gastos  Movimientos de caja y gastos
GET/POST /compras                Compras directas (contado/crédito)
GET/POST /compras/ordenes        Órdenes de compra (aprobar/recibir/cancelar)
GET  /compras/cuentas-pagar      Cuentas por pagar
POST /compras/cuentas-pagar/{id}/abonos   Abonar a proveedor
POST /cartera/abonos/clientes    Abonar a cuenta de cliente
GET  /cartera/cuentas-cobrar     Cartera por cobrar
GET  /cartera/estado-cuenta/{id} Estado de cuenta de cliente
POST /devoluciones               Nota crédito / devolución
POST /pagos/tarjeta/autorizar    Autorizar pago con tarjeta (simulador pasarela)
POST /pagos/tarjeta/{id}/confirmar   Confirmar/capturar transacción
POST /pagos/tarjeta/{id}/reversar    Reversar transacción
GET  /pagos/tarjeta              Historial de transacciones de tarjeta
GET  /offline/catalogo           Instantánea para operar sin conexión
POST /offline/pendientes         Encolar operación offline (venta)
POST /offline/sincronizar        Replicar ventas offline en el servidor
GET  /offline/novedades          Delta de datos nuevos desde una fecha
POST /pantalla                   Publicar ticket en curso (pantalla de cliente)
GET  /pantalla, /pantalla/vista  Lectura y vista web de la pantalla de cliente
POST /devoluciones/cambio        Cambio de productos (devolución + reventa)
GET/POST /promociones            Promociones (toggle activa)
POST /ventas/{id}/suspender      Suspender venta
POST /ventas/{id}/reanudar       Reanudar venta
POST /ventas/{id}/nota-debito    Nota débito sobre venta
GET  /productos/{id}/precios     Historial de precios
POST /compras/devoluciones       Devolución a proveedor (DCP-xxxxxx)
GET  /compras/estado-cuenta/{id} Estado de cuenta de proveedor
GET/POST /compras/cotizaciones   Cotizaciones de proveedor (aprobar)
POST /inventario/mermas          Registrar merma/dañado/vencido
GET/POST /inventario/conteos     Conteo físico (liquidar)
GET  /exportar/* , POST /importar/*   Importación/exportación CSV
GET/POST /vendedores/*           Vendedores, metas y reglas de comisión
GET/POST /facturacion/resoluciones   Resoluciones DIAN (prefijos y rangos)
GET  /facturacion/documentos     Historial de documentos fiscales (filtros)
POST /facturacion/generar/{venta_id}  Emitir factura/nota electrónica
POST /facturacion/{id}/enviar    Enviar documento a la DIAN (simulado)
POST /facturacion/{id}/consultar Consultar estado DIAN (aprobación)
POST /facturacion/{id}/rechazar  Simular rechazo de la DIAN
POST /facturacion/{id}/reintentar Reintentar documento rechazado
POST /facturacion/{id}/anular    Anular documento electrónico
GET  /facturacion/{id}/pdf       PDF de representación gráfica
GET  /facturacion/{id}/ticket    Ticket térmico imprimible (80mm)
GET  /facturacion/{id}/html      Vista HTML imprimible
POST /facturacion/{id}/correo, /whatsapp  Envío simulado
GET  /facturacion/resumen        Resumen por estado y tipo
GET  /facturacion/ventas-sin-facturar  Ventas pendientes de facturar
GET  /reportes/auditoria         Bitácora de auditoría
GET  /reportes/ventas-por-sucursal  Ventas por sucursal
GET  /reportes/ventas-por-caja   Ventas por caja
GET  /reportes/ventas-por-cliente  Ventas por cliente
GET  /reportes/ventas-por-categoria  Ventas por categoría
GET  /reportes/ventas-por-marca  Ventas por marca
GET  /reportes/ventas-por-hora   Ventas por hora del día
GET  /reportes/ventas-por-mes    Ventas por mes (YYYY-MM)
GET  /reportes/ventas-por-ano    Ventas por año
GET/POST /configuracion/...      Impuestos y parámetros generales
GET  /reportes/*                 Reportes y dashboard
GET/POST /fidelizacion/...       Puntos, cupones, bonos, tarjetas de regalo (consumir/recargar) y resumen
GET/POST /apartados/...          Apartados (abonos, liquidar → venta+factura, cancelar)
GET/POST /pedidos/...            Pedidos y domicilios (estados, despacho, entregar)
GET/POST /restaurante/...        Salones, mesas, comandas (servir/cerrar), reservas y resumen
GET/POST /domicilios/...         Repartidores, rutas, seguimiento GPS, mapa en vivo, tracking y simulación
GET/POST /seguridad/...          Permisos por rol, mi-permisos, verificar/{modulo}/{accion} y autorizaciones
POST /produccion                 Crear orden de producción (consumo de MP y stock)
GET  /produccion, /produccion/resumen   Órdenes y resumen (producción, MP, desperdicios)
POST /acuerdos-pago              Crear acuerdo de pago (cuotas por periodicidad)
POST /acuerdos-pago/{id}/pagar-cuota     Pagar cuota del acuerdo
GET/POST /monedas                Monedas y tasas; POST /monedas/{id}/convertir
GET/POST /balanzas               Balanzas; POST /balanzas/{id}/pesar
GET/POST /bancos/cuentas         Cuentas bancarias; POST /bancos/movimientos/{id}/conciliar
GET/POST /webhooks               Webhooks por evento (venta.creada, ...)
POST /whatsapp/enviar            Enviar WhatsApp (simulado, con registro)
GET/POST /backups                Backups de tablas núcleo; POST /backups/{id}/restaurar
GET  /etiquetas/productos        Etiquetas de precio (copias, mayorista, vencimiento)
GET  /etiquetas/gondola          Etiquetas grandes de góndola/estante
GET  /productos/{id}/codigo-barras   SVG del código EAN-13
POST /ventas/{id}/dividir        Dividir venta a crédito entre clientes
GET  /reportes/proveedores       Reporte de proveedores
GET  /reportes/pronostico        Pronóstico de demanda a N días
GET  /reportes/exportar/ventas, /ventas-por-producto   Exportación XLS/PDF
```

## Notas

- Puerto de SQL Server en host: **11433** (para evitar conflictos con una instalación local de SQL Server en el 1433).
- La configuración se puede sobreescribir con un archivo `.env` en `backend/` (ver `backend/app/config.py`).
- En producción cambiar `SECRET_KEY` en la configuración.
- La interfaz usa **modo claro y modo oscuro** (toggle en la barra superior, persistido en `localStorage`) con una paleta roja/blanco/negro.
- El mapa de domicilios usa teselas de OpenStreetMap (no requiere API key).
- Validación automatizada del módulo de ventas en `backend/test_ventas.py` (87 checks: caja/apertura-cierre/arqueo, ventas contado/crédito con impuesto/descuento/propina/pagos mixtos, validaciones, crédito y límites, suspensión/nota débito/anulación con reversión y permisos, auto-factura, devoluciones y cambios, cierre con saldo exacto, reportes y anulación admin). Resto de flujos en `backend/test_fase2.py`, `test_fase3.py`, `test_fase4.py`, `test_especial.py`, `backend/test_fase6.py` (producción, acuerdos, promociones por cliente, división de cuentas, restricciones por sucursal/caja, monedas, balanzas, bancos, webhooks, WhatsApp, backups/restauración, etiquetas, códigos de barras, exports y pronóstico) y `backend/test_pagos_tarjeta.py` (18 checks del simulador de pasarela: autorizar/confirmar/reversar, rechazos, venta con tarjeta y referencia en el comprobante) y `backend/test_offline.py` (29 checks: catálogo offline, cola idempotente, sincronización de ventas offline, novedades por fecha y pantalla de cliente con su vista).

## Aplicación de escritorio (Windows)

Existe una versión **portable** del sistema en `C:\Users\DORADO\Documents\pos-desktop-tauri\deploy\` (proyecto separado `pos-desktop-tauri`):

- `POS-Escritorio.exe` — launcher **Tauri 2** (Rust + WebView2) que abre el POS en una ventana nativa y sirve el frontend + un proxy `/api` en el mismo origen.
- `binaries\backendsrv.exe` — backend embebido (FastAPI + SQLAlchemy compilado con PyInstaller) que se lanza automáticamente a **127.0.0.1:18000**.
- `webview` — usa `WebView2Loader.dll` (junto al exe; el runtime WebView2 Evergreen viene con Windows 10/11).
- `datos\` — carpeta de datos generada en el primer arranque (`backend.log`, `app.log` y `db.json` si se sobrescribe la conexión).
- El backend embebido NO requiere controladores ODBC: usa `pymssql` pegado al binario y se conecta por defecto a **SQL Server en `127.0.0.1:11433` (bd `posdb`, usuario `sa`)**. Para apuntar a otro servidor, crear `datos\db.json` junto al exe con `{"host","port","db","user","password"}`.
- Registros de diagnóstico: `datos\backend.log` (uvicorn/pymssql) y `datos\app.log` (launcher). Para ejecución sin ventana (diagnóstico/servidor), variables `POS_HEADLESS=1` y `POS_SPA_PORT=<puerto>`.

Pasos para levantar el proyecto de escritorio desde fuente: ver `pos-desktop-tauri\README` (build Tauri `cargo build --release` en `src-tauri` y backend PyInstaller `--onefile --windowed --collect-all=pymssql --collect-submodules=app`).
