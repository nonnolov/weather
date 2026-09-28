from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import re


class LocationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    elevation_m: float | None = None
    timezone: str = Field(default="UTC", max_length=64)
    country_code: str | None = Field(default=None, max_length=2)
    description: str | None = None
    is_active: bool = True
    provider: str = Field(default="open_meteo", max_length=64)


class LocationCreate(LocationBase):
    pass


class LocationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    elevation_m: float | None = None
    timezone: str | None = Field(default=None, max_length=64)
    country_code: str | None = Field(default=None, max_length=2)
    description: str | None = None
    is_active: bool | None = None
    provider: str | None = Field(default=None, max_length=64)


class LocationRead(LocationBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
