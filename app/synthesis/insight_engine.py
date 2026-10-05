import os
import sys
from dotenv import load_dotenv
from typing import List, Dict  # <-- Restores the missing type definitions

# Ensure local project architecture paths map cleanly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from models.research_insight import ResearchInsight

try:
    from google import genai

    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


STATUS_AI = "ai"
STATUS_NO_EVIDENCE = "no_evidence"
STATUS_TEMPLATE = "template"
MAX_ABSTRACT_CHARS = 1200
_NO_TEXT = {"", "no description", "no description.", "n/a", "none", "empty"}


class InsightEngine:
    def __init__(self, evidence_store=None):
        self.evidence_store = evidence_store
        self.client = None

        # 1. Force fetch current workspace environment properties
        load_dotenv()

        # 2. Extract standard API keys defined in your local configurations
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

        # 3. Securely instantiate the modern Google Gen AI client wrapper
        if api_key and HAS_GENAI:
            try:
                self.client = genai.Client(api_key=api_key)
                print("Gemini Client (google-genai) successfully initialized.")
            except Exception as e:
                print(f"Client constructor processing error: {e}")
        else:
            print("Warning: GEMINI_API_KEY / GOOGLE_API_KEY missing from environment scope.")

    @staticmethod
    def usable_evidence(evidence_items) -> List[tuple]:
        """(title, abstract) for every item that has abstract text to summarize.

        Accepts both block shapes in use: {title, abstract} and the pipeline's {id, content}.
        """
        usable = []
        for item in evidence_items or []:
            if isinstance(item, dict):
                title, text = item.get("title"), item.get("abstract") or item.get("content")
            else:
                title, text = getattr(item, "title", None), getattr(item, "abstract", None) or getattr(item, "content", None)
            text = str(text or "").strip()
            if text.casefold() in _NO_TEXT:
                continue
            usable.append((str(title or "Untitled source").strip(), text[:MAX_ABSTRACT_CHARS]))
        return usable

    def generate_insight(self, theme: str, evidence_items: List[Dict]) -> ResearchInsight:
        usable = self.usable_evidence(evidence_items)
        if not usable:
            # Nothing to summarize: do not ask the model (it can only refuse) and do not invent findings.
            return ResearchInsight(
                theme=theme,
                insight=f"No summary was generated for '{theme}': none of the retrieved sources included an abstract to summarize.",
                supported_by=evidence_items, status=STATUS_NO_EVIDENCE,
            )
        unavailable = ResearchInsight(
            theme=theme,
            insight=f"No AI summary was generated for '{theme}': the AI service was unavailable for this scan.",
            supported_by=evidence_items, status=STATUS_TEMPLATE,
        )
        if not self.client:
            return unavailable

        evidence_str = "".join(
            f"\n[{i}] Title: {title}\nAbstract: {abstract}\n" for i, (title, abstract) in enumerate(usable, 1)
        )
        prompt = (
            f"You are a research core platform. Synthesize a granular, evidence-based research insight "
            f"for the following theme based strictly on the provided evidence blocks.\n\n"
            f"Theme: {theme}\n"
            f"Evidence Blocks:\n{evidence_str}\n"
            f"Synthesize an insightful research summary:"
        )
        try:
            # Targeted to the modern gemini-3.6-flash model as required by the API server
            response = self.client.models.generate_content(model='gemini-3.6-flash', contents=prompt)
            text = str(response.text or "").strip()
        except Exception as e:
            print(f"[InsightEngine API Error]: {e}")
            return unavailable
        if not text:
            return unavailable
        return ResearchInsight(theme=theme, insight=text, supported_by=evidence_items, status=STATUS_AI)
