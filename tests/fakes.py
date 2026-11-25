"""Test doubles shared by the agent and router tests."""

from ai_commerce_marketplace.llm import LLMResponse, ToolCall, Usage


class FakeLLM:
    """Returns the scripted responses one by one and records what it was sent."""

    name = "fake"

    def __init__(self, *responses):
        self.responses, self.sent = list(responses), []

    def chat(self, messages, tools=(), *, temperature=0.2, max_tokens=1024):
        self.sent.append((list(messages), list(tools)))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def say(text, **kw):
    return LLMResponse(text, (), "stop", Usage(10, 5), kw.pop("provider", "gemini"), "m", **kw)


def call(name, args, id="c1"):
    c = ToolCall(id, name, args)
    return LLMResponse("", (c,), "tool_calls", Usage(10, 2), "gemini", "m")
