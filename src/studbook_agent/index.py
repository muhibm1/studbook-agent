"""A BM25 index over the record's sections, built in memory and cached as JSON.

BM25 is the ranking function behind most keyword search engines: a section scores higher the
more often it uses the query's words, the rarer those words are across the whole record, and
the shorter the section is. It needs no model, no GPU and no database, and it is good at what
an engineering record needs most: exact names (`interrupt`, `SqliteSaver`, `G4`). The agent
compensates for its weakness, synonyms, by searching more than once with different words.
Headings count three times, because a heading is the author's own summary of the section.
"""

import json
import math
import re
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from studbook_agent.corpus import Section

K1 = 1.4
B = 0.75
HEADING_WEIGHT = 3
TOKEN = re.compile(r"[a-z0-9_]+")
STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "so",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "would",
        "you",
        "our",
        "not",
        "no",
        "can",
        "could",
        "should",
    ]
)


def stem(word: str) -> str:
    """A light suffix strip so `decided`, `decides` and `decision` meet more often."""
    for suffix in ("ations", "ation", "ings", "ing", "ies", "ied", "es", "ed", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def tokens(text: str) -> list[str]:
    """Lower-cased, stemmed words without stopwords; `snake_case` names also split."""
    words = []
    for raw in TOKEN.findall(text.lower()):
        parts = [raw, *raw.split("_")] if "_" in raw else [raw]
        words.extend(stem(part) for part in parts if part and part not in STOPWORDS)
    return words


class Index:
    """Sections plus their term statistics."""

    def __init__(self, sections: list[Section]):
        """Build the index."""
        self.sections = sections
        self.by_id = {section.id: section for section in sections}
        self.terms: list[Counter[str]] = []
        for section in sections:
            counts = Counter(tokens(section.text))
            for word in tokens(section.heading):
                counts[word] += HEADING_WEIGHT
            self.terms.append(counts)
        self.lengths = [sum(counts.values()) for counts in self.terms]
        self.average = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0
        frequency: Counter[str] = Counter()
        for counts in self.terms:
            frequency.update(counts.keys())
        n = len(sections)
        self.idf = {
            word: math.log(1 + (n - df + 0.5) / (df + 0.5)) for word, df in frequency.items()
        }

    def search(
        self,
        query: str,
        *,
        k: int = 6,
        repo: str | None = None,
        doc_type: str | None = None,
    ) -> list[tuple[Section, float]]:
        """The `k` best sections for `query`, optionally within one repository or type."""
        words = set(tokens(query))
        scored = []
        for position, counts in enumerate(self.terms):
            section = self.sections[position]
            if repo and section.repo != repo:
                continue
            if doc_type and section.doc_type != doc_type:
                continue
            score = 0.0
            length = self.lengths[position]
            for word in words:
                tf = counts.get(word)
                if not tf:
                    continue
                norm = tf + K1 * (1 - B + B * length / (self.average or 1))
                score += self.idf[word] * tf * (K1 + 1) / norm
            if score > 0:
                scored.append((section, score))
        scored.sort(key=lambda item: (-item[1], item[0].id))
        return scored[:k]

    def repos(self) -> dict[str, int]:
        """Section counts by repository."""
        return dict(Counter(section.repo for section in self.sections))

    def save(self, path: Path) -> None:
        """Cache the sections as JSON (the statistics rebuild in well under a second)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([asdict(s) for s in self.sections]), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Index":
        """Rebuild from a cache written by `save`."""
        return cls([Section(**raw) for raw in json.loads(path.read_text(encoding="utf-8"))])
