"""A deterministic stand-in for a hosted chat model.

The quickstart's point is durable execution, not model quality, so it ships a
canned two-turn conversation: ask for the tool, then answer from the tool's
result. That keeps the demo free, offline and identical on every run.

Set OPENAI_API_KEY and DIAGRID_QUICKSTART_MODEL=openai to use a real provider.
"""

from typing import Any, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable


class CannedToolCallingChatModel(BaseChatModel):
    """Returns `first_turn` until a tool has run, then `final_turn`.

    The decision reads the conversation rather than counting calls. That matters
    here: each graph node is a Dapr workflow activity, so after a restart the
    replayed history is the only reliable state. A call counter resets with the
    process and would ask for the tool a second time.

    Both the class name and `model_name` are load-bearing for the Catalyst
    console. The agent registry finds the model by scanning the node's globals
    for a type whose name contains "chat" and which exposes `model_name` or
    `model`, so without either the console reports this agent's model as
    "unknown".
    """

    first_turn: AIMessage
    final_turn: AIMessage
    model_name: str = "canned-offline"

    @property
    def _llm_type(self) -> str:
        return "canned-tool-calling"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Runnable:
        # Accepted and ignored: the tool call below is already decided, so there
        # is no schema for this model to read. Overriding is not optional:
        # BaseChatModel.bind_tools raises NotImplementedError.
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        tool_has_run = any(isinstance(m, ToolMessage) for m in messages)
        turn = self.final_turn if tool_has_run else self.first_turn
        # Copy, never hand out the field itself: BaseChatModel stamps an `id` on
        # the message it returns, mutating it in place.
        return ChatResult(generations=[ChatGeneration(message=turn.model_copy(deep=True))])


def build_canned_model() -> CannedToolCallingChatModel:
    """The canned two-turn conversation this quickstart runs on.

    It lives here rather than in main.py so that the tests can assert against the
    real thing instead of a copy of it. main.py's build_model() returns this.
    """
    return CannedToolCallingChatModel(
        first_turn=AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "check_availability",
                    "args": {"venue": "Grand Ballroom", "date": "March 15th"},
                    "id": "call_availability_1",
                    "type": "tool_call",
                }
            ],
        ),
        final_turn=AIMessage(
            content=(
                "Yes, the Grand Ballroom is available on March 15th. "
                "Open slots are 9AM-1PM, 2PM-6PM, and 6PM-11PM."
            )
        ),
    )
