"""A deterministic stand-in for a hosted chat model.

This quickstart's point is inbound identity, not model quality, so it ships a
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

    The decision reads the conversation rather than counting calls. A call
    counter resets with the process and would ask for the tool a second time;
    the replayed message history is the only state that always tells the truth.

    Both the class name and `model_name` are a convention the Catalyst console's
    agent registry relies on: it finds a node's model by scanning globals for a
    type whose name contains "chat" and which exposes `model_name` or `model`.
    That registry is populated by the Diagrid agent runner, which this sample
    deliberately does not use, so neither name is load-bearing here. They are
    kept so the two LangGraph quickstarts read as one family.
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

    Note the subject the first turn asks for: `someone@example.com`, which is
    nobody. A model does not know who is calling and must not be trusted to
    decide -- main.py's `call_tools` replaces this argument with the subject the
    middleware verified. A real provider behaves the same way, which is the
    point of substituting rather than validating.
    """
    return CannedToolCallingChatModel(
        first_turn=AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "my_bookings",
                    "args": {"subject": "someone@example.com"},
                    "id": "call_my_bookings_1",
                    "type": "tool_call",
                }
            ],
        ),
        final_turn=AIMessage(
            content=(
                "You have two bookings: the Grand Ballroom on March 15th "
                "(9AM-1PM) and the Rooftop Terrace on March 22nd (6PM-11PM)."
            )
        ),
    )
