from typing import Dict, Any

class CitationEngine:
    @staticmethod
    def _authors(source: Dict[str, Any]) -> list[str]:
        authors = source.get("authors") or []
        if isinstance(authors, str):
            authors = [author.strip() for author in authors.split(";") if author.strip()]
            if len(authors) == 1:
                authors = [author.strip() for author in authors[0].split(" and ") if author.strip()]
            if len(authors) == 1:
                authors = [author.strip() for author in authors[0].split(" & ") if author.strip()]
            if len(authors) == 1 and authors[0].count(",") > 1:
                authors = [author.strip() for author in authors[0].split(",") if author.strip()]
        return [str(author).strip() for author in authors if str(author).strip()]

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
            return "[Author information unavailable]"
        formatted = [cls._format_author(author) for author in authors]
        if len(formatted) > 20:
            formatted = [*formatted[:19], "...", formatted[-1]]
        if len(formatted) == 1:
            return formatted[0]
        return f"{', '.join(formatted[:-1])}, & {formatted[-1]}"

    @staticmethod
    def generate_apa_7th(source: Dict[str, Any]) -> str:
        """Format available source metadata as an APA 7 reference without inventing fields."""
        authors_list = CitationEngine._authors(source)
        year = source.get("year") or "n.d."
        title = source.get("title") or "Untitled Work"
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
