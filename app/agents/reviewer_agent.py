"""
Nexus Research AI v0.6.1 - Reviewer
"""
from .base_agent import BaseAgent
import json
import re
from typing import List, Dict

from app.research.publication_quality import PublicationQualityGate


class ReviewerAgent(BaseAgent):
    """
    The Reviewer (v0.6.1) specializes in Factual Grounding.
    It cross-references synthesized insights against source evidence.
    """
    def __init__(self):
        super().__init__(name='Reviewer', role='Factual Grounding Specialist')
        self.client = None
        self.has_llm = False
        self.quality_gate = PublicationQualityGate()

        try:
            import os
            from dotenv import load_dotenv
            from google import genai

            load_dotenv()
            api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')

            if api_key:
                self.client = genai.Client(api_key=api_key)
                self.has_llm = True
        except Exception:
            pass

    def execute(self, insight: str, evidence_items: list) -> dict:
        """Runs deterministic editorial checks and an optional grounded LLM review."""
        self.announce('Commencing factual grounding review...')
        source_report = self.quality_gate.evaluate_sources(evidence_items or [])
        citation_report = self.quality_gate.validate_citations(evidence_items or [])
        text = str(insight or "")
        required_headings = ("ABSTRACT", "KEY THEMES", "RESEARCH GAPS")
        missing_headings = [
            heading for heading in required_headings if heading not in text.upper()
        ]
        editorial_issues = []
        if len(text.split()) < 40:
            editorial_issues.append("Synthesis is too short for editorial review.")
        if missing_headings:
            editorial_issues.append(
                "Missing editorial sections: " + ", ".join(missing_headings) + "."
            )
        if re.search(r"\b(obviously|clearly|proves|always|never)\b", text, re.I):
            editorial_issues.append("Absolute or promotional language requires qualification.")

        llm_review = {}
        if self.has_llm and self.client and evidence_items and text:
            review_prompt = (
                "Act as a senior journal editor. Review the synthesis against the supplied sources. "
                "Return JSON only with keys score (0 to 1), unsupported_claims (array), "
                "style_issues (array), and recommendation (string). Do not invent citations.\n\n"
                f"SYNTHESIS:\n{text}\n\nSOURCES:\n{evidence_items}"
            )
            try:
                response = self.client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=review_prompt,
                )
                raw = response.text.strip()
                raw = raw.removeprefix("```json").removesuffix("```").strip()
                llm_review = json.loads(raw)
            except (ValueError, TypeError, AttributeError, json.JSONDecodeError):
                llm_review = {"score": 0.0, "recommendation": "Editorial review could not be parsed."}

        deterministic_score = (
            source_report["score"] * 0.45
            + citation_report["score"] * 0.25
            + (0.30 if not editorial_issues else max(0.0, 0.30 - 0.10 * len(editorial_issues)))
        )
        llm_score = min(max(float(llm_review.get("score", 0.0) or 0.0), 0.0), 1.0)
        score = round((deterministic_score * 0.7) + (llm_score * 0.3), 3) if llm_review else round(deterministic_score, 3)
        feedback_parts = ["Editorial and evidence review completed."]
        if editorial_issues:
            feedback_parts.extend(editorial_issues)
        if llm_review.get("recommendation"):
            feedback_parts.append(str(llm_review["recommendation"]))
        feedback = " ".join(feedback_parts)

        if source_report['issues']:
            feedback += ' Review warnings: ' + '; '.join(source_report['issues'][:2]) + '.'

        return {
            'status': 'reviewed',
            'score': score,
            'feedback': feedback,
            'quality_report': source_report,
            'citation_report': citation_report,
            'editorial_issues': editorial_issues,
            'llm_review': llm_review,
        }
