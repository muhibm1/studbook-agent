"""The adapter between Flywheel and the Studbook agent.

A test case is a question with the passages that answer it (`gold`: repository and path) and a
reference answer. Three checks grade a run:

- `found_the_source`: an answerable question's answer cites at least one gold file; an
  unanswerable question's answer cites nothing.
- `refused_correctly`: the agent refused exactly when the record does not hold the answer.
- `answer_correct`: a model judge compares the answer with the reference. It runs only with
  `STUDBOOK_JUDGE=1`, because it costs a model call per run.
"""

import json
import os
from typing import Any

from studbook_agent.graph import ask

JUDGE_MODEL = "claude-haiku-4-5-20251001"
JUDGE_PROMPT = """You grade an answer about a software team's engineering record.

Question: {question}
Reference answer: {reference}
Answer to grade: {answer}

Is the answer to grade correct and consistent with the reference? Extra correct detail is fine;
a contradiction, a missing core point, or a refusal when the reference has an answer is not.
Reply with JSON only: {{"correct": true or false, "reason": "one sentence"}}"""


def target(inputs: dict[str, Any]) -> dict[str, Any]:
    """Ask the agent one question."""
    return ask(inputs["question"])


def cited_paths(outputs: dict[str, Any]) -> set[tuple[str, str]]:
    """(repository, path) of every citation."""
    return {(c["repo"], c["path"]) for c in outputs.get("citations", [])}


def found_the_source(inputs: dict, outputs: dict, reference_outputs: dict) -> bool:
    """Answerable: a gold file is cited. Unanswerable: nothing is cited."""
    gold = {(g["repo"], g["path"]) for g in reference_outputs.get("gold", [])}
    if not gold:
        return not outputs.get("citations")
    return bool(gold & cited_paths(outputs))


def refused_correctly(inputs: dict, outputs: dict, reference_outputs: dict) -> bool:
    """The agent refused exactly when the record has no answer."""
    should_refuse = not reference_outputs.get("gold")
    return bool(outputs.get("refused")) == should_refuse


def answer_correct(inputs: dict, outputs: dict, reference_outputs: dict) -> dict[str, Any]:
    """A model judge's verdict against the reference answer; no score unless enabled."""
    if os.environ.get("STUDBOOK_JUDGE") != "1":
        return {"key": "answer_correct", "score": None}
    from langchain_anthropic import ChatAnthropic

    judge = ChatAnthropic(model=JUDGE_MODEL, temperature=0, max_tokens=300)
    reply = judge.invoke(
        JUDGE_PROMPT.format(
            question=inputs["question"],
            reference=reference_outputs.get("reference_answer", ""),
            answer=outputs.get("answer", ""),
        )
    )
    text = str(reply.content)
    verdict = json.loads(text[text.index("{") : text.rindex("}") + 1])
    return {
        "key": "answer_correct",
        "score": bool(verdict["correct"]),
        "comment": verdict["reason"],
    }
