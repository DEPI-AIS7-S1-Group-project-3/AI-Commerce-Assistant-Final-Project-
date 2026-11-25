import json
from typing import Any, Literal

import pytest

from ai_commerce_marketplace.agents.order_actions.tools import REGISTRY as ORDER_ACTIONS
from ai_commerce_marketplace.agents.seller.tools import REGISTRY as SELLER
from ai_commerce_marketplace.agents.shopping.tools import REGISTRY as SHOPPING
from ai_commerce_marketplace.agents.support.tools import REGISTRY as SUPPORT
from ai_commerce_marketplace.agents.tool_specs import tool_specs, weak_params
from ai_commerce_marketplace.llm import ToolSpec


def sample(
    ctx,
    order_id: int,
    note: str | None = None,
    sort: Literal["newest", "price_asc"] = "newest",
    ids: list[int] | None = None,
    flag: bool = False,
    amount: float = 1.0,
    status: Literal["a", "b"] | None = None,
    anything: Any = None,
):
    """Sample tool.

    Args:
        order_id: The order number, e.g. 10002.
        note: Free text.
        sort: Sort order.
        ids: Product ids.
        flag: A switch.
        amount: A number.
        status: One status.
    """


def entry(fn, params, **extra):
    return {"t": {"fn": fn, "description": "Sample tool", "params": params, **extra}}


ALL = list("order_id note sort ids flag amount status anything".split())


def props(**extra):
    (spec,) = tool_specs(entry(sample, ALL, **extra))
    return spec


def test_types_come_from_the_hints():
    p = props().parameters["properties"]
    assert p["order_id"]["type"] == "integer"
    assert p["note"]["type"] == "string"
    assert p["flag"]["type"] == "boolean"
    assert p["amount"]["type"] == "number"
    assert p["ids"] == {
        "type": "array",
        "items": {"type": "integer"},
        "description": "Product ids.",
    }
    assert p["sort"]["enum"] == ["newest", "price_asc"] and p["sort"]["type"] == "string"
    assert p["status"]["enum"] == ["a", "b"]  # Literal | None keeps the enum


def test_required_means_no_default():
    assert props().parameters["required"] == ["order_id"]


def test_descriptions_come_from_the_docstring_and_the_registry():
    spec = props()
    assert spec.description == "Sample tool"
    assert (
        spec.parameters["properties"]["order_id"]["description"] == "The order number, e.g. 10002."
    )


def test_only_listed_params_are_exposed():
    spec = props()
    assert "ctx" not in spec.parameters["properties"]
    (narrow,) = tool_specs(entry(sample, ["order_id"]))
    assert list(narrow.parameters["properties"]) == ["order_id"]


def test_param_not_in_the_signature_is_an_error():
    with pytest.raises(ValueError, match="not in the function signature"):
        tool_specs(entry(sample, ["customer_id"]))


def test_any_is_weak_and_an_override_fixes_it():
    weak = {(p, why.split(" ")[0]) for _, p, why in weak_params(entry(sample, ALL))}
    assert ("anything", "no") in weak
    fixed = entry(sample, ALL, param_schema={"anything": {"type": "string"}})
    assert not [w for w in weak_params(fixed) if w[1] == "anything" and "type hint" in w[2]]
    assert (
        props(param_schema={"anything": {"type": "string"}}).parameters["properties"]["anything"][
            "type"
        ]
        == "string"
    )


def test_missing_description_is_weak():
    def bare(ctx, order_id: int):
        """No args section."""

    assert weak_params(entry(bare, ["order_id"])) == [
        ("t", "order_id", "no description in the docstring Args: section")
    ]


@pytest.mark.parametrize(
    "registry",
    [SHOPPING, SUPPORT, ORDER_ACTIONS, SELLER],
    ids=["shopping", "support", "order_actions", "seller"],
)
def test_every_real_registry_builds_valid_json_schemas(registry):
    specs = tool_specs(registry)
    assert [s.name for s in specs] == list(registry)
    for s in specs:
        assert isinstance(s, ToolSpec) and s.description
        props_, required = s.parameters["properties"], s.parameters["required"]
        assert set(required) <= set(props_)
        assert not {"customer_id", "seller_id", "user_id", "ctx", "session"} & set(props_)
        json.dumps(s.parameters)


def test_support_tools_are_fully_described():
    # Support is the reference: no weak parameter. Other agents are listed by
    # `python -m scripts.check_tool_schemas` until their owners fix them.
    assert weak_params(SUPPORT) == []
    policy_get = next(s for s in tool_specs(SUPPORT) if s.name == "policy_get")
    assert policy_get.parameters["properties"]["slug"]["enum"] == [
        "shipping",
        "returns",
        "warranty",
        "cancellation",
    ]
    assert policy_get.parameters["required"] == ["slug"]


# ---- explicit "schema" (used by the Seller agent) ----
def plain(ctx, a: int, b: str = "x"):
    """No docstring args."""


EXPLICIT = {
    "type": "object",
    "properties": {
        "a": {"type": "integer", "minimum": 1, "maximum": 20},
        "b": {"type": "string"},
    },
    "required": ["a"],
    "additionalProperties": False,
}


def test_explicit_schema_is_used_as_written():
    (spec,) = tool_specs(entry(plain, ["a", "b"], schema=EXPLICIT))
    assert spec.parameters == EXPLICIT
    assert weak_params(entry(plain, ["a", "b"], schema=EXPLICIT)) == []


def test_explicit_schema_must_match_params():
    with pytest.raises(ValueError, match="differ from params"):
        tool_specs(entry(plain, ["a"], schema=EXPLICIT))
    bad = {**EXPLICIT, "required": ["zzz"]}
    with pytest.raises(ValueError, match="requires a parameter"):
        tool_specs(entry(plain, ["a", "b"], schema=bad))


def test_explicit_schema_without_a_type_is_weak():
    schema = {"type": "object", "properties": {"a": {"description": "?"}}, "required": []}
    assert weak_params(entry(plain, ["a"], schema=schema)) == [
        ("t", "a", "schema gives no type, enum or anyOf")
    ]


def test_seller_is_fully_described_by_its_own_schemas():
    assert weak_params(SELLER) == []
