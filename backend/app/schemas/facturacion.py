from datetime import date, datetime

from pydantic import BaseModel


class ResolucionCreate(BaseModel):
    resolucion: str
    prefijo: str
    tipo_documento: str = "factura"
    rango_inicial: int = 1
    rango_final: int = 100000
    fecha_inicio: date | None = None
    fecha_vencimiento: date | None = None
    tecnica: str = "habilitacion"


class ResolucionOut(BaseModel):
    id: int
    resolucion: str
    prefijo: str
    tipo_documento: str
    rango_inicial: int | None = None
    rango_final: int | None = None
    numero_actual: int | None = None
    fecha_inicio: date | None = None
    fecha_vencimiento: date | None = None
    activa: bool | None = None
    tecnica: str | None = None

    class Config:
        from_attributes = True


class GenerarDocumentoIn(BaseModel):
    tipo_documento: str = "factura"  # factura, nota_credito, nota_debito, documento_equivalente, documento_pos
    monto: float | None = None  # para notas: total a facturar
    concepto: str | None = None
    resolucion_id: int | None = None


class DocumentoFiscalOut(BaseModel):
    id: int
    venta_id: int | None = None
    resolucion_id: int | None = None
    referencia: str | None = None
    tipo_documento: str
    prefijo: str | None = None
    consecutivo: int | None = None
    numero: str | None = None
    fecha_emision: str | None = None
    cufe: str | None = None
    estado_dian: str
    fecha_envio: datetime | None = None
    motivo_rechazo: str | None = None
    anulado: bool | None = None
    motivo_anulacion: str | None = None
    monto: float | None = None
    concepto: str | None = None
    created_at: datetime | None = None
    cliente: str | None = None
    respuesta_dian: str | None = None

    class Config:
        from_attributes = True