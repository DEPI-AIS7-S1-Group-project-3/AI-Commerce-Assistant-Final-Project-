from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_commerce_marketplace.core.enums import SpecKind


class _Specs(BaseModel):
    # أي حقل مش معرّف هنا بيتم رفضه
    model_config = ConfigDict(extra="forbid", strict=True)


class MobileSpecs(_Specs):
    ram_gb: int = Field(ge=3, le=24)
    storage_gb: int = Field(ge=32, le=1024)
    screen_inch: float = Field(ge=4.5, le=7.5)
    battery_mah: int = Field(ge=2500, le=7000)
    camera_mp: int = Field(gt=0)
    os: Literal["android", "ios"]
    network: Literal["4g", "5g"]
    color_ar: str | None = None


class LaptopSpecs(_Specs):
    ram_gb: int = Field(ge=4, le=64)
    storage_gb: int = Field(ge=128, le=2048)
    storage_type: Literal["ssd", "hdd"]
    cpu: str = Field(min_length=1)
    gpu: str | None = None
    screen_inch: float = Field(ge=11, le=18)
    weight_kg: float = Field(ge=0.8, le=3.5)
    battery_hours: int | None = Field(default=None, ge=3, le=24)
    os: Literal["windows", "macos", "none"]


class AudioSpecs(_Specs):
    type: Literal["earbuds", "headphones", "speaker", "charger", "power_bank", "cable"]
    wireless: bool
    battery_hours: int | None = Field(default=None, ge=1)
    noise_cancelling: bool | None = None
    connector: Literal["usb_c", "lightning", "3.5mm", "bluetooth"] | None = None

    @model_validator(mode="after")
    def battery_only_if_wireless(self):
        if self.battery_hours is not None and not self.wireless:
            raise ValueError("battery_hours is only allowed when wireless is true")
        return self


SPEC_MODELS: dict[SpecKind, type[_Specs]] = {
    SpecKind.MOBILE: MobileSpecs,
    SpecKind.LAPTOP: LaptopSpecs,
    SpecKind.AUDIO: AudioSpecs,
}


def validate_specs(spec_kind: str, data: dict[str, Any]) -> dict[str, Any]:
    """يتحقق من مواصفات منتج حسب فئته، ويرجّع dict جاهز للتخزين في JSONB.

    بيرمي pydantic.ValidationError لو فيه خطأ، و ValueError لو الفئة غير معروفة.
    الحقول الاختيارية الفاضية بتتشال (مش بتتخزن null).
    """
    try:
        model = SPEC_MODELS[SpecKind(spec_kind)]
    except ValueError:
        raise ValueError(f"unknown spec_kind: {spec_kind!r}") from None
    return model.model_validate(data).model_dump(mode="json", exclude_none=True)