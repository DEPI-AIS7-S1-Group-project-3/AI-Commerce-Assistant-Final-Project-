"""Turn an agent's ``REGISTRY`` into the JSON-schema tool list the LLM needs.

The schema is read from the tool function itself, so it cannot drift from the code:

- the parameter type comes from the type hint (``int``, ``str``, ``bool``, ``float``,
  ``Literal[...]``, ``list[int]``, ``X | None``);
- a parameter is required when it has no default value;
- its description comes from the ``Args:`` section of the docstring;
- the tool description comes from ``REGISTRY[name]["description"]``.

A registry entry may instead carry a complete ``"schema"`` (a JSON-schema object written by hand,
as the Seller agent does); it is used as written and checked against ``params``.

A parameter typed ``Any`` (or not typed) gives the model no information, so it is reported as
weak. When a tool validates its input by hand and has to keep ``Any`` in its signature, the
registry entry can carry ``"param_schema": {"name": {...}}`` to give the model the real type.
"""

import inspect
import re
import types
from collections.abc import Callable
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints

from ai_commerce_marketplace.agents.common import ToolRegistry
from ai_commerce_marketplace.llm.types import ToolSpec

_SCALARS: dict[Any, str] = {bool: "boolean", int: "integer", float: "number", str: "string"}
_ARGS_LINE = re.compile(r"^\s{2,}(\w+)\s*(?:\([^)]*\))?:\s*(.+)$")


def _schema(annotation: Any) -> dict[str, Any] | None:
    """JSON schema for a type hint, or None when the hint says nothing useful."""
    if annotation is Any or annotation is inspect.Parameter.empty:
        return None
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        options = [a for a in get_args(annotation) if a is not type(None)]
        schemas = [_schema(a) for a in options]
        if any(s is None for s in schemas):
            return None
        return schemas[0] if len(schemas) == 1 else {"anyOf": schemas}  # type: ignore[return-value]
    if origin is Literal:
        values = list(get_args(annotation))
        kinds = {_SCALARS.get(type(v)) for v in values}
        out: dict[str, Any] = {"enum": values}
        if len(kinds) == 1 and None not in kinds:
            out["type"] = kinds.pop()
        return out
    if annotation in _SCALARS:
        return {"type": _SCALARS[annotation]}
    if origin in (list, tuple, set, frozenset) or annotation in (list, tuple):
        args = get_args(annotation)
        items = _schema(args[0]) if args else None
        return {"type": "array", **({"items": items} if items else {})}
    if origin is dict or annotation is dict:
        return {"type": "object"}
    return None


def _is_optional(annotation: Any) -> bool:
    return get_origin(annotation) in (Union, types.UnionType) and type(None) in get_args(annotation)


def _arg_docs(fn: Callable[..., Any]) -> dict[str, str]:
    """Google-style ``Args:`` section of the docstring: ``name: description``."""
    docs: dict[str, str] = {}
    in_args = False
    for line in (inspect.getdoc(fn) or "").splitlines():
        if line.strip() == "Args:":
            in_args = True
            continue
        if in_args:
            if line.strip() and not line.startswith((" ", "\t")):
                break
            m = _ARGS_LINE.match(line)
            if m:
                docs[m.group(1)] = m.group(2).strip()
    return docs


def _explicit(name: str, entry: Any) -> tuple[ToolSpec, list[tuple[str, str]]]:
    """A registry entry that carries its own JSON schema (``"schema"``) is used as written.

    It must describe exactly the parameters listed in ``params``, so the two cannot drift apart.
    """
    schema = entry["schema"]
    properties = schema.get("properties", {})
    if set(properties) != set(entry["params"]):
        raise ValueError(
            f"{name}: schema properties {sorted(properties)} differ from params "
            f"{sorted(entry['params'])}"
        )
    if not set(schema.get("required", [])) <= set(properties):
        raise ValueError(f"{name}: schema requires a parameter it does not define")
    weak = [
        (p, "schema gives no type, enum or anyOf")
        for p, prop in properties.items()
        if not {"type", "enum", "anyOf"} & set(prop)
    ]
    return ToolSpec(name, entry["description"], dict(schema)), weak


def _tool(name: str, entry: Any) -> tuple[ToolSpec, list[tuple[str, str]]]:
    if "schema" in entry:
        return _explicit(name, entry)
    fn = entry["fn"]
    sig = inspect.signature(fn)
    hints = get_type_hints(fn)
    docs = _arg_docs(fn)
    overrides = entry.get("param_schema", {})
    properties: dict[str, Any] = {}
    required: list[str] = []
    weak: list[tuple[str, str]] = []
    for pname in entry["params"]:
        if pname not in sig.parameters:
            raise ValueError(f"{name}: '{pname}' is in params but not in the function signature")
        param = sig.parameters[pname]
        annotation = hints.get(pname, inspect.Parameter.empty)
        schema = overrides.get(pname) or _schema(annotation)
        if schema is None:
            schema = {}
            weak.append((pname, "no useful type hint (Any or missing); use a real type or Literal"))
        prop = dict(schema)
        if pname in docs:
            prop["description"] = docs[pname]
        else:
            weak.append((pname, "no description in the docstring Args: section"))
        properties[pname] = prop
        if param.default is inspect.Parameter.empty and not _is_optional(annotation):
            required.append(pname)
    parameters = {"type": "object", "properties": properties, "required": required}
    return ToolSpec(name, entry["description"], parameters), weak


def tool_specs(registry: ToolRegistry) -> list[ToolSpec]:
    """The tools of one agent, in the neutral format the ``llm`` package sends to any model."""
    return [_tool(name, entry)[0] for name, entry in registry.items()]


def weak_params(registry: ToolRegistry) -> list[tuple[str, str, str]]:
    """``(tool, parameter, problem)`` for every parameter that tells the model too little."""
    return [(name, p, why) for name, entry in registry.items() for p, why in _tool(name, entry)[1]]
