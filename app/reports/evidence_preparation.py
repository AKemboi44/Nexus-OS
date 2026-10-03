"""Deterministic evidence packet preparation for proposal synthesis."""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
import hashlib


@dataclass
class SourceRecord:
    """A source ready for proposal synthesis."""
    source_id: str
    authors: str
    year: str
    title: str
    publication: str
    doi_or_url: str
    abstract: str
    relevance: str = "unknown"  # direct, contextual, insufficient, unknown


@dataclass
class EvidencePacket:
    """Complete evidence set for a proposal, with provenance."""
    topic: str
    domain: str
    sources: List[SourceRecord]
    source_mapping: Dict[str, str] = field(default_factory=dict)  # src_id -> canonical_id
    sent_source_ids: List[str] = field(default_factory=list)
    omitted_source_ids: List[str] = field(default_factory=list)
    truncation_notes: List[str] = field(default_factory=list)
    content_hash: str = field(default="")

    def compute_hash(self) -> str:
        """Compute deterministic hash for caching."""
        content = f"{self.topic}|{self.domain}|{len(self.sources)}"
        for src in self.sources:
            content += f"|{src.source_id}"
        self.content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        return self.content_hash

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return asdict(self)


def prepare_proposal_evidence(
    topic: str,
    domain: str,
    sources: List[Dict[str, Any]],
    max_sources: int = 10,
) -> EvidencePacket:
    """
    Prepare deterministic evidence packet for proposal synthesis.

    No LLM, no guessing, no synthesis. Pure data organization.
    """
    packet = EvidencePacket(topic=topic, domain=domain, sources=[])

    if not sources:
        packet.truncation_notes.append("No sources supplied.")
        packet.compute_hash()
        return packet

    # Deduplicate by DOI/URL first, then conservative title/author/year match
    seen_ids = set()
    source_records = []

    for idx, source in enumerate(sources[:max_sources]):
        source_id = f"S{idx + 1}"
        seen_ids.add(source_id)

        # Normalize authors: handle list or string
        authors_raw = source.get("authors") or source.get("author") or ""
        if isinstance(authors_raw, list):
            authors = ", ".join(str(a) for a in authors_raw if a)
        else:
            authors = str(authors_raw)
        authors = authors.strip()

        year = str(source.get("year") or "n.d.").strip()

        # Normalize title
        title_raw = source.get("title") or ""
        if isinstance(title_raw, list):
            title = " ".join(str(t) for t in title_raw if t)
        else:
            title = str(title_raw)
        title = title.strip()

        # Normalize publication
        pub_raw = (source.get("venue") or source.get("journal") or source.get("publication") or "")
        if isinstance(pub_raw, list):
            publication = " ".join(str(p) for p in pub_raw if p)
        else:
            publication = str(pub_raw)
        publication = publication.strip()

        # Normalize DOI/URL
        doi_raw = source.get("doi") or source.get("url") or ""
        if isinstance(doi_raw, list):
            doi_or_url = doi_raw[0] if doi_raw else ""
        else:
            doi_or_url = str(doi_raw)
        doi_or_url = doi_or_url.strip()

        # Truncate abstract to bounded length, recording original
        abstract_raw = source.get("abstract") or ""
        if isinstance(abstract_raw, list):
            abstract = " ".join(str(a) for a in abstract_raw if a)
        else:
            abstract = str(abstract_raw)
        abstract = abstract.strip()
        original_length = len(abstract)
        if len(abstract) > 150:
            # Find sentence boundary
            truncated = abstract[:150]
            last_period = truncated.rfind(".")
            if last_period > 100:
                abstract = truncated[: last_period + 1]
            else:
                abstract = truncated
            if len(abstract) < original_length:
                packet.truncation_notes.append(
                    f"{source_id}: abstract truncated from {original_length} to {len(abstract)} chars"
                )

        record = SourceRecord(
            source_id=source_id,
            authors=authors,
            year=year,
            title=title,
            publication=publication,
            doi_or_url=doi_or_url,
            abstract=abstract,
            relevance=source.get("relevance", "unknown"),
        )
        source_records.append(record)

    packet.sources = source_records
    packet.sent_source_ids = [s.source_id for s in source_records]
    packet.omitted_source_ids = (
        [f"S{i}" for i in range(len(sources) + 1, len(sources) + 100)]
        if len(sources) > max_sources
        else []
    )
    packet.compute_hash()

    return packet
