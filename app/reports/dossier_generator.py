import os
import re
from typing import List, Any, Optional
from dotenv import load_dotenv
from models.research_dossier import ResearchDossier
from app.research.publication_quality import PublicationQualityGate
from app.research.spelling import normalize_topic_spelling
from app.synthesis.providers import (
    SynthesisProviderRegistry,
    SynthesisProviderError,
    SynthesisUnavailableError,
    DegradationLogger,
)


class DossierGenerator:
    def __init__(self, provider_registry: Optional[SynthesisProviderRegistry] = None):
        load_dotenv()
        self.provider_registry = provider_registry or SynthesisProviderRegistry()
        self.quality_gate = PublicationQualityGate()
        # Maintain client property for backward compatibility
        primary = self.provider_registry.get_primary_provider()
        self.client = getattr(primary, "client", None)

    def generate(self, query: str, included_sources: list = None,
                 excluded_sources: list = None, evidence_summary: list = None,
                 themes: list = None, scoring_summary: list = None,
                 decision_rationales: list = None, **kwargs) -> ResearchDossier:
        dossier = self.generate_comprehensive_dossier(query=query, included_sources=included_sources or [], **kwargs)
        if excluded_sources is not None:
            dossier.excluded_sources = excluded_sources
        if evidence_summary is not None:
            dossier.evidence_summary = evidence_summary
        if themes is not None:
            dossier.themes = themes
        if scoring_summary is not None:
            dossier.scoring_summary = scoring_summary
        if decision_rationales is not None:
            dossier.decision_rationales = decision_rationales
        return dossier

    def generate_comprehensive_dossier(self, query: str, included_sources: list,
                                       custom_prompt: str = None,
                                       domain: str = "scholarly",
                                       report_type: str = "proposal") -> ResearchDossier:
        """Assembles, analyzes, and synthesizes structured research dossiers using refined prompts."""
        query = normalize_topic_spelling(query)
        dossier = ResearchDossier(query=query)
        dossier.included_sources = included_sources
        dossier.provenance = [
            {
                "source_id": self._source_value(src, "uid", self._source_value(src, "doi", f"source_{index}")),
                "title": self._source_value(src, "title", "Unknown Title"),
                "evidence_type": "abstract" if self._source_value(src, "abstract", "") else "metadata_only",
            }
            for index, src in enumerate(included_sources, 1)
        ]
        dossier.abstract = ""

        if not included_sources:
            dossier.evidence_summary = [
                "No eligible academic sources were available; synthesis was not generated."
            ]
            dossier.quality_report = self.quality_gate.validate_dossier(
                dossier, included_sources, report_type=report_type
            )
            return dossier

        source_context = ""
        for i, src in enumerate(included_sources, 1):
            title = self._source_value(src, "title", "Unknown Title")
            abstract = self._source_value(src, "abstract", "No Abstract Available")
            year = self._source_value(src, "year", "N/A")
            source_context += f"\n[Source {i}] Title: {title} ({year})\nAbstract: {abstract}\n"

        # Base system prompt template instructions
        base_prompt = self.quality_gate.build_generation_contract(query, custom_prompt, domain)
        base_prompt += f"\n\nSource Material for Extraction:\n{source_context}\n\n"

        if self.client and hasattr(self.client, "models") and hasattr(self.client.models, "generate_content"):
            # Compatibility with tests patching generator.client.models
            try:
                response = self.client.models.generate_content(
                    model='gemini-3.6-flash',
                    contents=base_prompt
                )
                text = getattr(response, "text", "") or ""
                self._parse_synthesis_payload(text, dossier)
            except Exception as e:
                DegradationLogger.log_degradation("gemini", "client_error", str(e))
                raise SynthesisProviderError(f"Dossier synthesis error: {e}", provider="gemini", raw_error=e)
        else:
            try:
                text, provider_name = self.provider_registry.generate_with_failover(base_prompt)
                self._parse_synthesis_payload(text, dossier)
            except SynthesisProviderError:
                raise
            except Exception as e:
                DegradationLogger.log_degradation("unknown", "unexpected_error", str(e))
                raise SynthesisProviderError(f"Dossier synthesis error: {e}", raw_error=e)

        quality_report = self.quality_gate.validate_dossier(
            dossier, included_sources, report_type=report_type
        )
        dossier.quality_report = quality_report
        return dossier

    def _parse_synthesis_payload(self, text: str, dossier: ResearchDossier):
        """Helper to break raw model string responses into explicit structural dossier lists."""
        current_section = None
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue

            # Simple header matching state switches
            section_match = re.match(
                r"^\s*(?:#{1,6}\s*)?(ABSTRACT|KEY THEMES|CONTRADICTIONS|RESEARCH GAPS|RESEARCH AREAS|OPPORTUNITY AREAS|PROBLEMS TO SOLVE)\b\s*:?\s*(.*)$",
                line,
                flags=re.I,
            )
            if section_match:
                section_name, section_content = section_match.groups()
                section_key = section_name.upper()
                current_section = {
                    "ABSTRACT": "abstract",
                    "KEY THEMES": "themes",
                    "CONTRADICTIONS": "contradictions",
                    "RESEARCH GAPS": "gaps",
                    "RESEARCH AREAS": "research_areas",
                    "OPPORTUNITY AREAS": "opportunities",
                    "PROBLEMS TO SOLVE": "problems",
                }[section_key]
                line = section_content.strip()
                if not line:
                    continue

            # Populate lines clean of markdown list characters.
            clean_line = line.lstrip("-*•1234567890. ").strip()
            if clean_line and current_section:
                if current_section == "abstract":
                    dossier.abstract = f"{dossier.abstract} {clean_line}".strip()
                elif current_section == "themes":
                    dossier.themes.append(clean_line)
                elif current_section == "contradictions":
                    dossier.contradictions.append(clean_line)
                elif current_section == "gaps":
                    dossier.research_gaps.append(clean_line)
                elif current_section == "research_areas":
                    dossier.research_areas.append(clean_line)
                elif current_section == "opportunities":
                    dossier.opportunity_areas.append(clean_line)
                elif current_section == "problems":
                    dossier.problems_to_solve.append(clean_line)

    @staticmethod
    def _source_value(source: Any, key: str, default: Any = "") -> Any:
        if isinstance(source, dict):
            value = source.get(key, default)
        else:
            value = getattr(source, key, default)
        if isinstance(value, dict):
            return " ".join(str(part) for part in value.keys())
        if isinstance(value, list):
            return ", ".join(str(item) for item in value)
        return value if value not in (None, "") else default
