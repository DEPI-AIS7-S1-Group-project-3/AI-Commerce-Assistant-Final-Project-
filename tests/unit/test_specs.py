import pytest
from pydantic import ValidationError

from ai_commerce_marketplace.schemas.specs import validate_specs

MOBILE = dict(
    ram_gb=8,
    storage_gb=128,
    screen_inch=6.5,
    battery_mah=5000,
    camera_mp=50,
    os="android",
    network="5g",
)
LAPTOP = dict(
    ram_gb=16,
    storage_gb=512,
    storage_type="ssd",
    cpu="Core i5-12th",
    screen_inch=15.6,
    weight_kg=1.8,
    os="windows",
)
AUDIO = dict(type="earbuds", wireless=True)


# ───────────── القبول ─────────────
@pytest.mark.parametrize(
    "kind, data",
    [("mobile", MOBILE), ("laptop", LAPTOP), ("audio", AUDIO)],
)
def test_valid_specs_are_accepted(kind, data):
    assert validate_specs(kind, data) == data


def test_optional_fields_are_accepted():
    out = validate_specs("mobile", {**MOBILE, "color_ar": "أسود"})
    assert out["color_ar"] == "أسود"
    out = validate_specs(
        "audio", {**AUDIO, "battery_hours": 20, "noise_cancelling": True, "connector": "bluetooth"}
    )
    assert out["battery_hours"] == 20


def test_none_values_are_dropped():
    assert "gpu" not in validate_specs("laptop", {**LAPTOP, "gpu": None})


# ───────────── الرفض ─────────────
@pytest.mark.parametrize(
    "kind, base, change",
    [
        ("mobile", MOBILE, {"ram_gb": 2}),
        ("mobile", MOBILE, {"ram_gb": 25}),
        ("mobile", MOBILE, {"storage_gb": 16}),
        ("mobile", MOBILE, {"screen_inch": 9.0}),
        ("mobile", MOBILE, {"battery_mah": 1000}),
        ("mobile", MOBILE, {"os": "windows"}),
        ("mobile", MOBILE, {"network": "6g"}),
        ("mobile", MOBILE, {"ram_gb": "8"}),  # نص بدل رقم
        ("laptop", LAPTOP, {"ram_gb": 2}),
        ("laptop", LAPTOP, {"weight_kg": 5.0}),
        ("laptop", LAPTOP, {"storage_type": "nvme"}),
        ("laptop", LAPTOP, {"cpu": ""}),
        ("laptop", LAPTOP, {"battery_hours": 40}),
        ("audio", AUDIO, {"type": "microphone"}),
        ("audio", AUDIO, {"connector": "hdmi"}),
        ("audio", AUDIO, {"wireless": "yes"}),  # لازم bool حقيقي
        ("audio", AUDIO, {"wireless": False, "battery_hours": 10}),
    ],
)
def test_invalid_values_are_rejected(kind, base, change):
    with pytest.raises(ValidationError):
        validate_specs(kind, {**base, **change})


@pytest.mark.parametrize(
    "kind, base, missing",
    [
        ("mobile", MOBILE, "ram_gb"),
        ("mobile", MOBILE, "os"),
        ("laptop", LAPTOP, "cpu"),
        ("audio", AUDIO, "wireless"),
    ],
)
def test_missing_required_field_is_rejected(kind, base, missing):
    data = {k: v for k, v in base.items() if k != missing}
    with pytest.raises(ValidationError):
        validate_specs(kind, data)


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        validate_specs("mobile", {**MOBILE, "turbo_mode": True})


def test_unknown_kind_is_rejected():
    with pytest.raises(ValueError):
        validate_specs("tablet", MOBILE)
