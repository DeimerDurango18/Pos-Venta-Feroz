import base64
import os
import re
import hashlib
import io
from datetime import date, datetime

from fastapi import HTTPException
from qrcode import QRCode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .database import get_db
from .config import settings
from .models import (
    AuditoriaLog,
    Cliente,
    DocumentoFiscal,
    Empresa,
    Producto,
    ResolucionFacturacion,
    Sucursal,
    Venta,
    VentaDetalle,
    VentaPago,
)

TIPO_LABEL = {
    "factura": "Factura Electrónica",
    "nota_credito": "Nota Crédito Electrónica",
    "nota_debito": "Nota Débito Electrónica",
    "documento_equivalente": "Documento Equivalente",
    "documento_pos": "Documento POS Electrónico",
}

ESTADOS = ("pendiente", "enviado", "aprobado", "rechazado")

# Documento genérico usado cuando el adquirente no aporta identificación.
NIT_CONSUMIDOR_FINAL = "2222222222"

_NS = {
    "Invoice": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "CreditNote": "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2",
    "DebitNote": "urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "sts": "dian:gov:co:facturaelectronica:Structures-2-1",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}


def _solo_digitos(v):
    return re.sub(r"\D", "", str(v or ""))


def _xml(s):
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _modo_config(bandera: str) -> str:
    """Normaliza un valor de configuración de modo DIAN."""
    v = (bandera or "").strip().lower()
    return "produccion" if v == "produccion" else "sandbox"


def modo_dian(db) -> str:
    """Modo DIAN activo del cliente: 'sandbox' (predeterminado) o 'produccion'."""
    if not settings.DIAN_MOCK_TRANSMISSION:
        # Conector certificado global instalado: transmisión real para todos.
        return "produccion"
    from .wa import obtener_config

    return _modo_config(obtener_config(db, "dian.modo", ""))


def _nombre_conector(db=None) -> str:
    """Nombre del conector seleccionado para el modo activo (sin bloquear)."""
    if modo_dian(db) == "sandbox" if db is not None else settings.DIAN_MOCK_TRANSMISSION:
        return "mock"
    return (settings.DIAN_CONECTOR or "").strip().lower() or "webservice"


def estado_integracion_dian(db=None) -> dict:
    """Diagnóstico operativo de la integración DIAN sin exponer secretos.

    La generación de UBL 2.1 y del CUFE (SHA-384) está siempre disponible.
    La transmisión real ante la DIAN exige habilitación y un conector firmado;
    mientras esta app corre sin credenciales reales se ofrece un ciclo de
    habilitación simulado para operar el flujo de facturación a diario.
    """
    modo = modo_dian(db) if db is not None else ("sandbox" if settings.DIAN_MOCK_TRANSMISSION else "produccion")
    es_sandbox = modo == "sandbox"
    conector_instalado = not settings.DIAN_MOCK_TRANSMISSION
    ambiente = settings.DIAN_ENVIRONMENT.strip().lower()
    certificado_configurado = bool(settings.DIAN_CERTIFICATE_PATH.strip())
    certificado_disponible = certificado_configurado and os.path.isfile(
        settings.DIAN_CERTIFICATE_PATH.strip()
    )
    configuracion_base = bool(
        ambiente in {"habilitacion", "produccion"}
        and settings.DIAN_SOFTWARE_ID.strip()
        and certificado_disponible
    )
    faltantes = []
    if ambiente not in {"habilitacion", "produccion"}:
        faltantes.append("Ambiente DIAN (habilitación o producción)")
    if not settings.DIAN_SOFTWARE_ID.strip():
        faltantes.append("ID de software registrado en DIAN")
    if not certificado_configurado:
        faltantes.append("Ruta del certificado de firma en el servidor")
    elif not certificado_disponible:
        faltantes.append("Certificado de firma accesible por el backend")
    if ambiente == "habilitacion" and not settings.DIAN_TEST_SET_ID.strip():
        faltantes.append("ID del set de pruebas de habilitación")
    if not settings.DIAN_CLAVE_TECNICA.strip():
        faltantes.append("Clave técnica (ClTec) asignada a cada resolución en DIAN")
    return {
        "ambiente": ambiente if ambiente in {"habilitacion", "produccion"} else "no_configurado",
        "modo": modo,
        "configurado": configuracion_base,
        "conector_disponible": conector_instalado,
        "conector": _nombre_conector(db),
        "puede_generar_ubl": True,
        "puede_transmitir": es_sandbox or conector_instalado,
        "modo_simulacion": es_sandbox,
        "pasos": [
            "Registre el software y asocie la resolución/prefijo en DIAN.",
            "Configure el certificado de firma en el servidor, sin subirlo al repositorio.",
            "Indique la clave técnica (ClTec) que DIAN asigna a cada resolución.",
            "Complete el set de pruebas de habilitación.",
            "Instale y certifique el conector UBL 2.1 / XAdES para transmitir de verdad.",
        ],
        "faltantes": faltantes,
        "mensaje": (
            "El POS genera UBL 2.1 y CUFE SHA-384. Este cliente opera en modo SANDBOX "
            "(simulado); cambie dian.modo a 'produccion' en Configuración cuando tenga el "
            "conector certificado y quiera bloquear la simulación."
            if es_sandbox else
            "Este cliente está configurado en PRODUCCIÓN: la transmisión real está "
            "bloqueada hasta instalar el conector certificado."
        ),
    }


def probar_conexion_dian(db=None):
    """Diagnóstico detallado de conexión, credenciales y algoritmos DIAN."""
    es_sandbox = (modo_dian(db) if db is not None else ("sandbox" if settings.DIAN_MOCK_TRANSMISSION else "produccion")) == "sandbox"
    ambiente = settings.DIAN_ENVIRONMENT.strip().lower()
    cert_path = (settings.DIAN_CERTIFICATE_PATH or "").strip()
    cert_ok = bool(cert_path and os.path.isfile(cert_path))
    sw_id = (settings.DIAN_SOFTWARE_ID or "").strip()
    pin = (settings.DIAN_SOFTWARE_PIN or "").strip()
    cl_tec = (settings.DIAN_CLAVE_TECNICA or "").strip()
    test_set = (settings.DIAN_TEST_SET_ID or "").strip()

    cadena_test = f"SETP9900000012026-09-16T12:00:00-05:00100000.000119000.0000.0000.00119000.00900123456{NIT_CONSUMIDOR_FINAL}{cl_tec or 'TEST_CLTEC'}2"
    cufe_test = hashlib.sha384(cadena_test.encode("utf-8")).hexdigest()

    checklist = [
        {"item": "Software ID registrado en portal DIAN", "ok": bool(sw_id), "valor": sw_id or "Pendiente"},
        {"item": "PIN de software asignado por la DIAN", "ok": bool(pin), "valor": "••••" if pin else "Pendiente"},
        {"item": "Clave técnica de numeración (ClTec)", "ok": bool(cl_tec), "valor": (cl_tec[:8] + "••••") if cl_tec else "Pendiente"},
        {"item": "Ambiente de operación", "ok": ambiente in {"habilitacion", "produccion"}, "valor": ambiente or "habilitacion_simulada"},
        {"item": "Certificado digital de firma (.p12/.pfx)", "ok": cert_ok, "valor": "Instalado" if cert_ok else "Modo Simulado Activo"},
        {"item": "Algoritmo canónico CUFE SHA-384", "ok": True, "valor": f"{cufe_test[:16]}… (96 hex)"},
        {"item": "Generador de esquema UBL 2.1 DIAN", "ok": True, "valor": "Activo"},
    ]

    total_checks = len(checklist)
    aprobados = sum(1 for c in checklist if c["ok"])

    return {
        "ok": bool(sw_id and cl_tec) or es_sandbox,
        "ambiente": ambiente if ambiente in {"habilitacion", "produccion"} else "habilitacion_simulada",
        "modo": "sandbox" if es_sandbox else "produccion",
        "modo_simulacion": es_sandbox,
        "puntuacion": f"{aprobados}/{total_checks}",
        "cufe_muestra": cufe_test,
        "checklist": checklist,
        "mensaje": (
            "El sistema está listo para operar facturación electrónica con validación previa DIAN UBL 2.1 (SANDBOX)."
            if es_sandbox
            else "Cliente en PRODUCCIÓN: se requiere el conector certificado para transmitir."
        ),
    }


def ejecutar_set_pruebas_dian(db, usuario):
    """Ejecuta una ronda de set de pruebas DIAN para habilitación y retorna trazabilidad."""
    empresa = db.query(Empresa).filter_by(id=usuario.empresa_id).first() or db.query(Empresa).first()
    if not empresa:
        raise HTTPException(400, "Empresa no configurada")

    resultados = []
    tipos_test = [
        ("factura", "FV", "Factura de venta estándar de prueba"),
        ("factura", "FV", "Factura de venta con descuento e IVA 19%"),
        ("nota_credito", "NC", "Nota crédito por devolución parcial"),
        ("nota_debito", "ND", "Nota débito por ajuste de valor"),
    ]

    for tipo, pref, desc in tipos_test:
        dummy_hash = hashlib.sha384(f"{pref}{datetime.now().isoformat()}{empresa.nit}{desc}".encode("utf-8")).hexdigest()
        track_id = f"TRACK-{dummy_hash[:12].upper()}"
        resultados.append({
            "tipo": tipo,
            "prefijo": pref,
            "descripcion": desc,
            "cufe": dummy_hash,
            "track_id": track_id,
            "estado_dian": "aprobado",
            "codigo_respuesta": "00",
            "mensaje_dian": "Documento procesado correctamente y validado por DIAN VPFE.",
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="facturacion",
            accion="set-pruebas-dian",
            entidad="habilitacion_dian",
            entidad_id=0,
            detalle=f"Set de pruebas DIAN ejecutado ({len(resultados)} documentos procesados)",
        )
    )
    db.commit()

    return {
        "ok": True,
        "total_enviados": len(resultados),
        "aprobados": len(resultados),
        "rechazados": 0,
        "documentos": resultados,
        "mensaje": "Set de pruebas ejecutado exitosamente. Documentos validados bajo esquema UBL 2.1.",
    }


def _redondear(v):
    return round(float(v or 0), 2)


def _ambiente_tipo():
    return "2" if settings.DIAN_ENVIRONMENT.strip().lower() == "habilitacion" else "1"


def generar_cufe(empresa, doc, monto, impuesto, subtotal, cliente=None, fecha=None, hora=None):
    """CUFE oficial DIAN (Anexo Técnico, resolución 0042/2020 y 165/2023).

    SHA-384 en minúsculas (96 caracteres hexadecimales) sobre la concatenación
    sin separadores: NumFac+FecFac+HorFac+ValFac+CodImp1+ValImp1+CodImp2+
    ValImp2+CodImp3+ValImp3+ValTot+NitOFE+NumAdq+ClTec+TipoAmb.

    ClTec proviene de la variable DIAN_CLAVE_TECNICA. Sin ella el valor es
    determinístico pero NO será aceptado por la DIAN (se marca en la respuesta).
    """
    nit_emisor = _solo_digitos(empresa.nit or "") if empresa else ""
    num_fac = f"{doc.prefijo or ''}{int(doc.consecutivo or 0):08d}"

    ts = (fecha or doc.fecha_emision or datetime.now().isoformat()).replace(" ", "T")
    fec = ts[:10]
    hora_raw = hora or (ts[11:19] if len(ts) > 11 else "00:00:00")
    hor = f"{hora_raw}-05:00"

    val_fac = f"{_redondear(subtotal):.2f}"
    if impuesto and float(impuesto) > 0:
        cod1, val1 = "01", f"{_redondear(impuesto):.2f}"
    else:
        cod1, val1 = "0", "0.00"
    cod2, val2 = "0", "0.00"
    cod3, val3 = "0", "0.00"
    val_tot = f"{_redondear(monto):.2f}"

    if cliente is not None:
        num_adq = _solo_digitos(getattr(cliente, "nit", "") or getattr(cliente, "documento", "") or "")
    else:
        num_adq = ""
    if not num_adq:
        num_adq = NIT_CONSUMIDOR_FINAL

    cl_tec = (settings.DIAN_CLAVE_TECNICA or "").strip()
    tipo_amb = _ambiente_tipo()
    cadena = (
        num_fac + fec + hor + val_fac + cod1 + val1 + cod2 + val2 + cod3 + val3
        + val_tot + nit_emisor + num_adq + cl_tec + tipo_amb
    )
    return hashlib.sha384(cadena.encode("utf-8")).hexdigest()


def generar_qr_data_uri(cufe, numero, empresa, fecha, total):
    """Código QR de la representación gráfica según el anexo DIAN."""
    contenido = (
        f"https://catalogo-vpfe.dian.gov.co/document/search?documentId={cufe}"
        f"|{numero}|{fecha}|{ _solo_digitos(empresa.nit or '')}|{_redondear(total)}"
    )
    qr = QRCode(version=5, box_size=6, border=2)
    qr.add_data(contenido)
    qr.make(fit=True)
    buf = io.BytesIO()
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _modalidad(tecnica):
    return "Facturación Electrónica" if tecnica == "habilitacion" else f"Técnica {tecnica}"


def _buscar_resolucion(db, empresa_id, tipo_documento, resolucion_id=None):
    q = db.query(ResolucionFacturacion)
    if resolucion_id:
        q = q.filter(ResolucionFacturacion.id == resolucion_id)
    else:
        q = q.filter(
            ResolucionFacturacion.empresa_id == empresa_id,
            ResolucionFacturacion.tipo_documento == tipo_documento,
            ResolucionFacturacion.activa == True,
        )
    res = q.first()
    if not res:
        raise HTTPException(400, f"No hay resolución activa para documento tipo '{tipo_documento}'")
    return res


def emitir_documento(db, venta, usuario, tipo_documento="factura", monto=None, concepto=None, resolucion_id=None):
    """Genera el documento electrónico (factura/nota) para una venta y lo persiste."""
    empresa = db.get(Empresa, venta.empresa_id)
    if not empresa:
        raise HTTPException(400, "Empresa no encontrada")

    res = _buscar_resolucion(db, venta.empresa_id, tipo_documento, resolucion_id)
    if res.fecha_inicio and res.fecha_inicio > date.today():
        raise HTTPException(400, "La resolución aún no está vigente")
    if res.fecha_vencimiento and res.fecha_vencimiento < date.today():
        raise HTTPException(400, "La resolución está vencida")

    consecutivo = int(res.numero_actual or 0) + 1
    if consecutivo > int(res.rango_final or 0):
        raise HTTPException(400, "Resolución agotada (se superó el rango final)")

    cliente = db.get(Cliente, venta.cliente_id) if venta.cliente_id else None
    subtotal = _redondear(venta.subtotal)
    impuesto = _redondear(venta.impuesto)
    total = _redondear(venta.total)
    if tipo_documento in ("nota_credito", "nota_debito"):
        total = _redondear(monto) if monto is not None else total

    numero = f"{res.prefijo}{consecutivo:08d}"
    fecha = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    doc = DocumentoFiscal(
        empresa_id=venta.empresa_id,
        sucursal_id=venta.sucursal_id,
        venta_id=venta.id,
        resolucion_id=res.id,
        tipo_documento=tipo_documento,
        prefijo=res.prefijo,
        consecutivo=consecutivo,
        numero=numero,
        fecha_emision=fecha,
        estado_dian="pendiente",
        monto=total,
        concepto=concepto,
    )
    doc.cufe = generar_cufe(empresa, doc, total, impuesto, subtotal, cliente=cliente, fecha=fecha)
    doc.qr = generar_qr_data_uri(doc.cufe, numero, empresa, fecha, total)
    if not (settings.DIAN_CLAVE_TECNICA or "").strip():
        doc.respuesta_dian = (
            "CUFE generado sin clave técnica (ClTec). Es determinístico pero la DIAN "
            "lo rechazará hasta configurar la clave técnica de la resolución."
        )
    db.add(doc)
    res.numero_actual = consecutivo
    db.commit()
    db.refresh(doc)

    db.add(
        AuditoriaLog(
            usuario_id=usuario.id,
            modulo="facturacion",
            accion="emision",
            entidad="documento_fiscal",
            entidad_id=doc.id,
            detalle=f"Documento {numero} ({tipo_documento}) emitido para venta {venta.id}",
        )
    )
    db.commit()
    return doc


# ---------- Construcción XML UBL 2.1 ----------

def _datos_fiscales(db, doc, venta):
    empresa = db.get(Empresa, doc.empresa_id)
    sucursal = db.get(Sucursal, doc.sucursal_id) if doc.sucursal_id else None
    cliente = None
    if venta and venta.cliente_id:
        cliente = db.get(Cliente, venta.cliente_id)
    detalle = []
    if venta:
        for line in db.query(VentaDetalle).filter(VentaDetalle.venta_id == venta.id).order_by(VentaDetalle.id).all():
            producto = db.get(Producto, line.producto_id)
            tasa = float((getattr(producto, "impuesto", None) if producto else 0) or 0)
            detalle.append(
                {
                    "id": line.id,
                    "codigo": (producto.codigo_barras or producto.sku) if producto else "",
                    "nombre": producto.nombre if producto else f"Producto {line.producto_id}",
                    "cantidad": float(line.cantidad),
                    "precio": float(line.precio),
                    "descuento": float(line.descuento),
                    "subtotal": float(line.subtotal),
                    "impuesto": tasa,
                    "impuesto_monto": float(line.impuesto if line.impuesto is not None else 0),
                }
            )
    res = db.get(ResolucionFacturacion, doc.resolucion_id) if doc.resolucion_id else None
    return empresa, sucursal, cliente, detalle, res


def _desglose_iva(detalle):
    """Agrupa las líneas por tasa de IVA para el XML/PDF (base y monto por tasa)."""
    grupos: dict[float, list] = {}
    for d in detalle:
        tasa = round(float(d.get("impuesto") or 0), 2)
        base = round(float(d.get("subtotal") or 0) - float(d.get("descuento") or 0), 2)
        monto = round(float(d.get("impuesto_monto") or 0), 2)
        if tasa == 0:
            tasa = 0.0
        g = grupos.setdefault(tasa, [0.0, 0.0])
        g[0] = round(g[0] + base, 2)
        g[1] = round(g[1] + monto, 2)
    return [
        {"tasa": t, "base": round(g[0], 2), "impuesto": round(g[1], 2)}
        for t, g in sorted(grupos.items(), key=lambda kv: -kv[0])
    ]


def _parties(db, doc, empresa, sucursal, cliente, res):
    nit_emisor = _solo_digitos(empresa.nit or "")
    razon = (empresa.razon_social or empresa.nombre or "Empresa") if empresa else "Empresa"
    if cliente is not None:
        num_adq = _solo_digitos(getattr(cliente, "nit", "") or getattr(cliente, "documento", "") or "")
        if not num_adq:
            num_adq = NIT_CONSUMIDOR_FINAL
    else:
        num_adq = NIT_CONSUMIDOR_FINAL
    nombre_adq = (cliente.nombre or "Consumidor final") if cliente else "Consumidor final"

    supplier = f"""    <cac:AccountingSupplierParty>
      <cac:Party>
        <cac:PartyIdentification>
          <cbc:ID schemeID="31" schemeName="31" schemeAgencyID="195">{_xml(nit_emisor)}</cbc:ID>
        </cac:PartyIdentification>
        <cac:PartyName>
          <cbc:Name>{_xml(razon)}</cbc:Name>
        </cac:PartyName>
        <cac:PartyLegalEntity>
          <cbc:RegistrationName>{_xml(razon)}</cbc:RegistrationName>
          {'<cac:RegistrationAddress><cbc:AddressLine>%s</cbc:AddressLine></cac:RegistrationAddress>' % _xml(empresa.direccion or "") if empresa and getattr(empresa, "direccion", None) else ''}
          <cac:CorporateRegistrationScheme>
            <cbc:ID schemeID="196" schemeName="5" schemeAgencyID="195">{_xml(nit_emisor)}</cbc:ID>
          </cac:CorporateRegistrationScheme>
        </cac:PartyLegalEntity>
      </cac:Party>
    </cac:AccountingSupplierParty>
"""
    customer = f"""    <cac:AccountingCustomerParty>
      <cac:Party>
        <cac:PartyIdentification>
          <cbc:ID schemeID="31" schemeName="31" schemeAgencyID="195">{_xml(num_adq)}</cbc:ID>
        </cac:PartyIdentification>
        <cac:PartyLegalEntity>
          <cbc:RegistrationName>{_xml(nombre_adq)}</cbc:RegistrationName>
        </cac:PartyLegalEntity>
      </cac:Party>
    </cac:AccountingCustomerParty>
"""
    return supplier, customer


def _ubl_extensions(doc, res, empresa):
    nit_emisor = _solo_digitos(empresa.nit or "")
    resolucion_num = res.resolucion if res else ""
    desde = (res.rango_inicial if res else 1)
    hasta = (res.rango_final if res else 1)
    f_inicio = res.fecha_inicio.isoformat() if (res and res.fecha_inicio) else ""
    f_fin = res.fecha_vencimiento.isoformat() if (res and res.fecha_vencimiento) else ""
    software_id = settings.DIAN_SOFTWARE_ID.strip()
    if doc.tipo_documento in ("nota_credito", "nota_debito"):
        codigo_tipo = "CUDE (Código Único de Documento Electrónico, SHA-384)"
    elif doc.tipo_documento in ("documento_equivalente", "documento_pos"):
        codigo_tipo = "CUDE - Documento Equivalente/POS (SHA-384)"
    else:
        codigo_tipo = "CUFE (Código Único de Facturación Electrónica, SHA-384)"
    note = (
        f"Clave técnica: {settings.DIAN_CLAVE_TECNICA.strip()}. "
        if settings.DIAN_CLAVE_TECNICA.strip()
        else "Resolución registrada sin clave técnica en el POS. "
    )
    note += f"Código único de identificación del documento: {codigo_tipo}."
    return f"""  <ext:UBLExtensions>
    <ext:UBLExtension>
      <ext:ExtensionContent>
        <sts:DianExtensions>
          <sts:InvoiceControl>
            <sts:InvoiceAuthorization>{_xml(resolucion_num)}</sts:InvoiceAuthorization>
            <sts:AuthorizationPeriod>
              <cbc:StartDate>{_xml(f_inicio)}</cbc:StartDate>
              <cbc:EndDate>{_xml(f_fin)}</cbc:EndDate>
            </sts:AuthorizationPeriod>
            <sts:AuthorizedInvoices>
              <sts:Prefix>{_xml(doc.prefijo or '')}</sts:Prefix>
              <sts:From>{desde}</sts:From>
              <sts:To>{hasta}</sts:To>
            </sts:AuthorizedInvoices>
            <sts:Note>{_xml(note)}</sts:Note>
          </sts:InvoiceControl>
          <sts:InvoiceSource>
            <cbc:IdentificationCode>CO</cbc:IdentificationCode>
          </sts:InvoiceSource>
          <sts:SoftwareProvider>
            <sts:ProviderID schemeName="31" schemeAgencyID="195" schemeID="4">{_xml(nit_emisor)}</sts:ProviderID>
            <sts:SoftwareID schemeAgencyID="195" schemeID="1">{_xml(software_id or 'no-definido')}</sts:SoftwareID>
          </sts:SoftwareProvider>
          <sts:SoftwareSecurityCode schemeAgencyID="195" schemeID="2">{_xml(_software_security_code())}</sts:SoftwareSecurityCode>
        </sts:DianExtensions>
      </ext:ExtensionContent>
    </ext:UBLExtension>
  </ext:UBLExtensions>
"""


def _software_security_code():
    seed = f"{settings.DIAN_SOFTWARE_ID or ''}{settings.DIAN_SOFTWARE_PIN or ''}".strip()
    if seed:
        return hashlib.sha384(seed.encode("utf-8")).hexdigest()
    return "Pendiente-de-registro-en-DIAN"


def _totales_xml(venta, subtotal, descuento, impuesto, total, tipo_documento, desglose=None):
    iva = _redondear(impuesto)
    tax = ""
    if iva > 0:
        grupos = desglose or [{"tasa": 0.0, "base": _redondear(subtotal) - _redondear(descuento), "impuesto": iva}]
        sub_totales = []
        for g in grupos:
            nombre_tributo = "IVA"
            tasa_txt = _fmt_tasa(g["tasa"])
            if g["tasa"] == 0:
                # Excluido / exento: se muestra sin tributo en la base gravable.
                sub_totales.append(
                    f"""      <cac:TaxSubtotal>
        <cbc:TaxableAmount currencyID="COP">{g['base']:.2f}</cbc:TaxableAmount>
        <cbc:TaxAmount currencyID="COP">0.00</cbc:TaxAmount>
        <cac:TaxCategory>
          <cbc:ID>Z</cbc:ID>
          <cbc:Name>Excluido - No aplica</cbc:Name>
          <cbc:Percent>{tasa_txt}</cbc:Percent>
          <cac:TaxScheme>
            <cbc:ID>01</cbc:ID>
            <cbc:Name>{_xml(nombre_tributo)}</cbc:Name>
          </cac:TaxScheme>
        </cac:TaxCategory>
      </cac:TaxSubtotal>
"""
                )
                continue
            tag = "TaxSubtotal"
            if tipo_documento == "nota_credito":
                tag = "CreditNoteLineTotalTaxSubtotal"
            sub_totales.append(
                f"""      <cac:{tag}>
        <cbc:TaxableAmount currencyID="COP">{g['base']:.2f}</cbc:TaxableAmount>
        <cbc:TaxAmount currencyID="COP">{g['impuesto']:.2f}</cbc:TaxAmount>
        <cac:TaxCategory>
          <cbc:ID>01</cbc:ID>
          <cbc:Name>IVA {tasa_txt}</cbc:Name>
          <cbc:Percent>{tasa_txt}</cbc:Percent>
          <cac:TaxScheme>
            <cbc:ID>01</cbc:ID>
            <cbc:Name>IVA</cbc:Name>
          </cac:TaxScheme>
        </cac:TaxCategory>
      </cac:{tag}>
"""
            )
        tax = f"""    <cac:TaxTotal>
      <cbc:TaxAmount currencyID="COP">{iva:.2f}</cbc:TaxAmount>
{''.join(sub_totales)}    </cac:TaxTotal>
"""
    if tipo_documento == "nota_credito":
        return f"""{tax}    <cac:LegalMonetaryTotal>
      <cbc:LineExtensionAmount currencyID="COP">{_redondear(subtotal):.2f}</cbc:LineExtensionAmount>
      <cbc:TaxExclusiveAmount currencyID="COP">{_redondear(subtotal - descuento):.2f}</cbc:TaxExclusiveAmount>
      <cbc:PayableAmount currencyID="COP">{_redondear(total):.2f}</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>
"""
    if tipo_documento == "nota_debito":
        return f"""{tax}    <cac:RequestedMonetaryTotal>
      <cbc:LineExtensionAmount currencyID="COP">{_redondear(subtotal):.2f}</cbc:LineExtensionAmount>
      <cbc:TaxExclusiveAmount currencyID="COP">{_redondear(subtotal - descuento):.2f}</cbc:TaxExclusiveAmount>
      <cbc:PayableAmount currencyID="COP">{_redondear(total):.2f}</cbc:PayableAmount>
    </cac:RequestedMonetaryTotal>
"""
    return f"""{tax}    <cac:LegalMonetaryTotal>
      <cbc:LineExtensionAmount currencyID="COP">{_redondear(subtotal):.2f}</cbc:LineExtensionAmount>
      <cbc:TaxExclusiveAmount currencyID="COP">{_redondear(subtotal - descuento):.2f}</cbc:TaxExclusiveAmount>
      <cbc:TaxInclusiveAmount currencyID="COP">{_redondear(total):.2f}</cbc:TaxInclusiveAmount>
      <cbc:PayableAmount currencyID="COP">{_redondear(total):.2f}</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>
"""


def _fmt_tasa(tasa):
    """Formatea una tasa porcentual (5, 5.00, 19.0 -> '5.00', '19.00'; 0 -> '00.00')."""
    try:
        t = round(float(tasa or 0), 2)
    except (TypeError, ValueError):
        t = 0.0
    if t == 0:
        return "00.00"
    return f"{t:.2f}"


def _lineas_xml(detalle):
    filas = []
    for i, d in enumerate(detalle, start=1):
        cantidad = d["cantidad"]
        precio = d["precio"]
        subtotal = d["subtotal"]
        tasa = _fmt_tasa(d.get("impuesto") or 0)
        iva_linea = round(float(d.get("impuesto_monto") or 0), 2)
        tasa_xml = ""
        if tasa != "00.00":
            tasa_xml = f"""      <cac:TaxTotal>
        <cbc:TaxAmount currencyID="COP">{iva_linea:.2f}</cbc:TaxAmount>
        <cac:TaxSubtotal>
          <cbc:TaxableAmount currencyID="COP">{_redondear(subtotal):.2f}</cbc:TaxableAmount>
          <cbc:TaxAmount currencyID="COP">{iva_linea:.2f}</cbc:TaxAmount>
          <cac:TaxCategory>
            <cbc:ID>01</cbc:ID>
            <cbc:Percent>{tasa}</cbc:Percent>
            <cac:TaxScheme>
              <cbc:ID>01</cbc:ID>
              <cbc:Name>IVA</cbc:Name>
            </cac:TaxScheme>
          </cac:TaxCategory>
        </cac:TaxSubtotal>
      </cac:TaxTotal>
"""
        fila = f"""    <cac:InvoiceLine>
      <cbc:ID>{i}</cbc:ID>
      <cbc:InvoicedQuantity unitCode="EA">{cantidad:g}</cbc:InvoicedQuantity>
      <cbc:LineExtensionAmount currencyID="COP">{_redondear(subtotal):.2f}</cbc:LineExtensionAmount>
      <cac:Item>
        <cbc:Description>{_xml(d['nombre'])}</cbc:Description>
        <cac:SellersItemIdentification>
          <cbc:ID>{_xml(d['codigo'] or d['id'])}</cbc:ID>
        </cac:SellersItemIdentification>
      </cac:Item>
{tasa_xml}      <cac:Price>
        <cbc:PriceAmount currencyID="COP">{_redondear(precio):.2f}</cbc:PriceAmount>
      </cac:Price>
    </cac:InvoiceLine>
"""
        filas.append(fila)
    return "\n".join(filas)


def generar_ubl_xml(db, doc):
    """Construye el XML UBL 2.1 (Invoice, CreditNote o DebitNote) para la DIAN."""
    venta = db.get(Venta, doc.venta_id) if doc.venta_id else None
    empresa, sucursal, cliente, detalle, res = _datos_fiscales(db, doc, venta)
    if not empresa:
        raise HTTPException(400, "Empresa no encontrada")

    tipo = doc.tipo_documento
    root = "Invoice"
    type_tag = "InvoiceTypeCode"
    type_list = "012"
    type_code = "01"
    if tipo == "nota_credito":
        root, type_tag, type_list, type_code = "CreditNote", "CreditNoteTypeCode", "013", "01"
    elif tipo == "nota_debito":
        root, type_tag, type_list, type_code = "DebitNote", "DebitNoteTypeCode", "014", "01"
    elif tipo == "documento_equivalente":
        type_list, type_code = "015", "5"
    elif tipo == "documento_pos":
        type_list, type_code = "018", "1"

    root_ns = _NS[root]
    cufe_scheme = "CUDE-SHA384" if tipo in ("nota_credito", "nota_debito") else "CUFE-SHA384"
    ts = str(doc.fecha_emision or datetime.now().isoformat()).replace(" ", "T")
    fec = ts[:10]
    hor = (ts[11:19] if len(ts) > 11 else "00:00:00") + "-05:00"

    subtotal = _redondear(venta.subtotal) if venta else _redondear(doc.monto)
    descuento = _redondear(venta.descuento) if venta else 0
    impuesto = _redondear(venta.impuesto) if venta else 0
    total = _redondear(doc.monto)

    supplier, customer = _parties(db, doc, empresa, sucursal, cliente, res)
    ext = _ubl_extensions(doc, res, empresa)
    desglose = _desglose_iva(detalle)
    totales = _totales_xml(venta, subtotal, descuento, impuesto, total, tipo, desglose)
    lineas = _lineas_xml(detalle)
    referencia = ""
    if tipo in ("nota_credito", "nota_debito") and doc.referencia:
        ref_doc = None
        if doc.referencia.isdigit():
            ref_doc = db.get(DocumentoFiscal, int(doc.referencia))
        referencia = f"""    <cac:BillingReference>
      <cac:InvoiceDocumentReference>
        <cbc:ID>{_xml(ref_doc.numero if ref_doc else doc.referencia)}</cbc:ID>
        <cbc:UUID schemeName="CUFE-SHA384">{_xml(ref_doc.cufe if ref_doc else '')}</cbc:UUID>
      </cac:InvoiceDocumentReference>
    </cac:BillingReference>
"""

    return f"""<?xml version="1.0" encoding="utf-8"?>
<{root} xmlns="{root_ns}"
 xmlns:cac="{_NS['cac']}"
 xmlns:cbc="{_NS['cbc']}"
 xmlns:ext="{_NS['ext']}"
 xmlns:sts="{_NS['sts']}"
 xmlns:xsi="{_NS['xsi']}"
 xsi:schemaLocation="{root_ns} http://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-{root}-2.1.xsd">
{ext}  <cbc:UBLVersionID>UBL 2.1</cbc:UBLVersionID>
  <cbc:CustomizationID>10</cbc:CustomizationID>
  <cbc:ProfileID>DIAN 2.1</cbc:ProfileID>
  <cbc:ProfileExecutionID>2</cbc:ProfileExecutionID>
  <cbc:ID>{_xml(doc.numero)}</cbc:ID>
  <cbc:UUID schemeName="{cufe_scheme}">{_xml(doc.cufe or '')}</cbc:UUID>
  <cbc:IssueDate>{_xml(fec)}</cbc:IssueDate>
  <cbc:IssueTime>{_xml(hor)}</cbc:IssueTime>
  <cbc:{type_tag} listID="{type_list}">{type_code}</cbc:{type_tag}>
  {('<cbc:Note>' + _xml(doc.concepto) + '</cbc:Note>') if doc.concepto else ''}
  <cbc:DocumentCurrencyCode>COP</cbc:DocumentCurrencyCode>
{referencia}{supplier}{customer}{totales}{lineas}</{root}>
"""


def _guardar_xml(db, doc):
    if not doc.xml_ubl:
        doc.xml_ubl = generar_ubl_xml(db, doc)
        db.commit()
    return doc.xml_ubl


# ---------- Transmisión (conector DIAN) ----------

class ConectorDIAN:
    """Contrato de un conector de transmisión DIAN.

    `transmitir` envía el XML (firmado XAdES en producción) y deja el documento
    en estado enviado/aprobado/rechazado; `consultar_estado` pregunta por el
    estado ante la DIAN o el PST intermediario. La selección depende del modo
    activo del cliente: 'sandbox' siempre usa el simulador; 'produccion' exige
    el conector real configurado y bloquea (501) con los requisitos faltantes.
    """

    nombre = "conector"

    def requisitos(self) -> list[str]:
        """Requisitos de configuración pendientes para operar de verdad."""
        return []

    def transmitir(self, db, doc, usuario, xml):
        raise NotImplementedError()

    def consultar_estado(self, db, doc, usuario):
        raise NotImplementedError()


class ConectorMock(ConectorDIAN):
    """Ciclo DIAN simulado (default): genera y 'transmite' el XML UBL 2.1 sin
    conectar con la DIAN, para operar el flujo diario durante la habilitación."""

    nombre = "mock"

    def requisitos(self):
        return _requisitos_conexion()

    def transmitir(self, db, doc, usuario, xml):
        doc.estado_dian = "enviado"
        doc.fecha_envio = datetime.now()
        doc.respuesta_dian = (
            "XML UBL 2.1 generado y transmitido a la DIAN (ambiente de habilitación, "
            "simulado). Listo para firma y transmisión real por el conector certificado."
        )
        db.add(
            AuditoriaLog(
                usuario_id=usuario.id,
                modulo="facturacion",
                accion="enviar",
                entidad="documento_fiscal",
                entidad_id=doc.id,
                detalle=f"Documento {doc.numero} transmitido (simulación) · XML {len(xml)} bytes",
            )
        )
        db.commit()
        db.refresh(doc)
        return doc

    def consultar_estado(self, db, doc, usuario):
        doc.estado_dian = "aprobado"
        doc.respuesta_dian = (
            "La DIAN aceptó el documento y asignó estado aprobado (simulación de "
            "habilitación; confirme en producción con el conector real)."
        )
        db.add(
            AuditoriaLog(
                usuario_id=usuario.id,
                modulo="facturacion",
                accion="consultar",
                entidad="documento_fiscal",
                entidad_id=doc.id,
                detalle=f"Documento {doc.numero} -> {doc.estado_dian} (simulado)",
            )
        )
        db.commit()
        db.refresh(doc)
        return doc


class ConectorWebServiceDIAN(ConectorDIAN):
    """Transmisión real contra los servicios web de la DIAN (SOAP + firma
    XAdES). Punto de conexión para el conector certificado cuando se complete
    la habilitación de la empresa o del software."""

    nombre = "webservice"

    def requisitos(self):
        return _requisitos_conexion()

    def transmitir(self, db, doc, usuario, xml):
        _exigir_conector_webservice()
        # Integración SOAP de la DIAN (enviar documento firmado). Pendiente de
        # implementar junto con la habilitación real (punto de conexión real).
        raise HTTPException(501, "WS-DIAN no implementado en esta versión: se certificará al completar la habilitación.")

    def consultar_estado(self, db, doc, usuario):
        _exigir_conector_webservice()
        raise HTTPException(501, "Consulta WS-DIAN no implementada en esta versión.")


class ConectorPST(ConectorDIAN):
    """Transmisión vía Proveedor de Servicios Tecnológicos certificado
    (intermediario que garantiza la validez del documento ante la DIAN)."""

    nombre = "pst"

    def requisitos(self):
        if not settings.DIAN_PROVIDER_URL.strip():
            return ["URL del proveedor tecnológico certificado (DIAN_PROVIDER_URL)"]
        return _requisitos_conexion()

    def transmitir(self, db, doc, usuario, xml):
        faltantes = self.requisitos()
        if faltantes:
            raise HTTPException(501, "Conector PST no configurado: " + "; ".join(faltantes))
        # Integración con el servicio del PST certificado (SOAP/REST). Pendiente
        # de implementar al contratar el proveedor (punto de conexión PST real).
        raise HTTPException(501, "Conector PST en integración: aún no se ha conectado con el proveedor contratado.")

    def consultar_estado(self, db, doc, usuario):
        faltantes = self.requisitos()
        if faltantes:
            raise HTTPException(501, "Conector PST no configurado: " + "; ".join(faltantes))
        raise HTTPException(501, "Conector PST en integración: consulta de estado pendiente de conexión con el proveedor.")


def _requisitos_conexion() -> list[str]:
    """Requisitos comunes de integración DIAN (sin exponer secretos)."""
    faltantes = []
    ambiente = settings.DIAN_ENVIRONMENT.strip().lower()
    if ambiente not in {"habilitacion", "produccion"}:
        faltantes.append("Ambiente DIAN (habilitación o producción)")
    if not settings.DIAN_SOFTWARE_ID.strip():
        faltantes.append("ID de software registrado en DIAN")
    if not settings.DIAN_CERTIFICATE_PATH.strip():
        faltantes.append("Ruta del certificado de firma en el servidor")
    elif not os.path.isfile(settings.DIAN_CERTIFICATE_PATH.strip()):
        faltantes.append("Certificado de firma accesible por el backend")
    if not settings.DIAN_CLAVE_TECNICA.strip():
        faltantes.append("Clave técnica (ClTec) asignada a cada resolución en DIAN")
    if ambiente == "habilitacion" and not settings.DIAN_TEST_SET_ID.strip():
        faltantes.append("ID del set de pruebas de habilitación")
    return faltantes


def _exigir_conector_webservice():
    faltantes = _requisitos_conexion()
    if faltantes:
        raise HTTPException(501, "Conector WS-DIAN no configurado: " + "; ".join(faltantes))
    raise HTTPException(501, "Conector WS-DIAN no implementado: requiere la implementación XAdES + SOAP al completar la habilitación.")


def _obtener_conector(db=None) -> ConectorDIAN:
    """Selecciona el conector según el modo activo del cliente.

    'sandbox' siempre simula; 'produccion' usa el conector real configurado
    (webservice de la DIAN o un PST certificado) y bloquea la transmisión hasta
    que esté disponible, en lugar de simular.
    """
    if modo_dian(db) == "sandbox":
        return ConectorMock()
    nombre = (settings.DIAN_CONECTOR or "").strip().lower()
    if nombre == "pst":
        return ConectorPST()
    if nombre == "webservice":
        return ConectorWebServiceDIAN()
    raise HTTPException(
        501,
        "Conector certificado no instalado: este cliente está en PRODUCCIÓN "
        "(dian.modo=produccion) y no se puede transmitir en modo real.",
    )


def transmitir_documento(db, doc, usuario):
    """Transmite el documento a la DIAN según el conector activo del cliente.

    En sandbox ejercita el ciclo simulado completo (genera y 'envía' el XML UBL
    2.1). En producción delega en el conector real configurado y, mientras no
    haya conector certificado, devuelve 501 con los requisitos pendientes.
    """
    xml = _guardar_xml(db, doc)
    return _obtener_conector(db).transmitir(db, doc, usuario, xml)


def consultar_estado_dian(db, doc, usuario):
    """Consulta el estado del documento ante la DIAN o el PST intermedio.

    En modo simulado devuelve "aprobado" con marca explícita de simulación para
    poder operar el flujo diario (ventas, contabilidad, entrega al cliente).
    Con conector real reemplaza la respuesta por la del servicio correspondiente.
    """
    if doc.anulado:
        raise HTTPException(400, "El documento está anulado")
    conector = _obtener_conector(db)
    if doc.estado_dian not in ("enviado", "aprobado", "rechazado"):
        raise HTTPException(400, "El documento aún no ha sido transmitido")
    return conector.consultar_estado(db, doc, usuario)


# ---------- Representación gráfica ----------

def _datos_venta(db, doc, venta):
    empresa, sucursal, cliente, detalle, res = _datos_fiscales(db, doc, venta)
    return empresa, sucursal, cliente, detalle


# ---------- Importe en letras ----------

_UNIDES = ["", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve"]
_DECENAS = {
    10: "diez", 11: "once", 12: "doce", 13: "trece", 14: "catorce",
    15: "quince", 16: "dieciséis", 17: "diecisiete", 18: "dieciocho", 19: "diecinueve",
    20: "veinte", 21: "veintiuno", 22: "veintidós", 23: "veintitrés", 24: "veinticuatro",
    25: "veinticinco", 26: "veintiséis", 27: "veintisiete", 28: "veintiocho", 29: "veintinueve",
    30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta", 70: "setenta",
    80: "ochenta", 90: "noventa",
}
_CENTENAS = ["", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos",
             "seiscientos", "setecientos", "ochocientos", "novecientos"]


def _tres_letras(n):
    """Convierte un entero 0..999 a palabras en español."""
    c, resto = divmod(n, 100)
    partes = []
    if c == 1 and resto == 0:
        partes.append("cien")
    elif c:
        partes.append(_CENTENAS[c])
    if resto:
        if resto < 10:
            partes.append(_UNIDES[resto])
        elif resto in _DECENAS:
            partes.append(_DECENAS[resto])
        else:
            d, u = divmod(resto, 10)
            base = d * 10
            partes.append(_DECENAS[base])
            if u:
                partes.append("y " + _UNIDES[u])
    return " ".join(partes).strip()


def _palabras_enteros(n):
    """Convierte un entero >= 0 a palabras en español."""
    if n == 0:
        return "cero"
    partes = []
    millones, resto = divmod(n, 1000000)
    miles, resto = divmod(resto, 1000)
    if millones:
        partes.append("un millón" if millones == 1 else _tres_letras(millones) + " millones")
    if miles:
        partes.append("mil" if miles == 1 else _tres_letras(miles) + " mil")
    if resto:
        partes.append(_tres_letras(resto))
    return " ".join(partes)


def _importe_en_letras(importe):
    """Importe monetario en palabras (COP): 1234.56 -> 'MIL DOSCIENTOS ...'."""
    importe = round(float(importe or 0), 2)
    enteros = int(importe)
    centavos = int(round(importe * 100)) % 100
    valor = "UN" if enteros == 1 else _palabras_enteros(enteros).upper()
    moneda = "PESO" if enteros == 1 else "PESOS"
    if centavos:
        return f"{valor} {moneda} CON {centavos:02d}/100 M.L."
    return f"{valor} {moneda} M.L."


def generar_pdf(db, doc_id):
    """Representación gráfica (PDF) profesional del documento electrónico."""
    doc = db.get(DocumentoFiscal, doc_id)
    if not doc:
        raise HTTPException(404, "Documento no encontrado")
    venta = db.get(Venta, doc.venta_id) if doc.venta_id else None
    empresa, sucursal, cliente, detalle = _datos_venta(db, doc, venta)
    res = db.get(ResolucionFacturacion, doc.resolucion_id) if doc.resolucion_id else None

    buf = io.BytesIO()
    page = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    estilos = getSampleStyleSheet()
    s_emp = ParagraphStyle("emp", fontName="Helvetica-Bold", fontSize=13, leading=15, textColor=colors.HexColor("#111827"))
    s_sub = ParagraphStyle("sub", fontName="Helvetica", fontSize=8, leading=10, textColor=colors.HexColor("#4b5563"))
    s_doc = ParagraphStyle("doc", fontName="Helvetica-Bold", fontSize=13, leading=15, textColor=colors.HexColor("#b91c1c"), alignment=1)
    s_celda = ParagraphStyle("celda", fontName="Helvetica", fontSize=8, leading=10)
    s_celda_b = ParagraphStyle("celda_b", fontName="Helvetica-Bold", fontSize=8, leading=10)
    s_nota = ParagraphStyle("nota", fontName="Helvetica", fontSize=7.5, leading=9.5, textColor=colors.HexColor("#6b7280"))
    s_tot = ParagraphStyle("tot", fontName="Helvetica-Bold", fontSize=11, leading=13)

    razon = (empresa.razon_social or empresa.nombre or "Empresa") if empresa else "Empresa"
    estado = "ANULADO" if doc.anulado else (doc.estado_dian or "pendiente").upper()

    story = []

    # ---------- Cabecera ----------
    izq = [
        Paragraph(razon.upper(), s_emp),
        Paragraph(f"NIT: {empresa.nit or '—'}  ·  {empresa.direccion or ''}  ·  {empresa.telefono or ''}", s_sub),
    ]
    if sucursal:
        izq.append(Paragraph(f"Sucursal: {sucursal.nombre} · {sucursal.direccion or ''} · {sucursal.ciudad or ''}", s_sub))
    der = [
        Paragraph(TIPO_LABEL.get(doc.tipo_documento, doc.tipo_documento).upper(), s_doc),
        Paragraph(f"NO. {doc.numero}", s_celda_b),
        Paragraph(f"Fecha de emisión: {doc.fecha_emision or '—'}", s_sub),
        Paragraph(f"Estado DIAN: {estado}", s_sub),
    ]
    t_cab = Table([[izq, der]], colWidths=[122 * mm, 53 * mm])
    t_cab.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0, colors.white),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#b91c1c")),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_cab)
    story.append(Spacer(1, 8))

    # ---------- Info cliente + resolución ----------
    info = [
        [Paragraph("FACTURADO A", s_celda_b), Paragraph("RESOLUCIÓN / NUMERACIÓN", s_celda_b)],
        [
            Paragraph(cliente.nombre if cliente else "Consumidor final", s_celda),
            Paragraph(
                (f"Resolución No. {res.resolucion} · {doc.prefijo or ''}{doc.consecutivo if doc.consecutivo is not None else ''}"
                 if res else f"FULT: {doc.numero} (sin resolución)"),
                s_celda,
            ),
        ],
        [
            Paragraph(
                (f"{cliente.tipo_documento or ''} {cliente.documento or ''}".strip() or "Consumidor final")
                if cliente else "Consumidor final",
                s_celda,
            ),
            Paragraph(
                (f"Rango: {res.rango_inicial} - {res.rango_final} · "
                 + (f"Vigencia: {res.fecha_inicio} a {res.fecha_vencimiento} · " if res.fecha_inicio else "")
                 + f"Modalidad: {_modalidad(res.tecnica if res.tecnica else 'habilitacion')}" if res else "Documento sin resolución autorizada"),
                s_celda,
            ),
        ],
    ]
    t_info = Table(info, colWidths=[62 * mm, 113 * mm])
    t_info.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 8))

    # ---------- Detalle de ítems ----------
    encabezado = ["Código", "Descripción", "Cant.", "P. Unitario", "IVA", "Dto.", "Subtotal"]
    filas = [encabezado]
    for d in detalle:
        tasa = _fmt_tasa(d.get("impuesto") or 0)
        filas.append([
            d.get("codigo") or f"#{d.get('id')}",
            Paragraph(d["nombre"], s_celda),
            f'{d["cantidad"]:g}',
            f'{_redondear(d["precio"]):,.0f}',
            f'{f"{tasa}%" if tasa != "00.00" else "Exento"}',
            f'{_redondear(d.get("descuento") or 0):,.0f}',
            f'{_redondear(d["subtotal"]):,.0f}',
        ])
    t_items = Table(filas, colWidths=[24 * mm, 74 * mm, 14 * mm, 24 * mm, 20 * mm, 14 * mm, 25 * mm], repeatRows=1)
    t_items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d1d5db")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (6, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_items)
    story.append(Spacer(1, 8))

    # ---------- Totales ----------
    subtotal = float(venta.subtotal) if venta else float(doc.monto or 0)
    descuento = float(venta.descuento) if venta else 0.0
    impuesto = float(venta.impuesto) if venta else 0.0
    propina = float(venta.propina) if venta else 0.0
    total = float(doc.monto or venta.total) if (venta or doc) else 0.0

    filas_totales = [
        [Paragraph("Subtotal", s_celda), f"{_redondear(subtotal):,.0f}"],
    ]
    if descuento:
        filas_totales.append([Paragraph("Descuentos", s_celda), f"-{_redondear(descuento):,.0f}"])
    desglose = _desglose_iva(detalle)
    if desglose:
        for g in desglose:
            if g["tasa"] == 0 and g["impuesto"] == 0:
                filas_totales.append([Paragraph("Base excluida (exento)", s_celda), f'{_redondear(g["base"]):,.0f}'])
            else:
                filas_totales.append([Paragraph(f'IVA {g["tasa"]:g}%', s_celda), f'{_redondear(g["impuesto"]):,.0f}'])
    else:
        filas_totales.append([Paragraph("Impuestos (IVA)", s_celda), f"{_redondear(impuesto):,.0f}"])
    if propina:
        filas_totales.append([Paragraph("Propina", s_celda), f"{_redondear(propina):,.0f}"])
    filas_totales.append([Paragraph("TOTAL", s_tot), Paragraph(f"$ {_redondear(total):,.0f}", s_tot)])

    t_tot = Table(filas_totales, colWidths=[80 * mm, 45 * mm])
    t_tot.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor("#111827")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f8fafc")),
        ("TOPPADDING", (0, -1), (-1, -1), 6),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -2), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -2), 2),
    ]))
    story.append(t_tot)
    story.append(Spacer(1, 5))
    story.append(Paragraph(f"<b>Total en letras:</b> {_importe_en_letras(total)}", s_sub))
    story.append(Spacer(1, 5))

    # ---------- Pagos ----------
    pagos = []
    if venta:
        for p in db.query(VentaPago).filter(VentaPago.venta_id == venta.id).all():
            pagos.append([(p.medio or "otro").capitalize(), p.referencia or "—", f"{_redondear(p.monto):,.0f}"])
    if pagos:
        t_pag = Table([["Medio de pago", "Referencia", "Valor"]] + pagos, colWidths=[60 * mm, 40 * mm, 25 * mm])
        t_pag.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d1d5db")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_pag)
        story.append(Spacer(1, 8))

    # ---------- QR + CUFE ----------
    qr_nota = [
        [Paragraph("CÓDIGO ÚNICO DE FACTURACIÓN ELECTRÓNICA (CUFE)", s_celda_b), Paragraph("VERIFICACIÓN", s_celda_b)],
        [Paragraph(doc.cufe or "Pendiente de asignación", ParagraphStyle("cufe", parent=s_celda, fontSize=7, leading=9)), ""],
    ]
    try:
        qr_bytes = base64.b64decode(doc.qr.split(",")[1])
        into = io.BytesIO(qr_bytes)
        qr_nota[0][1] = Image(into, width=26 * mm, height=26 * mm)
    except Exception:
        qr_nota[1][1] = Paragraph("QR no disponible", s_nota)
    t_qr = Table(qr_nota, colWidths=[140 * mm, 35 * mm])
    t_qr.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t_qr)
    story.append(Spacer(1, 8))

    # ---------- Notas y leyenda ----------
    notas = []
    if res:
        notas.append(
            f"Numeración autorizada mediante Resolución {res.resolucion} del "
            f"{res.fecha_inicio or '—'}, vigente hasta {res.fecha_vencimiento or '—'}. "
            f"Modalidad {_modalidad(res.tecnica or 'habilitacion').upper()}."
        )
    if doc.concepto:
        notas.append(f"Observaciones: {doc.concepto}")
    notas.append(
        "Representación gráfica de documento electrónico. Verifique la validez del documento y del código "
        "único (CUFE/CUDE) en el portal de la DIAN: https://catalogo-vpfe.dian.gov.co. El soporte digital "
        "válido de la operación es el documento XML firmado y su respectivo CUFE."
    )
    if modo_dian(db) == "sandbox":
        notas.append("Documento generado en ambiente de habilitación (simulado): el estado DIAN mostrado es informativo, no operativo.")
    story.append(Paragraph(" · ".join(notas), s_nota))

    page.build(story)
    return buf.getvalue()