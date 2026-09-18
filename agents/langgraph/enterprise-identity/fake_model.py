"""A deterministic stand-in for a hosted chat model.

A canned two-turn conversation -- ask for the tool, then answer from the tool's
result -- so the quickstart runs offline and identically on every run. Set
OPENAI_API_KEY and DIAGRID_QUICKSTART_MODEL=openai to use a real provider.
"""

from typing import Any, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable


class CannedToolCallingChatModel(BaseChatModel):
    """Returns `first_turn` until a tool has run, then `final_turn`."""

    first_turn: AIMessage
    final_turn: AIMessage
    model_name: str = "canned-offline"

    @property
    def _llm_type(self) -> str:
        return "canned-tool-calling"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Runnable:
        # Accepted and ignored: the tool call is already decided. Overriding is
        # not optional -- BaseChatModel.bind_tools raises NotImplementedError.
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
        # Return a copy: the returned message is mutated in place.
        return ChatResult(generations=[ChatGeneration(message=turn.model_copy(deep=True))])


def build_canned_model(*, offline: bool = False) -> CannedToolCallingChatModel:
    """The canned two-turn conversation this quickstart runs on.

    The first turn deliberately asks for `someone@example.com`, who is nobody:
    the subject a model asks for is never the subject that is served.
    """
    if offline:
        call = {
            "name": "my_bookings",
            "args": {"subject": "someone@example.com"},
            "id": "call_my_bookings_1",
            "type": "tool_call",
        }
        answer = (
            "You have two bookings: the Grand Ballroom on March 15th "
            "(9AM-1PM) and the Rooftop Terrace on March 22nd (6PM-11PM)."
        )
    else:
        call = {
            "name": "account_summary",
            "args": {"account_id": "ACME-1"},
            "id": "call_account_summary_1",
            "type": "tool_call",
        }
        answer = "Here is what the CRM returned for ACME-1."

    return CannedToolCallingChatModel(
        first_turn=AIMessage(content="", tool_calls=[call]),
        final_turn=AIMessage(content=answer),
    )
