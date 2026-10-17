"""Readers for a Tannhauser Gate repository's record: its lessons, ledger and run folders.

Tannhauser keeps its memory in two shapes the markdown reader cuts badly. A notes file is a
list of labelled lessons (`- **R5** ... (TG-02 drill)`), so each lesson becomes one section,
cited by its label: `tannhauser:notes/rulebook.md#R5`. A run folder (`runs/TG-03/`) is JSON:
the design and deployment pages, the decisions made alone, every review round and the retro.
Each part, decision and review becomes one section in plain sentences, so a search for "why
cloud merge" finds the decision itself rather than a whole file.
"""

import json
import re

from studbook_agent.corpus import DATE, MAX_WORDS, Section, sections_of, split_words

LESSON = re.compile(r"^- \*\*([A-Z]\d+)\*\*\s+(.+)$")
TITLE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
RUN_FOLDER = re.compile(r"^runs/([^/]+)/([^/]+)\.json$")


def tannhauser_sections(repo: str, relative: str, text: str) -> list[Section]:
    """The sections of one file of a Tannhauser repository."""
    if relative.endswith(".json"):
        return run_sections(repo, relative, text)
    if relative.startswith("notes/") and relative.endswith("ledger.md"):
        return ledger_sections(repo, relative, text)
    if relative.startswith("notes/") and relative.endswith(".md"):
        return lesson_sections(repo, relative, text)
    return sections_of(repo, relative, text)


def make(
    repo: str, relative: str, anchor: str, heading: str, kind: str, text: str
) -> list[Section]:
    """One section, or several numbered ones when the text is over the word budget."""
    pieces = split_words(text.strip(), MAX_WORDS) or [""]
    date = DATE.search(text)
    found = []
    for number, piece in enumerate(pieces):
        suffix = f".{number}" if len(pieces) > 1 else ""
        found.append(
            Section(
                id=f"{repo}:{relative}#{anchor}{suffix}",
                repo=repo,
                path=relative,
                heading=heading,
                doc_type=kind,
                date=date[1] if date else None,
                text=piece,
            )
        )
    return found


def lesson_sections(repo: str, relative: str, text: str) -> list[Section]:
    """One section per labelled lesson; the rest of the file as ordinary sections."""
    title_match = TITLE.search(text)
    title = title_match[1] if title_match else relative
    kind = "retired-lesson" if relative.endswith("retired.md") else "lesson"
    found: list[Section] = []
    rest = []
    for line in text.splitlines():
        match = LESSON.match(line.strip())
        if match:
            label = match[1]
            found += make(repo, relative, label, f"{title} > {label}", kind, f"{label} {match[2]}")
        else:
            rest.append(line)
    if any(line.strip() and not line.startswith("#") for line in rest):
        found += sections_of(repo, relative, "\n".join(rest))
    return found


def ledger_sections(repo: str, relative: str, text: str) -> list[Section]:
    """One section per ledger row, each cell labelled with its column."""
    rows = [line for line in text.splitlines() if line.strip().startswith("|")]
    if len(rows) < 3:
        return sections_of(repo, relative, text)
    header = cells(rows[0])
    found: list[Section] = []
    for row in rows[2:]:
        values = cells(row)
        if not values or not values[0]:
            continue
        body = "\n".join(f"{name}: {value}" for name, value in zip(header, values, strict=False))
        anchor = values[0].split()[0]
        found += make(repo, relative, anchor, f"Ledger > {values[0]}", "ledger", body)
    return found


def cells(row: str) -> list[str]:
    """The cells of one markdown table row."""
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def leaves(value: object, label: str = "") -> list[str]:
    """Every scalar inside a JSON value as `label: value` lines, nested labels joined by dots."""
    if isinstance(value, dict):
        lines = []
        for key, inner in value.items():
            lines += leaves(inner, f"{label}.{key}" if label else str(key))
        return lines
    if isinstance(value, list):
        lines = []
        for inner in value:
            lines += leaves(inner, label)
        return lines
    if value is None or value == "":
        return []
    return [f"{label}: {value}" if label else str(value)]


