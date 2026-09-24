"""Reconcilia documentos fiscales emitidos sin el adquirente consumidor final.

Recalcula CUFE, QR y XML UBL con la lógica actual (NIT_CONSUMIDOR_FINAL =
"2222222222") para toda factura/nota ya emitida y actualiza la fila
únicamente cuando el valor cambia (idempotente). También normaliza clientes
que quedaron con el antiguo documento genérico 222222222222 o sin documento.

Uso (desde el repo, con el .env raíz):
    $env:PYTHONIOENCODING="utf-8"; python -X utf8 reparar_consumidor_final.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal  # noqa: E402
from app.dian import (  # noqa: E402
    NIT_CONSUMIDOR_FINAL,
    _redondear,
    generar_cufe,
    generar_qr_data_uri,
    generar_ubl_xml,
)
from app.models import Cliente, DocumentoFiscal, Empresa, Venta  # noqa: E402

ANTIGUO = "222222222222"


def main() -> None:
    db = SessionLocal()
    corregidos: list[str] = []
    correcciones_pk: set[int] = set()
    sin_cambio = 0
    try:
        clientes = (
            db.query(Cliente)
            .filter(
                (Cliente.documento.is_(None))
                | (Cliente.documento == "")
                | (Cliente.documento == ANTIGUO)
            )
            .all()
        )
        for c in clientes:
            viejo = (c.documento or "").strip()
            if viejo != ANTIGUO and viejo:
                continue
            c.documento = NIT_CONSUMIDOR_FINAL
            if not (c.tipo_documento or "").strip():
                c.tipo_documento = "CC"
            print(f"cliente {c.id}: documento {viejo or '-'} -> {NIT_CONSUMIDOR_FINAL}")
        db.flush()

        docs = db.query(DocumentoFiscal).all()
        for doc in docs:
            venta = db.get(Venta, doc.venta_id) if doc.venta_id else None
            cliente = (
                db.get(Cliente, venta.cliente_id) if venta and venta.cliente_id else None
            )
            empresa = db.get(Empresa, doc.empresa_id)
            subtotal = _redondear(venta.subtotal) if venta else _redondear(doc.monto)
            impuesto = _redondear(venta.impuesto) if venta else 0
            total = _redondear(doc.monto)
            nuevo_cufe = generar_cufe(
                empresa, doc, total, impuesto, subtotal,
                cliente=cliente, fecha=doc.fecha_emision,
            )
            if nuevo_cufe == (doc.cufe or ""):
                sin_cambio += 1
                continue
            doc.cufe = nuevo_cufe
            doc.qr = generar_qr_data_uri(nuevo_cufe, doc.numero, empresa, doc.fecha_emision, total)
            corregidos.append(f"{doc.numero} ({doc.tipo_documento})")
            correcciones_pk.add(doc.id)

        if correcciones_pk:
            for doc in docs:
                if doc.id in correcciones_pk:
                    doc.xml_ubl = generar_ubl_xml(db, doc)
                elif doc.tipo_documento in ("nota_credito", "nota_debito") and doc.referencia:
                    ref = None
                    if doc.referencia.isdigit():
                        ref = db.get(DocumentoFiscal, int(doc.referencia))
                    if ref is not None and ref.id in correcciones_pk:
                        doc.xml_ubl = generar_ubl_xml(db, doc)

        db.commit()
    finally:
        db.close()

    print(f"\nFacturas corregidas: {len(corregidos)}")
    for n in corregidos:
        print(f"  - {n}")
    print(f"Sin cambios: {sin_cambio}")


if __name__ == "__main__":
    main()