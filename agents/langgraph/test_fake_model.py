"""Tests for the canned offline model.

Run from this directory with:

    uv run --with pytest pytest test_fake_model.py

pytest is an ephemeral dependency on purpose. It is not in pyproject.toml and
not in uv.lock, so nothing here forces a lock regeneration.

No Catalyst, no Dapr, no network and no API key: these assertions all sit at the
model boundary. Nothing here is a copy of production data. The canned turns come
from fake_model.build_canned_model(), which is what main.py's build_model()
returns, and the tool comes from tools.py, which is what main.py wires into the
graph, so a change to either fails these tests rather than sliding past them.

main.py itself is deliberately NOT imported: its module-level
DaprWorkflowGraphRunner health-checks the Dapr sidecar and retries for about two
minutes when there is not one. That is why the tool lives in its own module. The
compiled graph is covered by the live run in the spec's verification section.
"""

import pytest
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import Runnable

from fake_model import CannedToolCallingChatModel, build_canned_model
from tools import check_availability, tools_by_name

TIME_SLOTS = ["9AM-1PM", "2PM-6PM", "6PM-11PM"]


@pytest.fixture
def model() -> CannedToolCallingChatModel:
    """A new instance per test, since this fixture is function scoped."""
    return build_canned_model()


def a_tool_message(model: CannedToolCallingChatModel) -> ToolMessage:
    """The real tool's output, invoked with the arguments the canned first turn asks for.

    Only its type matters to the model under test, which branches on
    isinstance(m, ToolMessage). Building it from the real tool anyway means a tool
    whose signature drifts away from the canned tool_call fails here.
    """
    call = model.first_turn.tool_calls[0]
    return ToolMessage(content=check_availability.invoke(call["args"]), tool_call_id=call["id"])


def test_first_turn_requests_the_tool(model):
    reply = model.invoke([HumanMessage(content="Is the Grand Ballroom free?")])

    assert len(reply.tool_calls) == 1, "the first turn must ask for exactly one tool"
    call = reply.tool_calls[0]
    # The tool name must be one main.py can actually dispatch: call_tools looks the
    # reply's tool_calls up in tools_by_name and a miss is a KeyError at runtime.
    assert call["name"] in tools_by_name, (
        f"the canned model asks for {call['name']}, which the graph cannot dispatch"
    )
    assert set(call["args"]) == {"venue", "date"}, (
        "the canned call must supply exactly the arguments check_availability takes"
    )


def test_answer_after_tool_result(model):
    messages = [
        HumanMessage(content="Is the Grand Ballroom free?"),
        model.first_turn.model_copy(deep=True),
        a_tool_message(model),
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

    messages = messages + [first_reply, a_tool_message(model)]
    second_reply = model.invoke(messages)

    assert second_reply.tool_calls == [], "turn two must end the loop"
    # The canned answer under test comes from fake_model, and the slots come from the
    # real tool, so this fails if the two ever describe different availability.
    tool_output = check_availability.invoke(model.first_turn.tool_calls[0]["args"])
    for slot in TIME_SLOTS:
        assert slot in tool_output, f"the tool must offer the slot {slot}"
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
            fresh.first_turn.model_copy(deep=True),
            a_tool_message(fresh),
        ]
    )

    assert reply.tool_calls == [], "a replayed history must not re-call the tool"
    assert "Grand Ballroom" in reply.content


def test_a_new_question_after_the_tool_still_answers(model):
    # The turn choice reads the history for ANY ToolMessage, so a follow-up question
    # asked after the tool ran keeps getting the final turn. That is the documented
    # behaviour of a two-turn canned model, and this pins it so a future change to
    # _generate's condition cannot alter it silently.
    reply = model.invoke(
        [
            HumanMessage(content="Is the Grand Ballroom free?"),
            model.first_turn.model_copy(deep=True),
            a_tool_message(model),
            HumanMessage(content="And what about the week after?"),
        ]
    )

    assert reply.tool_calls == [], "the tool has already run, so it must not be called again"
    assert reply.content == model.final_turn.content


def test_llm_type_is_stable(model):
    # _llm_type ends up in LangChain's callback and tracing payloads, so it is part of
    # this model's observable surface rather than an internal detail.
    assert model._llm_type == "canned-tool-calling"


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


def test_bind_tools_returns_the_same_model(model):
    # BaseChatModel.bind_tools raises NotImplementedError, so the override is
    # load-bearing: main.py calls build_model().bind_tools(tools) at import.
    # `is model` implies Runnable, so asserting the identity is the stronger check.
    bound = model.bind_tools([check_availability])

    assert bound is model, "binding tools must not swap the canned model out"
    assert isinstance(bound, Runnable)


def test_console_can_read_the_model_name(model):
    # The Catalyst agent registry finds the model by scanning the graph node's
    # globals for a type whose name contains "chat" and which exposes
    # model_name or model. Both halves are load-bearing: drop either and the
    # console reports this agent's model as "unknown" on the page the README
    # sends the reader to.
    assert "chat" in type(model).__name__.lower(), "the class name must contain 'chat'"
    assert model.model_name == "canned-offline"
