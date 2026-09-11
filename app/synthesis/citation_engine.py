from typing import Dict, Any

class CitationEngine:
    @staticmethod
    def generate_apa_7th(source: Dict[str, Any]) -> str:
        """Dynamically formats normalized source dictionaries into strict APA 7th Edition layouts."""
        authors_list = source.get("authors", [])
        year = source.get("year", "n.d.")
        title = source.get("title", "Untitled Work")
        venue = source.get("venue", "Unknown Source")
        url = source.get("url", "")

        if not authors_list:
            author_str = "Unknown Author"
        elif len(authors_list) == 1:
            author_str = authors_list[0]
        elif len(authors_list) == 2:
            author_str = f"{authors_list[0]} & {authors_list[1]}"
        else:
            author_str = f"{authors_list[0]}, et al."

        if source.get("domain") == "legal":
            return f"{title}, {venue} ({author_str}, {year}). {url}".strip()
        return f"{author_str} ({year}). *{title}*. {venue}. {url}".strip()

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
