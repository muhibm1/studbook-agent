"""The graph: tool budget, citation checks, refusals. Scripted model, no network."""

from conftest import ScriptedModel, call
from langchain_core.messages import AIMessage

from studbook_agent.graph import REFUSAL_PREFIX, Answer, ask, build_graph

DECISION = "workhorse:docs/adr/0001-control-state.md#1"


def test_answer_cites_what_was_read(index):
    """Search, read, answer: the citation resolves to the file and heading."""
    model = ScriptedModel(
        [
            call("search_records", {"query": "control state worktrees"}),
            call("read_section", {"section_id": DECISION}, "c2"),
            AIMessage("I have what I need."),
        ],
        [
            Answer(
                answer="It moved to the git common directory.", citations=[DECISION], refused=False
            )
        ],
    )
    result = ask("Where does control state live?", model=model, index=index)
    assert result["refused"] is False
    assert result["citations"][0]["path"] == "docs/adr/0001-control-state.md"
    assert result["tool_rounds"] == 2


def test_invented_citation_is_retried_then_refused(index):
    """Citing an id no tool showed is sent back once, then the answer is refused."""
    model = ScriptedModel(
        [AIMessage("done")],
        [
            Answer(answer="x", citations=[DECISION], refused=False),
            Answer(answer="x", citations=[DECISION], refused=False),
        ],
    )
    result = ask("Where does control state live?", model=model, index=index)
    assert result["refused"] is True
    assert result["answer"].startswith(REFUSAL_PREFIX)
    retry_prompt = model.prompts[-1][-1].content
    assert "never shown to you" in retry_prompt


def test_retry_can_recover(index):
    """An answer without citations is sent back; a cited second attempt is accepted."""
    model = ScriptedModel(
        [call("search_records", {"query": "control state"}), AIMessage("done")],
        [
            Answer(answer="It moved.", citations=[], refused=False),
            Answer(answer="It moved.", citations=[DECISION], refused=False),
        ],
    )
    assert ask("q", model=model, index=index)["refused"] is False


def test_refusal_gets_the_prefix(index):
    """A refusal reads 'Not in the record' however the model phrased it."""
    model = ScriptedModel(
        [AIMessage("nothing")], [Answer(answer="No such record.", citations=[], refused=True)]
    )
    result = ask("What database stores invoices?", model=model, index=index)
    assert result["answer"] == f"{REFUSAL_PREFIX}: No such record."


def test_budget_stops_research(index):
    """A model that never stops asking for tools is cut off at the budget."""
    model = ScriptedModel(
        [call("search_records", {"query": f"q{n}"}, f"c{n}") for n in range(10)],
        [Answer(answer="none", citations=[], refused=True)],
    )
    graph = build_graph(model, index, max_rounds=3)
    state = graph.invoke({"question": "loop"})
    assert state["rounds"] == 3
    assert state["refused"] is True


def test_unknown_section_and_tool_are_reported_not_raised(index):
    """A bad id or tool name becomes a message the model can correct."""
    model = ScriptedModel(
        [
            AIMessage(
                "",
                tool_calls=[
                    {"name": "read_section", "args": {"section_id": "nope#0"}, "id": "a"},
                    {"name": "delete_everything", "args": {}, "id": "b"},
                ],
            ),
            AIMessage("done"),
        ],
        [Answer(answer="n", citations=[], refused=True)],
    )
    graph = build_graph(model, index)
    state = graph.invoke({"question": "q"})
    outputs = [m.content for m in state["messages"] if m.type == "tool"]
    assert "No section has the id" in outputs[0]
    assert "no tool named" in outputs[1]
