"""Evidence criteria: what a user can ask a scan to require of its sources, and how many they get.

Each criterion is a plain rule over the metadata the providers return, with three outcomes: met, missed, or
"not reported" when the provider simply does not say (open-access status, publication year). Not reported is
neutral: it is neither a miss nor a match, and it is always shown. A source that meets every criterion is a
full match. Unless the user asks for strict matching, a source that meets at least a minimum share of them
(NEXUS_MIN_CRITERIA_MATCH_PERCENT, default 20%, and every "hard" one) is a closest match that can fill the places
full matches leave empty, each labelled with what it met, missed and could not be checked. Anything below that is
excluded with the criterion and the fact that failed it, so the audit explains every decision.
"""

import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from app.synthesis.citation_engine import CitationEngine

FREE_LIMIT = 3
PAID_LIMIT = 8
MIN_MATCH_ENV = "NEXUS_MIN_CRITERIA_MATCH_PERCENT"
DEFAULT_MIN_MATCH_PERCENT = 20.0
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

def min_match_share() -> float:
    """The share of the selected criteria a closest match must meet, from the Railway variable (default 20%).

    Read on every call so a changed variable takes effect without a code change. Anything that is not a number
    falls back to the default; values are held between 0 and 100.
    """
    raw = os.getenv(MIN_MATCH_ENV)
    try:
        percent = float(raw) if raw not in (None, "") else DEFAULT_MIN_MATCH_PERCENT
    except ValueError:
        percent = DEFAULT_MIN_MATCH_PERCENT
    if percent != percent:   # NaN
        percent = DEFAULT_MIN_MATCH_PERCENT
    return min(max(percent, 0.0), 100.0) / 100.0


class NotReported(str):
    """Returned by a check when the provider does not say, so the criterion can be neither met nor missed."""


_REVIEW_PATTERN = re.compile(
    r"\b(systematic review|scoping review|umbrella review|literature review|review of the literature|"
    r"meta-?analysis|a survey|survey of the literature|state-of-the-art review)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Criterion:
    label: str
    check: Callable[[Dict[str, Any], int], Optional[str]]  # None = met, str = missed, NotReported = cannot tell
    hard: bool = False      # a hard criterion is never relaxed: a closest match must meet it
    baseline: bool = False  # always applied to every scan, so it is shown but not counted


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
        return NotReported("publication year not reported")
    return None if year >= now - RECENT_YEARS else f"published in {year}, before {now - RECENT_YEARS}"


def _open(source, now):
    if source.get("is_open_access") is True:
        return None
    if source.get("is_open_access") is False:
        return "not open access"
    return NotReported("open-access status not reported by the provider")


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
    Criterion(LABEL_UNIQUE, _unique, baseline=True),
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
    unreported: Tuple[str, ...]    # each with what could not be checked, e.g. "Open access source (status not reported)"
    hard_missed: bool

    @property
    def total(self) -> int:
        return len(self.met) + len(self.missed) + len(self.unreported)

    @property
    def gap(self) -> int:
        """How far from a full match: misses plus anything that could not be confirmed."""
        return len(self.missed) + len(self.unreported)

    @property
    def result_text(self) -> str:
        if self.total == 0:
            return "Topic relevance only"
        if not self.gap:
            return f"Met all {self.total}"
        text = f"Met {len(self.met)} of {self.total}"
        return text + (f", {len(self.unreported)} not reported" if self.unreported else "")


def evaluate(source: Dict[str, Any], resolved: Resolved, now: Optional[int] = None) -> Evaluation:
    """Which selected criteria a source meets, misses, or cannot be checked against.

    Baseline criteria (unique and topic-relevant) apply to every scan and are not counted.
    """
    year = now or current_year()
    met, missed, unreported, hard_missed = [], [], [], False
    for criterion in resolved.applied:
        if criterion.baseline:
            continue
        fact = criterion.check(source, year)
        if fact is None:
            met.append(criterion.label)
        elif isinstance(fact, NotReported):
            unreported.append(f"{criterion.label} ({fact})")
        else:
            missed.append(f"{criterion.label} ({fact})")
            hard_missed = hard_missed or criterion.hard
    return Evaluation(tuple(met), tuple(missed), tuple(unreported), hard_missed)


def needed_for_closest(total: int) -> int:
    """How many criteria a closest match must meet: the configured share, and never fewer than one."""
    return max(1, math.ceil(round(total * min_match_share(), 6)))


def qualification(evaluation: Evaluation, resolved: Resolved) -> str:
    """"full" (meets everything), "closest" (meets enough to fill a gap) or "no".

    Strict matching wants every criterion confirmed, so a criterion the provider did not report is not enough.
    """
    if not evaluation.gap:
        return "full"
    if resolved.strict or evaluation.hard_missed:
        return "no"
    return "closest" if len(evaluation.met) >= needed_for_closest(evaluation.total) else "no"


# --- asking the providers for what the criteria need -----------------------------------------------------------------------

def retrieval_hints(resolved: Resolved, now: Optional[int] = None) -> Dict[str, Any]:
    """What the selected criteria let a provider filter on, so the search itself returns candidates that can meet them."""
    year = now or current_year()
    labels = set(resolved.labels)
    hints: Dict[str, Any] = {}
    if LABEL_RECENT in labels:
        hints["year_from"] = year - RECENT_YEARS
    if LABEL_OPEN in labels:
        hints["open_access"] = True
    if LABEL_HIGHLY in labels:
        hints["min_citations"] = HIGHLY_CITED
    if LABEL_REVIEW in labels:
        hints["review"] = True
    for name, allowed in SOURCE_TYPES.values():
        if f"{TYPE_PREFIX}{name}" in labels:
            hints["work_types"] = list(allowed)
    return hints


def hint_variants(hints: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The extra searches to run: everything asked for at once, then the rarest ask on its own."""
    if not hints:
        return []
    variants = [dict(hints)]
    if hints.get("review") and len(hints) > 1:
        variants.append({"review": True})
    return variants


def describe_hints(hints: Dict[str, Any]) -> str:
    parts = []
    if hints.get("review"):
        parts.append("reviews")
    if hints.get("work_types"):
        parts.append(" / ".join(hints["work_types"]))
    if hints.get("open_access"):
        parts.append("open access")
    if hints.get("min_citations"):
        parts.append(f"{hints['min_citations']}+ citations")
    if hints.get("year_from"):
        parts.append(f"from {hints['year_from']}")
    return ", ".join(parts)


def failures(source: Dict[str, Any], resolved: Resolved, now: Optional[int] = None) -> List[str]:
    """Every selected criterion the source misses, each with the fact that failed it."""
    return list(evaluate(source, resolved, now).missed)
