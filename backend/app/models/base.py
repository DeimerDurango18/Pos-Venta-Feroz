from datetime import datetime

from sqlalchemy import Column, DateTime, func
from sqlalchemy.orm import declared_attr

from ..database import Base


class BaseModel(Base):
    __abstract__ = True

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