def prose(part: dict) -> str:
    """The words of one page part: its paragraphs, bullets and table rows, without layout keys."""
    words = {key: inner for key, inner in part.items() if key not in ("heading", "style")}
    return "\n".join(line.split(": ", 1)[-1] for line in leaves(words))


def run_sections(repo: str, relative: str, text: str) -> list[Section]:
    """The sections of one JSON file in a run folder."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    folder = RUN_FOLDER.match(relative)
    name = folder[2] if folder else relative.rsplit("/", 1)[-1].removesuffix(".json")
    run = (data.get("run") if isinstance(data, dict) else None) or (folder[1] if folder else name)
    if name in ("design", "deployment") and isinstance(data, dict):
        return page_sections(repo, relative, run, name, data)
    if name == "decisions" and isinstance(data, list):
        found = []
        for number, item in enumerate(data):
            body = (
                f"Chose: {item.get('choice', '')}\nNot taken: {item.get('not_taken', '')}\n"
                f"Why: {item.get('why', '')}\nAt: {item.get('at', '')}"
            )
            heading = f"{run} decisions > {item.get('step', 'decision')}"
            found += make(repo, relative, str(number), heading, "decision", body)
        return found
    if name == "reviews" and isinstance(data, dict):
        return review_sections(repo, relative, run, data)
    kinds = {"run": "run", "retro": "retro", "drill": "review"}
    heading = f"{run} {'record' if name == 'run' else name}"
    return make(repo, relative, name, heading, kinds.get(name, "doc"), "\n".join(leaves(data)))


def page_sections(repo: str, relative: str, run: str, name: str, page: dict) -> list[Section]:
    """A design or deployment page: the summary, the lessons it cited, then each part."""
    found: list[Section] = []
    summary = "\n".join(str(page[key]) for key in ("title", "lede", "flag") if page.get(key))
    found += make(repo, relative, "summary", f"{run} {name} > Summary", name, summary)
    lessons = page.get("lessons") or []
    if lessons:
        body = "\n".join(f"{item.get('id')}: {item.get('plain', '')}" for item in lessons)
        found += make(repo, relative, "lessons", f"{run} {name} > Lessons cited", name, body)
    for group, prefix in (("parts", ""), ("detail", "Engineering detail > ")):
        for number, part in enumerate(page.get(group) or []):
            heading = f"{run} {name} > {prefix}{part.get('heading', number)}"
            anchor = f"{group}.{number}"
            found += make(repo, relative, anchor, heading, name, prose(part))
    return found


def review_sections(repo: str, relative: str, run: str, reviews: dict) -> list[Section]:
    """Each plain-language review and each build review round, one section per reviewer."""
    found: list[Section] = []
    for number, review in enumerate(reviews.get("plain") or []):
        lines = [f"Verdict: {review.get('verdict')}"]
        for finding in review.get("findings") or []:
            lines.append(
                f'Sent back: "{finding.get("quote", "")}". Problem: {finding.get("problem", "")} '
                f"Fix: {finding.get('fix', '')}"
            )
        heading = f"{run} plain review > {review.get('kind', 'page')} {number + 1}"
        found += make(repo, relative, f"plain.{number}", heading, "review", "\n".join(lines))
    for review_round in reviews.get("build") or []:
        number = review_round.get("round", len(found))
        for reviewer in ("code", "security"):
            verdict = review_round.get(reviewer)
            if not isinstance(verdict, dict):
                continue
            lines = [f"Verdict: {verdict.get('verdict')} on {review_round.get('head', '')}"]
            for finding in verdict.get("findings") or []:
                lines.append(
                    "; ".join(
                        f"{key}: {finding[key]}"
                        for key in ("severity", "where", "plain", "detail", "proof", "fixed")
                        if finding.get(key)
                    )
                )
            heading = f"{run} review round {number} > {reviewer}"
            anchor = f"build.{number}.{reviewer}"
            found += make(repo, relative, anchor, heading, "review", "\n".join(lines))
    return found
