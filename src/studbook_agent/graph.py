"""The agent as a LangGraph graph: research with tools, then answer with checked citations.

    START -> research --(tool calls, budget left)--> tools -> research
                      --(done, or budget spent)----> answer --(valid)--> END
                                                            --(invalid, retries left)--> answer
                                                            --(invalid, none left)--> END (refused)

The model decides what to search and what to read. Code decides everything else:
- **The budget.** At most `MAX_ROUNDS` rounds of tool calls; then the graph moves to the answer
  whatever the model wanted.
- **The citations.** Every id in the answer must be a section the agent was actually shown by a
  tool in this run. An answer that cites anything else, or answers without citing, is sent back
  once with the reason, and then refused rather than shown. A fabricated citation never reaches
  the reader.
"""

import os
import re
from collections.abc import Sequence
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from studbook_agent import prompts
from studbook_agent.index import Index
from studbook_agent.record import load_index

MAX_ROUNDS = 6
ANSWER_ATTEMPTS = 2
SEARCH_RESULTS = 6
SNIPPET_CHARS = 280
READ_CHARS = 6000
REFUSAL_PREFIX = "Not in the record"
DEFAULT_MODEL = "claude-sonnet-5-5"
DEV_MODEL = "claude-haiku-4-5-20251001"


def merge_ids(left: list[str], right: list[str]) -> list[str]:
    """Union of two id lists, in first-seen order."""
    return list(dict.fromkeys([*left, *right]))


class State(TypedDict, total=False):
    """Everything one question's run carries."""

    question: str
    messages: Annotated[list[AnyMessage], add_messages]
    # Section ids a tool returned in this run: the only ids an answer may cite.
    shown: Annotated[list[str], merge_ids]
    rounds: int
    answer_attempts: int
    answer_problem: str | None
    answer: str
    citations: list[str]
    refused: bool


class Answer(BaseModel):
    """The structured answer the model returns."""

    answer: str = Field(description="Two to four plain sentences, or one sentence if refused.")
    citations: list[str] = Field(description="Ids of the sections the answer relies on.")
    refused: bool = Field(description="True when the record does not answer the question.")


def make_tools(index: Index) -> list[Any]:
    """The three tools the model may call, bound to one index."""

    @tool
    def search_records(query: str, repo: str | None = None, doc_type: str | None = None) -> str:
        """Search the record. Returns section ids, where each comes from, and a snippet.

        Args:
            query: words the record would use; names of components, commands, terms.
            repo: optionally, one repository name to search within.
            doc_type: optionally one of decision, spec, plan, retro, readme, changelog,
                research, status, brief, ship, doc.
        """
        hits = index.search(query, k=SEARCH_RESULTS, repo=repo, doc_type=doc_type)
        if not hits:
            return "No sections matched. Try other words, or drop the filters."
        lines = []
        for section, _ in hits:
            snippet = " ".join(section.text.split())[:SNIPPET_CHARS]
            lines.append(
                f"[{section.id}] ({section.doc_type}, {section.date or 'undated'}) "
                f"{section.heading}\n    {snippet}"
            )
        return "\n".join(lines)

    @tool
    def read_section(section_id: str) -> str:
        """Read one section in full, by the id a search returned."""
        section = index.by_id.get(section_id)
        if section is None:
            return f"No section has the id {section_id!r}; use an id exactly as search showed it."
        text = section.text[:READ_CHARS]
        return f"[{section.id}] {section.heading}\n\n{text}"

    @tool
    def list_decisions(repo: str | None = None) -> str:
        """List the decision records (ADRs and decision logs), optionally for one repository."""
        seen: dict[str, str] = {}
        for section in index.sections:
            if section.doc_type == "decision" and (repo is None or section.repo == repo):
                seen.setdefault(f"{section.repo}:{section.path}", section.id)
        if not seen:
            return "No decision records found."
        return "\n".join(
            f"[{first_id}] {index.by_id[first_id].heading.split(' > ')[0]}"
            for first_id in seen.values()
        )

    return [search_records, read_section, list_decisions]


SECTION_ID = re.compile(r"\[([^\]\s]+#\d+)\]")


def ids_in(text: str, index: Index) -> list[str]:
    """Every known section id that appears, in brackets, in a tool's output."""
    return [found for found in SECTION_ID.findall(text) if found in index.by_id]


