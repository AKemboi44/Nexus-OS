from typing import List, Dict

class ResearchInsight:
    def __init__(self, theme: str, insight: str, supported_by: List[Dict]):
        self.theme = theme
        self.insight = insight
        self.supported_by = supported_by

    def __repr__(self):
        return f"ResearchInsight(theme='{self.theme}', insight='{self.insight[:50]}...')"

    def to_dict(self):
        return {
            'theme': self.theme,
            'insight': self.insight,
            'supported_by': self.supported_by
        }
