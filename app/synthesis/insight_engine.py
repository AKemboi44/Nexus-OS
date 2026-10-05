import logging
import os
import sys
from dotenv import load_dotenv
from typing import List, Dict, Optional

# Ensure local project architecture paths map cleanly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from models.research_insight import ResearchInsight
from app.synthesis.providers import SynthesisProviderRegistry

logger = logging.getLogger(__name__)


STATUS_AI = "ai"
STATUS_NO_EVIDENCE = "no_evidence"
STATUS_TEMPLATE = "template"
MAX_ABSTRACT_CHARS = 1200
_NO_TEXT = {"", "no description", "no description.", "n/a", "none", "empty"}


class InsightEngine:
    def __init__(self, evidence_store=None, registry: Optional[SynthesisProviderRegistry] = None):
        self.evidence_store = evidence_store
        # Claude first, Gemini as the backup, one retry on a transient error: the same providers the dossier uses.
        load_dotenv()
        self.registry = registry or SynthesisProviderRegistry()

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

    def generate_insight(self, theme: str, evidence_items: List[Dict], ledger=None) -> ResearchInsight:
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
            text, provider = self.registry.generate_with_failover(
                prompt, ledger=ledger, purpose="scan_summary", max_tokens=1200
            )
            text = str(text or "").strip()
        except Exception as e:
            logger.warning("Scan summary unavailable: %s", e)
            return unavailable
        if not text:
            logger.warning("Scan summary: the provider returned no text.")
            return unavailable
        return ResearchInsight(theme=theme, insight=text, supported_by=evidence_items, status=STATUS_AI)
