from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from urllib.parse import quote_plus


PROJECT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # Puede definirse una URL completa (producción) o los mismos valores que
    # usa docker-compose (desarrollo local). Evita que ambos entornos usen
    # contraseñas distintas por accidente.
    DATABASE_URL: str = ""
    SA_PASSWORD: str = "Pos2026Clave01!"
    DB_NAME: str = "posdb"
    DB_PORT_HOST: int = 26433
    SECRET_KEY: str = "change-me-in-production-9f8e7d6c5b4a392817260"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    DEBUG: bool = False
    # Lista separada por comas. En producción incluya exclusivamente los dominios
    # desde los que se sirve el POS.
    CORS_ORIGINS: str = (
        "http://localhost:28742,http://127.0.0.1:28742,"
        "http://localhost:5173,http://127.0.0.1:5173"
    )
    # DIAN. Nunca se guardan certificados, PIN ni claves técnicas en la base de datos.
    # La integración real se habilita únicamente después de superar las pruebas DIAN.
    DIAN_ENVIRONMENT: str = "disabled"  # disabled | habilitacion | produccion
    DIAN_SOFTWARE_ID: str = ""
    DIAN_SOFTWARE_PIN: str = ""  # PIN del software que DIAN entrega al activar el software
    DIAN_TEST_SET_ID: str = ""
    DIAN_CERTIFICATE_PATH: str = ""
    DIAN_CERTIFICATE_PASSWORD: str = ""
    # Clave técnica (ClTec) que la DIAN asigna a cada resolución de numeración.
    # Sin ella el CUFE (SHA-384) es determinístico pero la DIAN lo rechaza.
    DIAN_CLAVE_TECNICA: str = ""
    # Dirección del servicio de un proveedor tecnológico certificado. Este POS
    # no intenta transmitir directamente hasta contar con el conector firmado.
    DIAN_PROVIDER_URL: str = ""
    # Modo simulado del ciclo DIAN (enviar/consultar) para operar a diario sin
    # conector certificado. Pasa a 0 al conectar un conector UBL/XAdES real.
    DIAN_MOCK_TRANSMISSION: bool = True
    # Conector DIAN activo: mock | webservice | pst. Con "mock" (o sin conector
    # configurado) el modo produccion queda bloqueado (501) y nunca simula.
    # "webservice" usa los WS de la DIAN; "pst" usa un proveedor tecnológico
    # certificado (DIAN_PROVIDER_URL) en nombre del software.
    DIAN_CONECTOR: str = "mock"

    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    def database_url(self) -> str:
        if self.DATABASE_URL.strip():
            return self.DATABASE_URL.strip()
        return (
            f"mssql+pyodbc://sa:{quote_plus(self.SA_PASSWORD)}@127.0.0.1:"
            f"{self.DB_PORT_HOST}/{quote_plus(self.DB_NAME)}"
            "?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
        )

    # El mismo .env también alimenta Docker/SQL Server. Esas claves no son
    # configuración de FastAPI y deben ignorarse, no impedir el arranque.
    model_config = SettingsConfigDict(
        env_file=PROJECT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
