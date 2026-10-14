"""Scripted chat model so agent graphs can be tested offline and deterministically."""

import re
from collections.abc import Callable
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import ConfigDict

ADDR = re.compile(r"\b(bc1[a-z0-9]{20,}|[13][a-km-zA-HJ-NP-Z1-9]{25,39})\b")


def text_of(m) -> str:
    if isinstance(m, tuple):
        return str(m[1])
    return m.content if isinstance(m.content, str) else str(m.content)


class ScriptedChatModel(BaseChatModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    responder: Callable[[list[BaseMessage]], AIMessage]
    structured: Callable[[type, list], Any]

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self.responder(messages))])

    def bind_tools(self, tools, **kwargs):
        return self

    def with_structured_output(self, schema, **kwargs):
        return RunnableLambda(lambda msgs: self.structured(schema, msgs))


def tool_call(name: str, args: dict, call_id: str = "c1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def specialist_responder(messages: list[BaseMessage]) -> AIMessage:
    system = text_of(messages[0]) if messages else ""
    if any(isinstance(m, ToolMessage) for m in messages):
        return AIMessage(content="findings recorded")
    task = " ".join(text_of(m) for m in messages[1:])
    addr = (ADDR.search(task) or [None])[0] if ADDR.search(task) else None
    if "on-chain analyst" in system and addr:
        return tool_call("assess_wallet", {"address": addr})
    if "sanctions/intel" in system and addr:
        return tool_call("lookup_sanctions", {"address": addr})
    if "research analyst" in system:
        return tool_call("search_typologies", {"query": "how are peeling chains used"})
    return AIMessage(content="nothing to do")
