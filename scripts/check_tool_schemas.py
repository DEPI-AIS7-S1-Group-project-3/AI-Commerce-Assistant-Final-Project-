"""Show, for each agent, the tool parameters that give the LLM too little information.

    uv run python -m scripts.check_tool_schemas            # report only
    uv run python -m scripts.check_tool_schemas --strict   # exit 1 if anything is weak

A weak parameter has no useful type hint (``Any``) or no description in the docstring.
"""

import sys

from ai_commerce_marketplace.agents.order_actions.tools import REGISTRY as ORDER_ACTIONS
from ai_commerce_marketplace.agents.seller.tools import REGISTRY as SELLER
from ai_commerce_marketplace.agents.shopping.tools import REGISTRY as SHOPPING
from ai_commerce_marketplace.agents.support.tools import REGISTRY as SUPPORT
from ai_commerce_marketplace.agents.tool_specs import tool_specs, weak_params

AGENTS = {
    "shopping": SHOPPING,
    "support": SUPPORT,
    "order_actions": ORDER_ACTIONS,
    "seller": SELLER,
}


def main(strict: bool = False) -> int:
    total = 0
    for agent, registry in AGENTS.items():
        weak = weak_params(registry)
        total += len(weak)
        n_params = sum(len(s.parameters["properties"]) for s in tool_specs(registry))
        print(f"\n{agent}: {len(registry)} tools, {n_params} parameters, {len(weak)} weak")
        for tool, param, why in weak:
            print(f"  {tool}.{param}: {why}")
    print(f"\n{total} weak parameter(s) in total")
    return 1 if strict and total else 0


if __name__ == "__main__":
    sys.exit(main("--strict" in sys.argv))
