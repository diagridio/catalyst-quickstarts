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


class CannedToolCallingModel(BaseChatModel):
    """Returns `first_turn` until a tool has run, then `final_turn`.

    The decision reads the conversation rather than counting calls. That matters
    here: each graph node is a Dapr workflow activity, so after a restart the
    replayed history is the only reliable state. A call counter resets with the
    process and would ask for the tool a second time.
    """

    first_turn: AIMessage
    final_turn: AIMessage

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
