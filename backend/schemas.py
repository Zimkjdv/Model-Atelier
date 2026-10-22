"""Pure request schemas shared by application instances."""
from typing import Literal
from uuid import UUID
from urllib.parse import urlsplit
from pydantic import BaseModel, Field, field_validator
from backend.lora_settings import LoraSetting


class Settings(BaseModel):
    comfy_url: str

    @field_validator('comfy_url')
    @classmethod
    def validate_url(cls, value):
        value = value.strip().rstrip('/')
        parsed = urlsplit(value)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('請使用不含帳密、查詢參數的 HTTP 或 HTTPS 位址')
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError('連接埠無效') from exc
        return value


class ModelTarget(BaseModel):
    engine_url: str
    name: str = Field(min_length=1, max_length=2048)


class ModelMetadata(ModelTarget):
    version: str = Field(default='', max_length=100)
    notes: str = Field(default='', max_length=4000)
    source_url: str = Field(default='', max_length=2048)
    architecture: Literal['unknown', 'sd1', 'sdxl', 'sd3', 'flux', 'other'] = 'unknown'
    size_bytes: int | None = Field(default=None, strict=True, gt=0, le=9007199254740991)
    sha256: str = Field(default='', max_length=64, pattern=r'^(?:[0-9a-f]{64})?$')
    license_name: str = Field(default='', max_length=200)
    license_url: str = Field(default='', max_length=2048)

    @field_validator('version', 'notes', 'source_url', 'sha256', 'license_name', 'license_url', mode='before')
    @classmethod
    def clear_nullable_text(cls, value):
        return '' if value is None else value

    @field_validator('architecture', mode='before')
    @classmethod
    def clear_architecture(cls, value):
        return 'unknown' if value is None or value == '' else value

    @field_validator('size_bytes', mode='before')
    @classmethod
    def clear_size(cls, value):
        return None if isinstance(value, str) and value == '' else value

    @field_validator('sha256', mode='before')
    @classmethod
    def normalize_checksum(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator('source_url', 'license_url')
    @classmethod
    def validate_source(cls, value):
        return Settings.validate_url(value) if value.strip() else ''


class DraftInput(BaseModel):
    workflow_mode: Literal['text2image', 'image2image'] = 'text2image'
    image_asset_id: UUID | None = None
    reference_resize: Literal['fit', 'stretch'] = 'fit'
    loras: list[LoraSetting] = Field(default_factory=list, max_length=4)
    reference_ids: list[UUID] = Field(default_factory=list, max_length=8)
    title: str = Field(min_length=1, max_length=100)
    prompt: str = Field(default='', max_length=20000)
    negative_prompt: str = Field(default='', max_length=20000)
    engine_url: str
    checkpoint: str = Field(default='', max_length=2048)
    width: int = Field(default=1024, ge=64, le=8192, multiple_of=8, strict=True)
    height: int = Field(default=1024, ge=64, le=8192, multiple_of=8, strict=True)
    seed: str = '0'
    steps: int = Field(default=20, ge=1, le=150, strict=True)
    cfg: float = Field(default=7.0, ge=0, le=30, strict=True, allow_inf_nan=False)
    sampler_name: str = Field(default='euler', min_length=1, max_length=64, pattern=r'^[a-z][a-z0-9_]*$')
    scheduler: str = Field(default='normal', min_length=1, max_length=64, pattern=r'^[a-z][a-z0-9_]*$')
    denoise: float = Field(default=1.0, ge=0, le=1, strict=True, allow_inf_nan=False)
    revision: int | None = Field(default=None, ge=1)

    @field_validator('loras')
    @classmethod
    def unique_loras(cls, value):
        if len({item.name for item in value}) != len(value):
            raise ValueError('同一 LoRA 不可重複選取')
        return value

    @field_validator('title')
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError('草稿名稱不可空白')
        return value.strip()

    @field_validator('engine_url')
    @classmethod
    def draft_url(cls, value):
        return Settings.validate_url(value)

    @field_validator('seed')
    @classmethod
    def seed_valid(cls, value):
        if not value.isascii() or not value.isdigit() or len(value) > 20 or int(value) > 18446744073709551615:
            raise ValueError('Seed 必須是 0 至 18446744073709551615 的整數')
        return str(int(value))


class AssetUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    archived: bool = False
    purpose: Literal['unspecified', 'style', 'character', 'composition'] | None = None
    revision: int | None = Field(default=None, strict=True, ge=0)

    @field_validator('title')
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError('名稱不可空白')
        return value.strip()
