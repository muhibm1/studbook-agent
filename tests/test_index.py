"""Sections and search."""

from studbook_agent.corpus import doc_type, matches, sections_of
from studbook_agent.index import stem, tokens


def test_sections_follow_headings(index):
    """Each ## heading starts a section with the title in its heading path."""
    ids = [s.id for s in index.sections if s.repo == "workhorse"]
    assert ids == [f"workhorse:docs/adr/0001-control-state.md#{n}" for n in range(3)]
    assert index.sections[1].heading.endswith("> Decision")
    assert index.sections[0].doc_type == "decision"


def test_search_ranks_the_decision_first(index):
    """A query in the record's own words finds the decision section."""
    hits = index.search("where does control state live for worktrees")
    assert hits[0][0].heading.endswith("Decision") or hits[0][0].heading.endswith("Context")
    assert index.search("control state", repo="paddock") == []


def test_long_section_splits_by_paragraph():
    """A section over the word budget becomes several sections."""
    body = "\n\n".join("word " * 200 for _ in range(5))
    sections = sections_of("r", "doc.md", f"# T\n\n## Big\n\n{body}")
    assert len(sections) >= 2


def test_code_fences_hide_headings():
    """A `#` line inside a code block is not a heading."""
    text = "# T\n\n## Real\n\n```\n## not a heading\n```\n"
    assert len(sections_of("r", "d.md", text)) == 1


def test_tokens_and_globs():
    """Stemming joins word forms; snake_case splits; `**/` globs match at the root."""
    assert stem("decided") == stem("decides")
    assert "approval" in tokens("needs_approval")
    assert matches("README.md", ("**/README.md",))
    assert not matches("src/a.py", ("**/*.md",))
    assert doc_type("docs/sdlc/x/retro.md") == "retro"
