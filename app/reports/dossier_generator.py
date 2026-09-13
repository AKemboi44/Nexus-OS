import os
from typing import List, Any
from google import genai
from dotenv import load_dotenv
from models.research_dossier import ResearchDossier


class DossierGenerator:
    def __init__(self):
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=api_key) if api_key else None

    def generate_comprehensive_dossier(self, query: str, included_sources: list,
                                       custom_prompt: str = None,
                                       domain: str = "scholarly") -> ResearchDossier:
        """Assembles, analyzes, and synthesizes structured research dossiers using refined prompts."""
        dossier = ResearchDossier(query=query)
        dossier.included_sources = included_sources
        dossier.abstract = ""

        if not included_sources:
            dossier.evidence_summary = ["No academic sources available for structural synthesis mapping."]
            return dossier

        source_context = ""
        for i, src in enumerate(included_sources, 1):
            title = self._source_value(src, "title", "Unknown Title")
            abstract = self._source_value(src, "abstract", "No Abstract Available")
            year = self._source_value(src, "year", "N/A")
            source_context += f"\n[Source {i}] Title: {title} ({year})\nAbstract: {abstract}\n"

        if not self.client:
            dossier.abstract = (
                f"This evidence synthesis evaluates {query} using "
                f"{len(included_sources)} selected {domain} source(s)."
            )
            dossier.themes = [
                f"Evidence base: the selected literature addresses {query}."
            ]
            dossier.research_gaps = [
                "The available source set does not fully resolve the methods, populations, or contexts that remain under-studied."
            ]
            dossier.opportunity_areas = [
                "Future work can test the reported findings in broader settings with transparent, reproducible evaluation."
            ]
            return dossier

        # Base system prompt template instructions
        base_prompt = (
            f"You are the Lead Scientific Synthesis Intelligence of Nexus OS.\n"
            f"Perform an exhaustive, multi-dimensional {domain} evaluation for the query theme: '{query}'.\n"
            f"Source Material for Extraction:\n{source_context}\n\n"
        )

        # Inject user instruction dynamically if it's passed down from the loop input window
        if custom_prompt:
            base_prompt += f"CRITICAL USER DIRECTION OVERRIDE:\n{custom_prompt}\n\n"

        base_prompt += (
            f"Structure your synthesis response exactly across these five explicit markdown blocks. "
            f"Use one concise, evidence-grounded bullet for each distinct theme. Do not add conversational text:\n\n"
            f"### ABSTRACT\n- Write a concise abstract grounded only in the supplied sources.\n\n"
            f"### KEY THEMES\n- Identify overarching consensus vectors. Highlight country specific trends and regression types.\n\n"
            f"### CONTRADICTIONS\n- Extract empirical discrepancies or diverging operational conclusions among authors.\n\n"
            f"### RESEARCH GAPS\n- Pinpoint unaddressed methodologies or under-researched consumer demographic segments.\n\n"
            f"### OPPORTUNITY AREAS\n- Define downstream commercial opportunities or software incubation vectors.\n"
        )

        try:
            response = self.client.models.generate_content(
                model='gemini-3.6-flash',
                contents=base_prompt
            )
            self._parse_synthesis_payload(response.text, dossier)
        except Exception as e:
            print(f"[Dossier Generator Error]: {e}")
            dossier.evidence_summary = [f"Synthesis pipeline error: {str(e)}"]

        return dossier

    def _parse_synthesis_payload(self, text: str, dossier: ResearchDossier):
        """Helper to break raw model string responses into explicit structural dossier lists."""
        current_section = None
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue

            # Simple header matching state switches
            if "KEY THEMES" in line.upper():
                current_section = "themes"
                continue
            elif "ABSTRACT" in line.upper():
                current_section = "abstract"
                continue
            elif "CONTRADICTIONS" in line.upper():
                current_section = "contradictions"
                continue
            elif "RESEARCH GAPS" in line.upper():
                current_section = "gaps"
                continue
            elif "OPPORTUNITY AREAS" in line.upper():
                current_section = "opportunities"
                continue

            # Populate lines clean of markdown list characters
            clean_line = line.lstrip('-*•1234567890. ')
            if clean_line and current_section:
                if current_section == "abstract":
                    dossier.abstract = f"{dossier.abstract} {clean_line}".strip()
                elif current_section == "themes":
                    dossier.themes.append(clean_line)
                elif current_section == "contradictions":
                    dossier.contradictions.append(clean_line)
                elif current_section == "gaps":
                    dossier.research_gaps.append(clean_line)
                elif current_section == "opportunities":
                    dossier.opportunity_areas.append(clean_line)

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
