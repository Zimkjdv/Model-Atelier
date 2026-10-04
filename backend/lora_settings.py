"""Single-LoRA draft settings; saved choices are not load verification."""
from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoraSetting(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=2048)
    enabled: bool = Field(default=True, strict=True)
    strength_model: float = Field(default=1.0, ge=-20, le=20, strict=True, allow_inf_nan=False)
    strength_clip: float = Field(default=1.0, ge=-20, le=20, strict=True, allow_inf_nan=False)

    @field_validator('name')
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError('LoRA 名稱不可空白')
        return value
