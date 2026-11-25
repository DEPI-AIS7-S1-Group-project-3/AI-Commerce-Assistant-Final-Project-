"""The four agents as ``AgentSpec`` objects, in one place for the router."""

from ai_commerce_marketplace.agents import runner
from ai_commerce_marketplace.agents.order_actions import prompts as order_actions_prompts
from ai_commerce_marketplace.agents.order_actions import tools as order_actions_tools
from ai_commerce_marketplace.agents.seller import prompts as seller_prompts
from ai_commerce_marketplace.agents.seller import tools as seller_tools
from ai_commerce_marketplace.agents.shopping import prompts as shopping_prompts
from ai_commerce_marketplace.agents.shopping import tools as shopping_tools
from ai_commerce_marketplace.agents.support import prompts as support_prompts
from ai_commerce_marketplace.agents.support import tools as support_tools

AGENTS: dict[str, runner.AgentSpec] = {
    "shopping": runner.AgentSpec(
        "shopping",
        shopping_tools.REGISTRY,
        shopping_tools.call_tool,
        shopping_prompts.build_system_prompt,
    ),
    "support": runner.AgentSpec(
        "support",
        support_tools.REGISTRY,
        support_tools.call_tool,
        support_prompts.build_system_prompt,
    ),
    "order_actions": runner.AgentSpec(
        "order_actions",
        order_actions_tools.REGISTRY,
        order_actions_tools.call_tool,
        order_actions_prompts.build_system_prompt,
    ),
    "seller": runner.AgentSpec(
        "seller",
        seller_tools.REGISTRY,
        seller_tools.call_tool,
        seller_prompts.build_system_prompt,
    ),
}
