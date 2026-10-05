"""Evidence criteria: what a user can ask a scan to require of its sources, and how many they get.

Each criterion is a plain rule over the metadata the providers return. Missing metadata counts as "not met":
we do not guess in the user's favour. A source that meets every criterion is a full match. Unless the user asks
for strict matching, sources that meet at least half of them (and every "hard" one) are closest matches that
can fill the places full matches leave empty, each labelled with what it missed. Anything below that is excluded
with the criterion and the fact that failed it, so the audit explains every decision.
"""

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from app.synthesis.citation_engine import CitationEngine

FREE_LIMIT = 3
PAID_LIMIT = 8
MIN_SHARE = 0.5   # a closest match meets at least this share of the selected criteria
RECENT_YEARS = 5
HIGHLY_CITED = 10

LABEL_PEER = "Peer-reviewed or journal-associated source"
LABEL_CITED = "Cited source with usable metadata"
LABEL_UNIQUE = "Unique source relevant to the requested topic"
LABEL_RECENT = "Recent publication within the research area"
LABEL_OPEN = "Open access source"
LABEL_HIGHLY = "Highly cited source (10+ citations)"
LABEL_REVIEW = "Review, survey or meta-analysis"
TYPE_PREFIX = "Publication type: "

# The publication-type selector: what the user sees -> the normalized work types it allows.
SOURCE_TYPES: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "journal": ("Journal article", ("journal-article", "review")),
    "conference": ("Conference paper", ("conference-paper",)),
    "preprint": ("Preprint", ("preprint",)),
    "book": ("Book or chapter", ("book", "book-chapter")),
}

# When nothing is selected: cited, recent, and unique and topic-relevant.
DEFAULT_LABELS = (LABEL_CITED, LABEL_RECENT, LABEL_UNIQUE)

