"""Search and read the record with plain Python: no model, no key, nothing to install.

This is the path other agents use when they do their own reading, such as Tannhauser's
recon, designer and reviewers. They search here, read the sections they need, and write the
answer themselves, so the only cost is their own session. `studbook-agent ask` (the graph) is
the paid path and lives in `graph.py`; nothing here imports it.

    python3 -m studbook_agent.record search "why cloud merge" [--repo tannhauser] [--json]
    python3 -m studbook_agent.record read "tannhauser:notes/rulebook.md#R5"
    python3 -m studbook_agent.record index

Run it from the repository root with `PYTHONPATH=src`, or after `pip install -e .`.
"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

from studbook_agent.corpus import files_of, load_corpus, read_corpus
from studbook_agent.index import Index

READ_CHARS = 6000


def corpus_path() -> Path:
    """The corpus file: `STUDBOOK_CORPUS`, else the public corpus next to this package."""
    configured = os.environ.get("STUDBOOK_CORPUS")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "corpus.public.toml"


def newest_source(config: Path) -> float:
    """The latest change time across the corpus file, every file it covers and this package."""
    newest = max(path.stat().st_mtime for path in [config, *Path(__file__).parent.glob("*.py")])
    for repo in load_corpus(config):
        if repo.optional and not repo.path.is_dir():
            continue
        for path in files_of(repo):
            newest = max(newest, path.stat().st_mtime)
    return newest


@lru_cache(maxsize=4)
def load_index(corpus: str | None = None) -> Index:
    """The index for a corpus file, rebuilt when any file it covers has changed since the cache."""
    path = Path(corpus) if corpus else corpus_path()
    cache = path.parent / ".index" / f"{path.stem}.json"
    if cache.exists() and cache.stat().st_mtime >= newest_source(path):
        return Index.load(cache)
    index = Index(read_corpus(load_corpus(path)))
    index.save(cache)
    return index


def search(
    query: str,
    *,
    repo: str | None = None,
    doc_type: str | None = None,
    k: int = 6,
    corpus: str | None = None,
) -> list[dict]:
    """The best sections for a query, as plain dictionaries with a short snippet each."""
    hits = load_index(corpus).search(query, k=k, repo=repo, doc_type=doc_type)
    return [
        {
            "id": section.id,
            "repo": section.repo,
            "path": section.path,
            "heading": section.heading,
            "doc_type": section.doc_type,
            "date": section.date,
            "score": round(score, 2),
            "snippet": " ".join(section.text.split())[:280],
        }
        for section, score in hits
    ]


def read(section_id: str, *, corpus: str | None = None) -> dict:
    """One section in full (capped at `READ_CHARS`), or an error naming the unknown id."""
    section = load_index(corpus).by_id.get(section_id)
    if section is None:
        return {"error": f"no section with id {section_id}"}
    found = asdict(section)
    found["text"] = section.text[:READ_CHARS]
    return found


def main(argv: list[str] | None = None) -> int:
    """Entry point for `python3 -m studbook_agent.record`."""
    summary = __doc__.split("\n\n")[0]
    parser = argparse.ArgumentParser(prog="studbook_agent.record", description=summary)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("index", help="build the index and print what it holds")
    find = sub.add_parser("search", help="run one search")
    find.add_argument("query")
    find.add_argument("--repo")
    find.add_argument("--type", dest="doc_type")
    find.add_argument("-k", type=int, default=6)
    find.add_argument("--json", action="store_true", help="print the hits as JSON")
    show = sub.add_parser("read", help="print one section in full")
    show.add_argument("id")
    args = parser.parse_args(argv)

    if args.command == "index":
        index = load_index()
        print(f"{corpus_path()}: {len(index.sections)} sections")
        for repo, count in sorted(index.repos().items()):
            print(f"  {repo}: {count}")
        return 0
    if args.command == "search":
        hits = search(args.query, repo=args.repo, doc_type=args.doc_type, k=args.k)
        if args.json:
            print(json.dumps(hits, indent=2))
            return 0
        for hit in hits:
            print(f"{hit['score']:6.1f}  {hit['id']}\n        {hit['heading']}")
        return 0
    found = read(args.id)
    print(json.dumps(found, indent=2))
    return 1 if "error" in found else 0


if __name__ == "__main__":
    sys.exit(main())
