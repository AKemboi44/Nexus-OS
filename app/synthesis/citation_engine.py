import re
from typing import Dict, Any
from urllib.parse import urlsplit


class CitationEngine:
    INVALID_METADATA = {
        "",
        "n/a",
        "na",
        "none",
        "unknown",
        "unknown author",
        "unknown contributor",
        "unknown source",
        "untitled",
        "untitled work",
    }

    @classmethod
    def is_referenceable(cls, source: Dict[str, Any]) -> bool:
        authors = cls._authors(source)
        valid_authors = [
            author for author in authors
            if not cls._is_missing_metadata(author)
        ]
        title = str(source.get("title") or "").strip()
        if not valid_authors or cls._is_missing_metadata(title):
            return False

        year = str(source.get("year") or "").strip()
        if not year.isdigit() or len(year) != 4:
            return False

        venue = str(source.get("venue") or source.get("journal") or "").strip()
        valid_venue = not cls._is_missing_metadata(venue)
        doi = str(source.get("doi") or "").strip()
        url = str(source.get("url") or "").strip()
        valid_doi = bool(re.fullmatch(r"10\.\d{4,9}/\S+", doi.strip())) if doi else False
        parsed_url = urlsplit(url) if url else None
        valid_url = bool(
            parsed_url
            and parsed_url.scheme.lower() in {"http", "https"}
            and parsed_url.netloc
        )
        valid_identifier = valid_doi or valid_url
        return valid_venue or valid_identifier

    @classmethod
    def _is_missing_metadata(cls, value: str) -> bool:
        normalized = str(value or "").casefold().strip(" []().")
        return (
            normalized in cls.INVALID_METADATA
            or "unavailable" in normalized
            or normalized.startswith(("unknown", "untitled", "not provided", "not available"))
        )

    @classmethod
    def referenceable_sources(cls, sources):
        return [
            source for source in (sources or [])
            if cls.is_referenceable(
                source if isinstance(source, dict) else vars(source)
            )
        ]

    @classmethod
    def _authors(cls, source: Dict[str, Any]) -> list[str]:
        authors = source.get("authors") or []
        if isinstance(authors, str):
            authors = [author.strip() for author in authors.split(";") if author.strip()]
            if len(authors) == 1:
                authors = [author.strip() for author in authors[0].split(" and ") if author.strip()]
            if len(authors) == 1:
                authors = [author.strip() for author in authors[0].split(" & ") if author.strip()]
            if len(authors) == 1 and authors[0].count(",") > 1:
                authors = [author.strip() for author in authors[0].split(",") if author.strip()]
        return [
            str(author).strip()
            for author in authors
            if str(author).strip() and not cls._is_missing_metadata(author)
        ]

    @staticmethod
    def _format_author(author: str) -> str:
        pieces = [piece.strip() for piece in author.split(",", 1)]
        if len(pieces) == 2:
            surname, given_names = pieces
        else:
            name_parts = author.split()
            if len(name_parts) == 1:
                return name_parts[0].title()
            surname = name_parts[-1]
            given_names = " ".join(name_parts[:-1])
        if surname.isupper():
            surname = surname.title()
        initials = " ".join(
            f"{part[0].upper()}." for part in given_names.split() if part
        )
        return f"{surname}, {initials}".strip()

    @classmethod
    def _format_authors(cls, authors: list[str]) -> str:
        if not authors:
            return ""
        formatted = [cls._format_author(author) for author in authors]
        if len(formatted) > 20:
            formatted = [*formatted[:19], "...", formatted[-1]]
        if len(formatted) == 1:
            return formatted[0]
        return f"{', '.join(formatted[:-1])}, & {formatted[-1]}"

    @staticmethod
    def generate_apa_7th(source: Dict[str, Any]) -> str:
        """Format available source metadata as an APA 7 reference without inventing fields."""
        if not CitationEngine.is_referenceable(source):
            return ""
        authors_list = CitationEngine._authors(source)
        year = str(source["year"]).strip()
        title = str(source["title"]).strip()
        venue = source.get("venue") or source.get("journal") or ""
        volume = source.get("volume")
        issue = source.get("issue")
        pages = source.get("pages") or source.get("page_range")
        url = source.get("doi") or source.get("url") or ""
        author_str = CitationEngine._format_authors(authors_list)

        if source.get("domain") == "legal":
            return f"{title}, {venue} ({author_str}, {year}). {url}".strip()

        reference = f"{author_str} ({year}). {title}."
        if venue:
            reference += f" {venue}"
            if volume:
                reference += f", {volume}"
                if issue:
                    reference += f"({issue})"
            if pages:
                reference += f", {pages}"
            reference += "."
        if url:
            url = str(url).strip()
            if url.lower().startswith("doi:"):
                url = url[4:].strip()
            if url and not url.lower().startswith(("http://", "https://")):
                url = f"https://doi.org/{url}"
            reference += f" {url}"
        return reference.strip()

    @staticmethod
    def generate_bluebook(source: Dict[str, Any]) -> str:
        """
        Formats legal case records into the strict Bluebook legal standard:
        Case Name, Volume Reporter FirstPage (Court Year).
        """
        title = source.get("title", "Case Name Unknown")
        venue = source.get("venue", "F. Supp. 2d")  # Maps as legal reporter column track
        year = source.get("year", "n.d.")
        authors_list = source.get("authors", [])
        court_info = authors_list[0] if authors_list else "Court Unknown"
        url = source.get("url", "")

        # Bluebook structures italicize or underline case names exclusively
        return f"*{title}*, {venue} ({court_info} {year}). {url}".strip()
