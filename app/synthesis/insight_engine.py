import os
import sys
from typing import List, Dict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from models.research_insight import ResearchInsight

import google.generativeai as genai

try:
    from google.colab import userdata

    HAS_COLAB = True
except ImportError:
    HAS_COLAB = False


class InsightEngine:
    def __init__(self):
        self.gemini_model = None
        if HAS_COLAB:
            try:
                api_key = userdata.get('GOOGLE_API_KEY')
                genai.configure(api_key=api_key)
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
            except Exception as e:
                print(f"API Initialization failed: {e}")

    def generate_insight(self, theme: str, evidence: List[Dict]) -> ResearchInsight:
        evidence_str = "\n".join([f"- {e.get('content', 'No content')}" for e in evidence])
        if not self.gemini_model:
            text = f"Synthesized Insight for '{theme}': Analysis of {len(evidence)} evidence blocks suggests a significant trend towards digital adoption."
        else:
            prompt = f"Theme: {theme}\nEvidence:\n{evidence_str}\n\nTask: Synthesize a single powerful research insight from this evidence."
            try:
                text = self.gemini_model.generate_content(prompt).text.strip()
            except:
                text = f"Fallback insight for {theme}."

        return ResearchInsight(theme=theme, insight=text, supported_by=evidence)