_REVIEW_PATTERN = re.compile(
    r"\b(systematic review|scoping review|umbrella review|literature review|review of the literature|"
    r"meta-?analysis|a survey|survey of the literature|state-of-the-art review)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Criterion:
    label: str
    check: Callable[[Dict[str, Any], int], Optional[str]]  # returns None when met, else the fact that failed
    hard: bool = False  # a hard criterion is never relaxed: a closest match must meet it


@dataclass(frozen=True)
class Resolved:
    applied: Tuple[Criterion, ...]
    defaults_applied: bool
    limited: bool
    limit: int
    strict: bool = False

    @property
    def labels(self) -> List[str]:
        return [criterion.label for criterion in self.applied]

    def summary(self) -> Dict[str, Any]:
        return {"applied": self.labels, "defaults_applied": self.defaults_applied,
                "limited": self.limited, "limit": self.limit, "strict": self.strict}


def _number(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _year(source: Dict[str, Any]) -> int:
    try:
        year = int(source.get("year"))
        return year if 1000 <= year <= 9999 else 0
    except (TypeError, ValueError):
        return 0


def _peer(source, now):
    if source.get("is_peer_reviewed") is True or source.get("work_type") in ("journal-article", "review"):
        return None
    return f"not published in a journal (work type: {source.get('work_type') or 'not reported'})"


def _cited(source, now):
    if _number(source.get("citation_count")) < 1:
        return "no citations recorded"
    if not CitationEngine.is_referenceable(source):
        return "metadata is not complete enough to cite"
    return None


def _unique(source, now):
    return None  # duplicates are removed and topical relevance is checked for every scan; this records the intent


def _recent(source, now):
    year = _year(source)
    if not year:
        return "publication year not reported"
    return None if year >= now - RECENT_YEARS else f"published in {year}, before {now - RECENT_YEARS}"


def _open(source, now):
    if source.get("is_open_access") is True:
        return None
    return "not open access" if source.get("is_open_access") is False else "open-access status not reported by the provider"


def _highly_cited(source, now):
    count = _number(source.get("citation_count"))
    return None if count >= HIGHLY_CITED else f"{count} citations"


def _review(source, now):
    if source.get("work_type") == "review":
        return None
    if _REVIEW_PATTERN.search(f"{source.get('title') or ''} {source.get('abstract') or ''}"):
        return None
    return "not a review, survey or meta-analysis"


def _type_check(allowed: Sequence[str], name: str) -> Callable[[Dict[str, Any], int], Optional[str]]:
    def check(source, now):
        work_type = source.get("work_type")
        if work_type in allowed:
            return None
        return f"work type is {work_type or 'not reported'}, not {name.lower()}"
    return check


REGISTRY: Tuple[Criterion, ...] = (
    Criterion(LABEL_PEER, _peer),
    Criterion(LABEL_CITED, _cited),
    Criterion(LABEL_UNIQUE, _unique),
    Criterion(LABEL_RECENT, _recent),
    Criterion(LABEL_OPEN, _open),
    Criterion(LABEL_HIGHLY, _highly_cited),
    Criterion(LABEL_REVIEW, _review),
)
_BY_LABEL = {criterion.label: criterion for criterion in REGISTRY}


def type_criterion(source_type: Optional[str]) -> Optional[Criterion]:
    entry = SOURCE_TYPES.get(str(source_type or "").strip().lower())
    if not entry:
        return None
    name, allowed = entry
    # Choosing "Journal articles" must never admit a preprint, so the type is never relaxed.
    return Criterion(f"{TYPE_PREFIX}{name}", _type_check(allowed, name), hard=True)


def resolve(selected_labels: Optional[Sequence[str]], source_type: Optional[str], paid: bool,
            strict: bool = False) -> Resolved:
    """Turn what a client sent into the criteria that will really be applied.

    Unknown labels are ignored; order is canonical; with nothing selected the defaults apply; the plan's
    limit (3 free, 8 paid) is enforced here so it cannot be bypassed by a client.
    """
    wanted = {str(label).strip() for label in (selected_labels or [])}
    chosen = [criterion for criterion in REGISTRY if criterion.label in wanted]
    by_type = type_criterion(source_type)
    if by_type:
        chosen.append(by_type)
    defaults_applied = not chosen
    if defaults_applied:
        chosen = [_BY_LABEL[label] for label in DEFAULT_LABELS]
    limit = PAID_LIMIT if paid else FREE_LIMIT
    return Resolved(tuple(chosen[:limit]), defaults_applied, len(chosen) > limit, limit, bool(strict))


def current_year() -> int:
    return datetime.now(timezone.utc).year


@dataclass(frozen=True)
class Evaluation:
    met: Tuple[str, ...]
    missed: Tuple[str, ...]        # each with the fact that failed it, e.g. "Open access source (not open access)"
    hard_missed: bool

    @property
    def total(self) -> int:
        return len(self.met) + len(self.missed)

    @property
    def result_text(self) -> str:
        return f"Met all {self.total}" if not self.missed else f"Met {len(self.met)} of {self.total}"


def evaluate(source: Dict[str, Any], resolved: Resolved, now: Optional[int] = None) -> Evaluation:
    """Which selected criteria a source meets and which it misses."""
    year = now or current_year()
    met, missed, hard_missed = [], [], False
    for criterion in resolved.applied:
        fact = criterion.check(source, year)
        if fact:
            missed.append(f"{criterion.label} ({fact})")
            hard_missed = hard_missed or criterion.hard
        else:
            met.append(criterion.label)
    return Evaluation(tuple(met), tuple(missed), hard_missed)


def needed_for_closest(total: int) -> int:
    """How many criteria a closest match must meet."""
    return max(1, math.ceil(total * MIN_SHARE))


def qualification(evaluation: Evaluation, resolved: Resolved) -> str:
    """"full" (meets everything), "closest" (meets enough to fill a gap) or "no"."""
    if not evaluation.missed:
        return "full"
    if resolved.strict or evaluation.hard_missed:
        return "no"
    return "closest" if len(evaluation.met) >= needed_for_closest(evaluation.total) else "no"


def failures(source: Dict[str, Any], resolved: Resolved, now: Optional[int] = None) -> List[str]:
    """Every selected criterion the source misses, each with the fact that failed it."""
    return list(evaluate(source, resolved, now).missed)
