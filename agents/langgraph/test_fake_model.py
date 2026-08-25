"""Tests for the canned offline model.

Run from this directory with:

    uv run --with pytest pytest test_fake_model.py

pytest is an ephemeral dependency on purpose. It is not in pyproject.toml and
not in uv.lock, so nothing here forces a lock regeneration.

No Catalyst, no Dapr, no network and no API key: these assertions all sit at the
model boundary. That is forced rather than chosen. main.py calls
runner.serve(...) at module level with no __main__ guard, so importing it would
start a Dapr-connected server and block forever. The compiled graph is covered
by the live run in the spec's verification section instead.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import Runnable

from fake_model import CannedToolCallingModel

# The two canned turns below mirror what build_model() constructs in main.py.
# They are duplicated here deliberately: main.py is not import-safe (see the
# module docstring), so the test file cannot reuse the original.
FIRST_TURN = AIMessage(
    content="",
    tool_calls=[
        {
            "name": "check_availability",
            "args": {"venue": "Grand Ballroom", "date": "March 15th"},
            "id": "call_availability_1",
            "type": "tool_call",
        }
    ],
)
FINAL_TURN = AIMessage(
    content=(
        "Yes, the Grand Ballroom is available on March 15th. "
        "Open slots are 9AM-1PM, 2PM-6PM, and 6PM-11PM."
    )
)

# What main.py's check_availability tool returns for these arguments. Also
# duplicated because main.py cannot be imported.
TOOL_RESULT = (
    "Grand Ballroom is available on March 15th. "
    "Time slots: 9AM-1PM, 2PM-6PM, 6PM-11PM."
)

TIME_SLOTS = ["9AM-1PM", "2PM-6PM", "6PM-11PM"]


def build_canned_model() -> CannedToolCallingModel:
    """A fresh model, wired the way main.py's build_model() wires it."""
    return CannedToolCallingModel(
        first_turn=FIRST_TURN.model_copy(deep=True),
        final_turn=FINAL_TURN.model_copy(deep=True),
    )


@pytest.fixture
def model() -> CannedToolCallingModel:
    """A new instance per test, since this fixture is function scoped."""
    return build_canned_model()


def a_tool_message() -> ToolMessage:
    return ToolMessage(content=TOOL_RESULT, tool_call_id="call_availability_1")


def test_first_turn_requests_the_tool(model):
    reply = model.invoke([HumanMessage(content="Is the Grand Ballroom free?")])

    assert len(reply.tool_calls) == 1, "the first turn must ask for exactly one tool"
    call = reply.tool_calls[0]
    assert call["name"] == "check_availability"
    assert call["args"] == {"venue": "Grand Ballroom", "date": "March 15th"}


def test_answer_after_tool_result(model):
    messages = [
        HumanMessage(content="Is the Grand Ballroom free?"),
        FIRST_TURN.model_copy(deep=True),
        a_tool_message(),
    ]

    reply = model.invoke(messages)

    # An empty tool_calls is precisely what main.py's should_use_tools branches
    # on: it routes to "tools" when the last message has a non-empty tool_calls
    # and to "__end__" otherwise. So this assertion pins the routing condition
    # at the model boundary, without importing main.py.
    assert reply.tool_calls == [], "a reply after the tool ran must not ask again"
    assert reply.content, "the final turn must carry an answer"


def test_two_turn_conversation_terminates(model):
    # Drive the model by hand through the loop the graph runs: agent, tools,
    # agent. The graph appends each reply and each tool result to one list.
    messages = [HumanMessage(content="Is the Grand Ballroom free on March 15th?")]

    first_reply = model.invoke(messages)
    assert first_reply.tool_calls, "turn one must call the tool"

    messages = messages + [first_reply, a_tool_message()]
    second_reply = model.invoke(messages)

    assert second_reply.tool_calls == [], "turn two must end the loop"
    for slot in TIME_SLOTS:
        assert slot in second_reply.content, f"the answer must report the slot {slot}"


def test_repeat_requests(model):
    # Three sequential requests against ONE instance, which is what
    # runner.serve() holds for the life of the process. A model that counted
    # calls would stop asking for the tool, or would ask on the wrong turn.
    for attempt in range(3):
        reply = model.invoke([HumanMessage(content="Is the Grand Ballroom free?")])
        assert len(reply.tool_calls) == 1, (
            f"request {attempt + 1} on the same instance did not call the tool"
        )
        assert reply.tool_calls[0]["name"] == "check_availability"


def test_resumed_conversation_does_not_recall_the_tool():
    # A workflow replay hands a brand-new process a history in which the tool
    # already ran. Answering from that result is the correct behaviour; asking
    # for the tool a second time is not.
    fresh = build_canned_model()

    reply = fresh.invoke(
        [
            HumanMessage(content="Is the Grand Ballroom free?"),
            FIRST_TURN.model_copy(deep=True),
            a_tool_message(),
        ]
    )

    assert reply.tool_calls == [], "a replayed history must not re-call the tool"
    assert "Grand Ballroom" in reply.content


def test_returned_messages_are_not_the_stored_fields(model):
    # _generate returns turn.model_copy(deep=True). Without that copy,
    # BaseChatModel stamps an id onto the stored field itself, so every call for
    # the life of the process hands back the same id and add_messages replaces
    # rather than appends.
    first = model.invoke([HumanMessage(content="Is the Grand Ballroom free?")])
    second = model.invoke([HumanMessage(content="Is the Grand Ballroom free?")])

    assert first.id is not None, "BaseChatModel is expected to stamp an id"
    assert first.id != second.id, "two invocations returned the same message id"
    assert model.first_turn.id is None, "the stored first_turn was mutated in place"


def test_bind_tools_returns_a_runnable(model):
    # BaseChatModel.bind_tools raises NotImplementedError, so the override is
    # load-bearing: main.py calls build_model().bind_tools(tools) at import.
    bound = model.bind_tools([])

    assert isinstance(bound, Runnable)
    assert bound is model, "binding tools must not swap the canned model out"
