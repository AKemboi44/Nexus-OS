from __future__ import annotations

import os
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List


class PublicationQualityGate:
    """Enforces evidence-grounded, publication-style quality checks for research synthesis."""

    REQUIRED_SECTIONS = [
        "ABSTRACT",
        "KEY THEMES",
        "CONTRADICTIONS",
        "RESEARCH GAPS",
        "OPPORTUNITY AREAS",
        "PROBLEMS TO SOLVE",
    ]
    DEFAULT_THRESHOLDS = {
        "proposal": 0.85,
        "full_starter": 0.90,
    }

    @staticmethod
    def _normalize_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, tuple, set)):
            return " ".join(str(item) for item in value)
        return str(value)

    @classmethod
    def threshold_for(cls, report_type: str = "proposal") -> float:
        normalized = (report_type or "proposal").strip().lower()
        default = cls.DEFAULT_THRESHOLDS.get(normalized, cls.DEFAULT_THRESHOLDS["proposal"])
        env_name = f"NEXUS_QUALITY_THRESHOLD_{normalized.upper()}"
        raw_value = os.getenv(env_name)
        if raw_value is None:
            return default
        try:
            value = float(raw_value)
        except ValueError:
            return default
        return min(max(value, 0.0), 1.0)

    @staticmethod
    def _source_value(source: Any, key: str, default: Any = "") -> Any:
        if isinstance(source, dict):
            return source.get(key, default)
        return getattr(source, key, default)

    @staticmethod
    def _normalize_title(title: Any) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(title or "").lower()).strip()

    @staticmethod
    def _normalize_doi(value: Any) -> str:
        text = str(value or "").strip().lower()
        text = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", text)
        text = text.removeprefix("doi:")
        return text.rstrip(" .;,)")

    def validate_citations(self, sources: List[Any]) -> Dict[str, Any]:
        """Checks DOI consistency and title agreement across duplicate source records."""
        issues: List[str] = []
        warnings: List[str] = []
        records = []
        by_doi: Dict[str, List[Dict[str, str]]] = {}

        for index, source in enumerate(sources or [], start=1):
            title = self._normalize_text(self._source_value(source, "title"))
            doi = self._normalize_doi(
                self._source_value(source, "doi")
                or self._source_value(source, "DOI")
                or self._source_value(source, "url")
            )
            if doi and not doi.startswith("10."):
                doi = ""
            record = {"index": str(index), "title": title, "doi": doi}
            records.append(record)
            if doi:
                by_doi.setdefault(doi, []).append(record)

        for doi, matches in by_doi.items():
            if len(matches) < 2:
                continue
            base_title = self._normalize_title(matches[0]["title"])
            for match in matches[1:]:
                similarity = SequenceMatcher(
                    None, base_title, self._normalize_title(match["title"])
                ).ratio()
                if similarity < 0.85:
                    issues.append(
                        f"DOI {doi} maps to conflicting titles in sources "
                        f"{matches[0]['index']} and {match['index']}."
                    )

        for record in records:
            if record["title"] and not record["doi"]:
                warnings.append(
                    f"Source {record['index']} has no DOI or DOI URL; title-only citation validation applied."
                )

        valid_records = len(records) - sum(
            1 for issue in issues if "conflicting titles" in issue
        )
        score = round(max(0.0, valid_records / len(records)), 3) if records else 0.0
        return {
            "score": score,
            "issues": issues,
            "warnings": warnings,
            "checked": len(records),
        }

    def build_generation_contract(self, query: str, custom_prompt: str = None, domain: str = "scholarly") -> str:
        contract = (
            f"You are the Lead Scientific Synthesis Intelligence for Nexus Research AI. "
            f"Create a publication-quality {domain} synthesis for the research question: '{query}'.\n\n"
            "Hard rules:\n"
            "1. Ground every major claim in the supplied evidence; never invent studies, methods, results, or citations.\n"
            "2. Use concise, evidence-based bullet points only.\n"
            "3. Write in a formal academic tone.\n"
            "4. Keep the structure exact and do not add conversational filler.\n"
            "5. Separate consensus findings, contradictions, and research gaps explicitly.\n"
            "6. If the evidence is weak or inconsistent, say so and avoid overclaiming.\n\n"
            "7. Paraphrase the evidence in an original researcher voice; never copy source wording or use quotation marks.\n"
            "8. Explain how studies agree, disagree, extend one another, or leave a limitation unresolved.\n"
            "9. Use complete sentences only; never use ellipses or truncated phrases.\n\n"
            "Exact structure required:\n"
            "### ABSTRACT\n"
            "- Write a publication-style abstract of 150 to 200 words.\n"
            "- Include the problem context, review objective, evidence or methods, main synthesized findings, "
            "trade-offs or limitations, and practical/research implications.\n"
            "- Use connected prose rather than a list. Do not insert citations into the abstract.\n"
            "- End with exactly one line formatted as: Keywords: term one, term two, term three, term four, term five.\n\n"
            "### KEY THEMES\n- 3 to 6 bullet points synthesizing recurring patterns.\n\n"
            "### CONTRADICTIONS\n- 2 to 5 explicit disagreements or boundary conditions.\n\n"
            "### RESEARCH GAPS\n- 2 to 5 specific unresolved methodological or evidence gaps.\n\n"
            "### OPPORTUNITY AREAS\n- 2 to 5 downstream research or commercial opportunities.\n\n"
            "### PROBLEMS TO SOLVE\n- 2 to 5 concrete problems future research should address.\n\n"
            "Quality control: cite sources by author-year when possible, avoid unsupported claims, and suppress speculation unless clearly labeled as a gap or opportunity."
        )
        if custom_prompt:
            contract += f"\n\nCRITICAL USER DIRECTIVE:\n{custom_prompt}\n"
        return contract

    def evaluate_sources(self, sources: List[Any]) -> Dict[str, Any]:
        if not sources:
            return {
                "score": 0.0,
                "issues": ["No evidence sources available for the publication-quality review."],
            }

        issues: List[str] = []
        scores: List[float] = []
        seen_titles = set()
        duplicate_titles: List[str] = []

        for index, source in enumerate(sources, start=1):
            title = self._normalize_text(source.get("title") if isinstance(source, dict) else getattr(source, "title", ""))
            abstract = self._normalize_text(source.get("abstract") if isinstance(source, dict) else getattr(source, "abstract", ""))
            year = self._normalize_text(source.get("year") if isinstance(source, dict) else getattr(source, "year", ""))
            authors = self._normalize_text(source.get("authors") if isinstance(source, dict) else getattr(source, "authors", ""))

            if not title:
                issues.append(f"Source {index} is missing a title.")
            if not year:
                issues.append(f"Source {index} is missing a publication year.")
            if len(abstract.split()) < 25:
                issues.append(f"Source {index} has insufficient abstract text for grounded synthesis.")
            if not authors:
                issues.append(f"Source {index} is missing author metadata.")

            key = title.lower().strip()
            if key and key in seen_titles:
                duplicate_titles.append(title)
            else:
                seen_titles.add(key)

            score = 0.0
            if title:
                score += 0.25
            if abstract:
                score += 0.25
            if year:
                score += 0.15
            if authors:
                score += 0.15
            if isinstance(source, dict) and source.get("is_peer_reviewed") is True:
                score += 0.1
            if isinstance(source, dict) and source.get("url"):
                score += 0.1
            scores.append(min(score, 1.0))

        if duplicate_titles:
            issues.append("Duplicate source titles detected: " + "; ".join(duplicate_titles[:3]))

        source_score = round(sum(scores) / len(scores), 3) if scores else 0.0
        if source_score < 0.8:
            issues.append("Source catalog does not meet the minimum publication-quality threshold.")

        return {"score": source_score, "issues": issues}

    def validate_dossier(
        self,
        dossier: Any,
        sources: List[Any],
        min_score: float = None,
        report_type: str = "proposal",
    ) -> Dict[str, Any]:
        sections = {
            "abstract": bool(getattr(dossier, "abstract", "") or getattr(dossier, "evidence_summary", None)),
            "themes": bool(getattr(dossier, "themes", [])),
            "contradictions": bool(getattr(dossier, "contradictions", [])),
            "gaps": bool(getattr(dossier, "research_gaps", [])),
            "opportunities": bool(getattr(dossier, "opportunity_areas", [])),
            "problems": bool(getattr(dossier, "problems_to_solve", [])),
        }

        missing_sections = [name for name, present in sections.items() if not present]

        section_score = 1.0 - (len(missing_sections) * 0.15)
        source_report = self.evaluate_sources(sources)
        citation_report = self.validate_citations(sources)
        score = round(
            (section_score + source_report["score"] + citation_report["score"]) / 3.0,
            3,
        )
        threshold = (
            self.threshold_for(report_type)
            if min_score is None
            else min(max(min_score, 0.0), 1.0)
        )
        passed = score >= threshold and not missing_sections and not citation_report["issues"]

        return {
            "score": score,
            "passed": passed,
            "threshold": threshold,
            "report_type": report_type,
            "missing_sections": missing_sections,
            "source_issues": source_report["issues"],
            "citation_report": citation_report,
            "recommendations": self._quality_recommendations(
                missing_sections,
                source_report["issues"] + citation_report["issues"],
            ),
        }

    @staticmethod
    def _quality_recommendations(missing_sections: List[str], issues: List[str]) -> List[str]:
        recommendations = []
        if missing_sections:
            recommendations.append("Add the missing evidence sections required for an academically defensible synthesis.")
        if any("insufficient abstract" in issue.lower() for issue in issues):
            recommendations.append("Increase abstract coverage by selecting higher-quality sources with fuller descriptions.")
        if any("duplicate" in issue.lower() for issue in issues):
            recommendations.append("Deduplicate the source list before synthesis to prevent repeated claims.")
        if not recommendations:
            recommendations.append("Maintain the evidence-first workflow and continue the reviewer/editor quality gate.")
        return recommendations
