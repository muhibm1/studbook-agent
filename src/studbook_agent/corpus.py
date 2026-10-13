"""Read the engineering records named in `corpus.toml` and cut them into sections.

A *record* is a markdown file a team writes to explain itself: decision records (ADRs),
design specs, plans, retrospectives, gate packets, READMEs, changelogs. Code is not a record.

Each file is cut at its `##` headings, and a long `##` section at its `###` headings, so a
search hit is a passage someone wrote to answer one question, not an arbitrary window of text.
A section still over `MAX_WORDS` is split by paragraph. Every section keeps where it came from
(repository, path, the heading path), which is what a citation points at.
"""

import fnmatch
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

MAX_WORDS = 600
HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*#*\s*$")
DATE = re.compile(r"(20\d\d-\d\d-\d\d)")
DEFAULT_EXCLUDE = (
    "**/node_modules/**",
    "**/vendor/**",
    "**/verify-logs/**",
    "**/.git/**",
    "**/.claude/**",
    "**/CLAUDE.md",
    "**/.env*",
)


@dataclass(frozen=True)
class Repo:
    """One repository in the corpus."""

    name: str
    path: Path
    include: tuple[str, ...]
    exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class Section:
    """One citable passage."""

    id: str
    repo: str
    path: str
    heading: str
    doc_type: str
    date: str | None
    text: str


def load_corpus(config: Path) -> list[Repo]:
    """The repositories listed in a corpus file; relative paths resolve against the file."""
    raw = tomllib.loads(config.read_text(encoding="utf-8"))
    repos = []
    for entry in raw.get("repo", []):
        path = Path(entry["path"]).expanduser()
        if not path.is_absolute():
            path = (config.parent / path).resolve()
        repos.append(
            Repo(
                name=entry["name"],
                path=path,
                include=tuple(entry.get("include", ["**/*.md"])),
                exclude=tuple(entry.get("exclude", ())),
            )
        )
    return repos


def matches(relative: str, patterns: tuple[str, ...]) -> bool:
    """Whether a POSIX relative path matches any glob (`**/` also matches at the root)."""
    for pattern in patterns:
        if fnmatch.fnmatch(relative, pattern):
            return True
        if pattern.startswith("**/") and fnmatch.fnmatch(relative, pattern[3:]):
            return True
    return False


def files_of(repo: Repo) -> list[Path]:
    """Every included, non-excluded markdown file of a repository, sorted."""
    if not repo.path.is_dir():
        raise FileNotFoundError(f"corpus repo {repo.name}: {repo.path} is not a directory")
    found = []
    for path in sorted(repo.path.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(repo.path).as_posix()
        if matches(relative, repo.include) and not matches(
            relative, (*DEFAULT_EXCLUDE, *repo.exclude)
        ):
            found.append(path)
    return found


def doc_type(relative: str) -> str:
    """A coarse document type from the path, for filtering and for the answer's citations."""
    lower = relative.lower()
    name = lower.rsplit("/", 1)[-1]
    if "/adr/" in f"/{lower}" or name.startswith("adr") or "decisions" in name:
        return "decision"
    for marker, kind in (
        ("retro", "retro"),
        ("spec", "spec"),
        ("plan", "plan"),
        ("brief", "brief"),
        ("ship", "ship"),
        ("readme", "readme"),
        ("changelog", "changelog"),
        ("research", "research"),
        ("status", "status"),
    ):
        if marker in lower:
            return kind
    return "doc"


def split_words(text: str, limit: int) -> list[str]:
    """Paragraph-aligned pieces of `text`, each at most about `limit` words."""
    pieces, current, count = [], [], 0
    for paragraph in re.split(r"\n\s*\n", text):
        words = len(paragraph.split())
        if current and count + words > limit:
            pieces.append("\n\n".join(current))
            current, count = [], 0
        current.append(paragraph)
        count += words
    if current:
        pieces.append("\n\n".join(current))
    return pieces


def sections_of(repo: str, relative: str, text: str) -> list[Section]:
    """The citable sections of one file."""
    title = relative
    blocks: list[tuple[list[str], list[str]]] = [([], [])]  # (heading path, lines)
    path_now: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        match = None if in_fence else HEADING.match(line)
        if match:
            level, heading = len(match[1]), match[2].strip()
            if level == 1:
                title = heading
                path_now = [heading]
                continue
            path_now = path_now[: level - 1] if path_now else []
            while len(path_now) < level - 1:
                path_now.append(title)
            path_now.append(heading)
            # Start a new block at every ## and at ### (merged back below when short).
            blocks.append((list(path_now), [line]))
            continue
        blocks[-1][1].append(line)

    merged: list[tuple[list[str], str]] = []
    for heading_path, lines in blocks:
        body = "\n".join(lines).strip()
        if not body:
            continue
        is_h3 = len(heading_path) >= 3
        if is_h3 and merged and len(merged[-1][1].split()) + len(body.split()) <= MAX_WORDS:
            merged[-1] = (merged[-1][0], merged[-1][1] + "\n\n" + body)
        else:
            merged.append((heading_path or [title], body))

    date_match = DATE.search(relative) or DATE.search(text[:2000])
    kind = doc_type(relative)
    sections = []
    for heading_path, body in merged:
        for piece in split_words(body, MAX_WORDS):
            number = len(sections)
            heading = " > ".join(dict.fromkeys([title, *heading_path]))
            sections.append(
                Section(
                    id=f"{repo}:{relative}#{number}",
                    repo=repo,
                    path=relative,
                    heading=heading,
                    doc_type=kind,
                    date=date_match[1] if date_match else None,
                    text=piece,
                )
            )
    return sections


def read_corpus(repos: list[Repo]) -> list[Section]:
    """Every section of every file of every repository."""
    sections: list[Section] = []
    for repo in repos:
        for path in files_of(repo):
            text = path.read_text(encoding="utf-8", errors="replace")
            sections.extend(sections_of(repo.name, path.relative_to(repo.path).as_posix(), text))
    return sections