def build_graph(model: BaseChatModel, index: Index, *, max_rounds: int = MAX_ROUNDS) -> Any:
    """Compile the graph for one model and one index."""
    tools = make_tools(index)
    by_name = {t.name: t for t in tools}
    researcher = model.bind_tools(tools)
    answerer = model.with_structured_output(Answer)
    system = prompts.RESEARCH.format(repos=", ".join(sorted(index.repos())), budget=max_rounds)

    def research(state: State) -> dict[str, Any]:
        """Ask the model what to look up next, or whether it is done."""
        messages = state.get("messages") or [HumanMessage(state["question"])]
        reply = researcher.invoke([SystemMessage(system), *messages])
        update: dict[str, Any] = {"messages": [reply]}
        if not state.get("messages"):
            update["messages"] = [messages[0], reply]
        return update

    def route_research(state: State) -> Literal["tools", "answer"]:
        """Tools while the model asks for them and the budget lasts; otherwise answer."""
        last = state["messages"][-1]
        wants_tools = isinstance(last, AIMessage) and bool(last.tool_calls)
        return "tools" if wants_tools and state.get("rounds", 0) < max_rounds else "answer"

    def run_tools(state: State) -> dict[str, Any]:
        """Run every tool call of the last message and record which sections were shown."""
        last = state["messages"][-1]
        assert isinstance(last, AIMessage)
        results, shown = [], []
        for call in last.tool_calls:
            chosen = by_name.get(call["name"])
            if chosen is None:
                output = f"There is no tool named {call['name']!r}."
            else:
                try:
                    output = str(chosen.invoke(call["args"]))
                except Exception as error:  # a bad argument is the model's to fix, not a crash
                    output = f"The tool failed: {type(error).__name__}: {error}"
            shown.extend(ids_in(output, index))
            results.append(ToolMessage(output, tool_call_id=call["id"], name=call["name"]))
        return {
            "messages": results,
            "shown": shown,
            "rounds": state.get("rounds", 0) + 1,
        }

    def answer(state: State) -> dict[str, Any]:
        """Write the answer, then check every citation against what was shown."""
        messages = list(state["messages"])
        # A reply that still asks for tools (budget spent) is dropped: its calls were never run.
        if isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
            messages = messages[:-1]
        instructions = prompts.ANSWER
        if state.get("answer_problem"):
            instructions += f"\n\nYour previous answer was rejected: {state['answer_problem']}"
        result = answerer.invoke([SystemMessage(system), *messages, HumanMessage(instructions)])
        attempts = state.get("answer_attempts", 0) + 1
        problem = citation_problem(result, set(state.get("shown", [])))
        if problem is None:
            text = result.answer.strip()
            if result.refused and not text.startswith(REFUSAL_PREFIX):
                text = f"{REFUSAL_PREFIX}: {text}"
            return {
                "answer": text,
                "citations": list(dict.fromkeys(result.citations)),
                "refused": result.refused,
                "answer_attempts": attempts,
                "answer_problem": None,
            }
        if attempts < ANSWER_ATTEMPTS:
            return {"answer_attempts": attempts, "answer_problem": problem}
        return {
            "answer": f"{REFUSAL_PREFIX}: no answer could be supported by the passages read.",
            "citations": [],
            "refused": True,
            "answer_attempts": attempts,
            "answer_problem": problem,
        }

    def route_answer(state: State) -> Literal["answer", "__end__"]:
        """Retry an answer whose citations failed the check, once."""
        return "answer" if state.get("answer_problem") and "answer" not in state else END

    graph = StateGraph(State)
    graph.add_node("research", research)
    graph.add_node("tools", run_tools)
    graph.add_node("answer", answer)
    graph.add_edge(START, "research")
    graph.add_conditional_edges("research", route_research, ["tools", "answer"])
    graph.add_edge("tools", "research")
    graph.add_conditional_edges("answer", route_answer, ["answer", END])
    return graph.compile()


def citation_problem(result: Answer, shown: set[str]) -> str | None:
    """Why an answer's citations are unacceptable, or None when they are fine."""
    if result.refused:
        return "a refusal cites nothing" if result.citations else None
    if not result.citations:
        return "an answer must cite at least one section it read"
    unknown = [cid for cid in result.citations if cid not in shown]
    if unknown:
        return f"these ids were never shown to you: {', '.join(unknown)}"
    return None


def chat_model(dev: bool | None = None) -> BaseChatModel:
    """The Anthropic model from the environment: `STUDBOOK_MODEL`, or Sonnet, or Haiku for dev."""
    from langchain_anthropic import ChatAnthropic

    if dev is None:
        dev = os.environ.get("STUDBOOK_DEV") == "1"
    model_id = os.environ.get("STUDBOOK_MODEL") or (DEV_MODEL if dev else DEFAULT_MODEL)
    return ChatAnthropic(model=model_id, temperature=0, max_tokens=2048, max_retries=3)


def ask(question: str, *, model: BaseChatModel | None = None, index: Index | None = None) -> dict:
    """Answer one question; the result names every cited section and where it lives."""
    index = index or load_index()
    graph = build_graph(model or chat_model(), index)
    state = graph.invoke({"question": question}, {"recursion_limit": 4 * MAX_ROUNDS + 10})
    return result_of(state, index)


def result_of(state: dict, index: Index) -> dict:
    """The public shape of a finished run."""
    return {
        "answer": state.get("answer", f"{REFUSAL_PREFIX}: the run ended without an answer."),
        "refused": bool(state.get("refused", True)),
        "citations": [
            {
                "id": cid,
                "repo": index.by_id[cid].repo,
                "path": index.by_id[cid].path,
                "heading": index.by_id[cid].heading,
            }
            for cid in state.get("citations", [])
            if cid in index.by_id
        ],
        "tool_rounds": state.get("rounds", 0),
        "sections_shown": len(state.get("shown", [])),
    }


def platform_graph(config: dict | None = None) -> Any:
    """The graph LangGraph's server and Studio load (langgraph.json)."""
    return build_graph(chat_model(), load_index())


def messages_text(messages: Sequence[AnyMessage]) -> str:
    """A transcript, for debugging."""
    return "\n".join(f"{type(m).__name__}: {m.content}" for m in messages)
