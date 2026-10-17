"""Tannhauser's record as sections, and the search path that needs only Python."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from studbook_agent import record
from studbook_agent.corpus import matches
from studbook_agent.tannhauser import tannhauser_sections

RULEBOOK = """# Rulebook

Lessons that hold on every project.

- **R5** Check one value either side of every switch. (TG-02 drill)
- **R6** The security reviewer is no backup for correctness. (TG-02)
"""

LEDGER = """# Ledger

| Run | Ask | Outcome |
| --- | --- | --- |
| TG-01 Nexus | Start stage 1 | Live 04:17 |
| TG-02 Sebastian | Start stage 2 | Merged 00:38 |
"""

DESIGN = {
    "kind": "design",
    "run": "TG-03 Offworld",
    "title": "A notice while offline",
    "lede": "Wasl says when you are offline.",
    "lessons": [{"id": "W5", "plain": "Run the type check before building."}],
    "parts": [
        {"heading": "The ask", "style": "quote", "paras": ["start stage 3"]},
        {"heading": "What will change", "bullets": ["A slim bar appears at the top."]},
    ],
    "detail": [{"heading": "The code", "paras": ["New `src/lib/connectivity.ts`."]}],
}

DECISIONS = [
    {
        "at": "2026-10-17T00:48:00Z",
        "step": "recon",
        "choice": "Picked the offline notice.",
        "not_taken": "A change to who can see what.",
        "why": "Every check for it can run.",
    }
]

REVIEWS = {
    "plain": [
        {
            "kind": "design",
            "verdict": "fail",
            "findings": [{"quote": "the hook", "problem": "undefined", "fix": "the safety rules"}],
        }
    ],
    "build": [
        {
            "round": 1,
            "head": "08d8743",
            "code": {
                "verdict": "fail",
                "findings": [
                    {
                        "severity": "blocking",
                        "where": "routes.tsx:42",
                        "plain": "No notice on onboarding.",
                    }
                ],
            },
            "security": {"verdict": "pass", "findings": []},
        }
    ],
}


def test_each_lesson_is_its_own_section_cited_by_label():
    """A notes file becomes one section per labelled lesson, plus its introduction."""
    sections = tannhauser_sections("tannhauser", "notes/rulebook.md", RULEBOOK)
    by_id = {s.id: s for s in sections}
    assert by_id["tannhauser:notes/rulebook.md#R5"].heading == "Rulebook > R5"
    assert by_id["tannhauser:notes/rulebook.md#R5"].doc_type == "lesson"
    assert "(TG-02 drill)" in by_id["tannhauser:notes/rulebook.md#R5"].text
    assert "R6" in by_id["tannhauser:notes/rulebook.md#R6"].text
    assert not any("Check one value" in s.text for s in sections if "#R" not in s.id)


def test_retired_lessons_are_marked():
    """A lesson in retired.md is typed so a search can leave it out."""
    text = "# Retired lessons\n\n- **W0** Removed because it was wrong. (TG-03)\n"
    (section,) = [s for s in tannhauser_sections("t", "notes/retired.md", text) if "#W0" in s.id]
    assert section.doc_type == "retired-lesson"


def test_ledger_rows_are_sections_with_labelled_cells():
    """Each ledger row is one section, anchored by its run number."""
    sections = tannhauser_sections("tannhauser", "notes/ledger.md", LEDGER)
    assert [s.id for s in sections] == [
        "tannhauser:notes/ledger.md#TG-01",
        "tannhauser:notes/ledger.md#TG-02",
    ]
    assert "Outcome: Merged 00:38" in sections[1].text
    assert sections[1].heading == "Ledger > TG-02 Sebastian"


def test_design_page_parts_lessons_and_detail():
    """A page becomes its summary, its cited lessons and one section per part."""
    sections = tannhauser_sections("t", "runs/TG-03/design.json", json.dumps(DESIGN))
    headings = [s.heading for s in sections]
    assert headings == [
        "TG-03 Offworld design > Summary",
        "TG-03 Offworld design > Lessons cited",
        "TG-03 Offworld design > The ask",
        "TG-03 Offworld design > What will change",
        "TG-03 Offworld design > Engineering detail > The code",
    ]
    assert sections[1].text == "W5: Run the type check before building."
    assert sections[3].text == "A slim bar appears at the top."
    assert "quote" not in sections[2].text


def test_decisions_and_reviews():
    """Each decision, plain review and reviewer verdict is its own section."""
    (decision,) = tannhauser_sections("t", "runs/TG-03/decisions.json", json.dumps(DECISIONS))
    assert decision.doc_type == "decision"
    assert decision.heading == "TG-03 decisions > recon"
    assert "Not taken: A change to who can see what." in decision.text
    assert decision.date == "2026-10-17"

    reviews = tannhauser_sections("t", "runs/TG-03/reviews.json", json.dumps(REVIEWS))
    assert [s.heading for s in reviews] == [
        "TG-03 plain review > design 1",
        "TG-03 review round 1 > code",
        "TG-03 review round 1 > security",
    ]
    assert 'Sent back: "the hook"' in reviews[0].text
    assert "severity: blocking; where: routes.tsx:42" in reviews[1].text


def test_broken_json_is_skipped_not_fatal():
    """A half-written run file yields nothing rather than stopping the whole index."""
    assert tannhauser_sections("t", "runs/TG-09/run.json", "{not json") == []


def test_double_star_matches_no_folder():
    """`docs/**/*.md` covers a file directly in `docs/`, as well as deeper ones."""
    assert matches("docs/ci.md", ("docs/**/*.md",))
    assert matches("docs/a/b/c.md", ("docs/**/*.md",))
    assert not matches("src/ci.md", ("docs/**/*.md",))


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """A corpus file over a small Tannhauser repository and one missing optional repo."""
    gate = tmp_path / "tannhauser-gate"
    (gate / "notes").mkdir(parents=True)
    (gate / "runs" / "TG-03").mkdir(parents=True)
    (gate / "notes" / "rulebook.md").write_text(RULEBOOK, encoding="utf-8")
    (gate / "runs" / "TG-03" / "decisions.json").write_text(json.dumps(DECISIONS), encoding="utf-8")
    config = tmp_path / "corpus.toml"
    config.write_text(
        '[[repo]]\nname = "tannhauser"\npath = "tannhauser-gate"\nkind = "tannhauser"\n'
        'include = ["notes/**/*.md", "runs/**/*.json"]\n\n'
        '[[repo]]\nname = "wasl"\npath = "wasl"\noptional = true\n',
        encoding="utf-8",
    )
    record.load_index.cache_clear()
    yield config
    record.load_index.cache_clear()


def test_search_and_read_without_a_model(corpus: Path):
    """Search returns ids with snippets; read returns the section, or an error for an unknown id."""
    hits = record.search("value either side of every switch", corpus=str(corpus))
    assert hits[0]["id"] == "tannhauser:notes/rulebook.md#R5"
    assert hits[0]["snippet"].startswith("R5 Check one value")
    found = record.read("tannhauser:runs/TG-03/decisions.json#0", corpus=str(corpus))
    assert found["doc_type"] == "decision"
    assert "error" in record.read("tannhauser:nope#1", corpus=str(corpus))


def test_index_rebuilds_when_a_record_changes(corpus: Path):
    """A lesson added after the cache was written is found on the next search."""
    record.search("anything", corpus=str(corpus))
    rulebook = corpus.parent / "tannhauser-gate" / "notes" / "rulebook.md"
    rulebook.write_text(RULEBOOK + "- **R9** Mount app-wide notices once at the root. (TG-03)\n")
    later = rulebook.stat().st_mtime + 5
    os.utime(rulebook, (later, later))
    record.load_index.cache_clear()
    hits = record.search("mount notices at the root", corpus=str(corpus))
    assert hits[0]["id"] == "tannhauser:notes/rulebook.md#R9"


def test_a_missing_required_repo_is_an_error(corpus: Path):
    """Only repositories marked optional may be absent."""
    corpus.write_text(corpus.read_text() + '\n[[repo]]\nname = "gone"\npath = "gone"\n')
    with pytest.raises(FileNotFoundError):
        record.search("anything", corpus=str(corpus))


def test_the_search_path_loads_no_model_library():
    """`studbook_agent.record` imports neither the graph nor any model or LangChain package."""
    src = Path(__file__).resolve().parents[1] / "src"
    code = (
        "import sys; import studbook_agent.record, studbook_agent.cli; "
        "bad = [m for m in sys.modules if m.split('.')[0] in "
        "('langgraph', 'langchain_core', 'langchain_anthropic', 'anthropic', 'pydantic', 'mcp') "
        "or m == 'studbook_agent.graph']; print(bad); sys.exit(1 if bad else 0)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        env={**os.environ, "PYTHONPATH": str(src)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
