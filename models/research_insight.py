from typing import List, Dict

class ResearchInsight:
    # "ai": written by the model from the supplied abstracts; "no_evidence": none had text to summarize;
    # "template": the model was unavailable or returned nothing. Only "ai" text is a real synthesis.
    def __init__(self, theme: str, insight: str, supported_by: List[Dict], status: str = "ai"):
        self.theme = theme
        self.insight = insight
        self.supported_by = supported_by
        self.status = status

    def __repr__(self):
        return f"ResearchInsight(theme='{self.theme}', insight='{self.insight[:50]}...')"

    def to_dict(self):
        return {
            'theme': self.theme,
            'insight': self.insight,
            'supported_by': self.supported_by,
            'status': self.status
        }
