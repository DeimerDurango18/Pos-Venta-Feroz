# RUTA_HABILITACION_DIAN.md

Ruta táctica para producir facturación electrónica **real** en la DIAN
(Colombia) con el período mínimo legal de contingencia y sin detener operación.

## Decisión adoptada (Bloque 1.3 del plan maestro)

- **Modelo: (c) PST certificado.** La empresa NO se certifica directamente en
  MUISCA; contrata un Proveedor Tecnológico Autorizado (PST) que transmite los
  XML y recibe las respuestas de la DIAN. Evita: manejo directo de certificados,
  navegación MUISCA, RUT con responsabilidad/actividad 491/571, Contabilidad
  Asia, Software propio en MUISCA.
- **Vía táctica certificada en 2-4 semanas:** conector "mock" actual opera; la
  facturación real se habilita una vez el PST asigna `DIAN_PROVIDER_URL`.
- El sistema ya detecta cualquier certificado de cliente (`.p12`) si más
  adelante se prefiere el modelo (b) webservice directo.

## Estado del código (ya desplegado)

| Pieza | Estado |
|---|---|
| `ConectorDIAN` (base) + `ConectorMock` / `ConectorWebServiceDIAN` / `ConectorPST` | Implementado en `backend/app/dian.py` |
| Selector de conector por configuración | `DIAN_CONECTOR` en entorno (`mock` \| `webservice` \| `pst`), default `mock` |
| Producción sin conector certificado | Devuelve HTTP 501 limpio (antes 500) |
| Endpoint público `/estado` | Expone `dian.modo/conector/puede_transmitir/configurado` para monitoreo |
| Modo sandbox (pruebas) | Sigue funcionando sin tocar la DIAN |

## Requisitos legales/habilitación (proceso externo)

1. **RUT** actualizado en DIAN: responsabilidad fiscal **IVA 13** y actividad
   económica **CIUU 4911** (emite factura electrónica) / **5711** (establecimiento
   de comercio). El sistema le mostrará al administrador la resolución y el NIT.
2. **Certificado digital** de facturación (emitido por una entidad certificadora
   acreditada) para firmar XML. En model	os el PST firma; guarde el `.p12` si usa
   modelo directo.
3. **Habilitación en MUISCA** del municipio/actividad del responsable de facturación
   (habilitación de facturación electrónica: resolución de facturación vigente).
4. **Software propio registrado** (solo si se certifica la app como tal; con PST
   recae sobre el PST).
5. **Acuerdo con el PST:** entregar NIT + razón social + resolución vigente; el
   PST asigna URL del proveedor y credenciales de autenticación.

## Configuración en el sistema (una vez el PST valida)

| Variable | Valor |
|---|---|
| `DIAN_CONECTOR` | `pst` |
| `DIAN_ENVIRONMENT` | `habilitacion` (LUEGO `produccion`) |
| `DIAN_PROVIDER_URL` | URL del endpoint del PST |
| `DIAN_SOFTWARE_ID` / `DIAN_SOFTWARE_PIN` / `DIAN_TEST_SET_ID` | credenciales del PST |
| `DIAN_CERTIFICATE_PATH` / `DIAN_CERTIFICATE_PASSWORD` | solo modelo directo |
| `DIAN_MOCK_TRANSMISSION` | `false` (importante: no enviar mocks) |

El cliente configurado en la app permite UI para estos valores
(`/configuracion/dian`), verificado en sandbox.

## Verificación por pasos (pre-producción)

1. Sandbox: generar factura → estado aparece `transmitido/aceptada`.
2. Con `DIAN_CONECTOR=pst` y URL falsa: el sistema debe devolver 501 con mensaje
   claro (ya verificado).
3. Habilitación real: 1 factura con NIT/CC válidos → validar XML contra esquema
   XSD de la DIAN → confirmar respuesta de la DIAN con `ConsultarEstado` (el
   conector ya implementa `consultar_estado_dian`).
4. Corre electrónico de validación y envío por lote de documentos atrasados.

## Cronograma referencial

- Semana 1-2: certificado + RUT + habilitación + contrato PST.
- Semana 3-4: pruebas certificadas en habilitación → pasar a producción → primera
  factura real.
- Contingencia: el sistema sigue en `mock` para no bloquear ventas; las facturas
  generadas en contingencia deben transmitirse al salir de contingencia (lote).

## Riesgos

- Retroactividad: autorizar solo desde fecha de habilitación.
- IVA/resoluciones vencidas: el sistema valida resolución activa.
- PST que cae: cola de reintentos + alerta en `/estado`.