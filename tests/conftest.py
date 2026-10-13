"""A tiny corpus and a scripted model, so the graph runs with no network and no key."""

from collections.abc import Iterator

import pytest
from langchain_core.messages import AIMessage

from studbook_agent.corpus import sections_of
from studbook_agent.index import Index

ADR = """# 0001: Keep control state in the git common directory

## Context

Worktrees each had their own copy of the active change, so two sessions disagreed.

## Decision

Control state moves into the git common directory, shared by every worktree.

## Alternatives

A tracked `.workhorse/active` file was rejected: it conflicted on every merge.
"""

README = """# Paddock

## What it is

A desktop app that shows gate documents and lets a person approve them.
"""


@pytest.fixture
def index() -> Index:
    """Two small documents in two repositories."""
    return Index(
        sections_of("workhorse", "docs/adr/0001-control-state.md", ADR)
        + sections_of("paddock", "README.md", README)
    )


class ScriptedModel:
    """Replays tool-calling replies, then structured answers, in order."""

    def __init__(self, replies: list[AIMessage], answers: list[object]):
        """Keep the scripts."""
        self.replies: Iterator[AIMessage] = iter(replies)
        self.answers: Iterator[object] = iter(answers)
        self.prompts: list[list] = []

    def bind_tools(self, tools):
        """The researcher."""
        model = self

        class Researcher:
            def invoke(self, messages):
                """Next scripted reply."""
                model.prompts.append(messages)
                return next(model.replies)

        return Researcher()

    def with_structured_output(self, schema):
        """The answerer."""
        model = self

        class Answerer:
            def invoke(self, messages):
                """Next scripted answer."""
                model.prompts.append(messages)
                return next(model.answers)

        return Answerer()


def call(name: str, args: dict, call_id: str = "c1") -> AIMessage:
    """A reply asking for one tool call."""
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": call_id}])
