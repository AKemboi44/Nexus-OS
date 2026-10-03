"""Deterministic research metadata extraction from sources (no LLM)."""

import re
from typing import List, Dict, Any


def extract_research_metadata(sources: List[Dict[str, Any]], topic: str) -> Dict[str, Any]:
    """
    Extract themes, gaps, and opportunities from source abstracts deterministically.
    No LLM calls - uses keyword patterns and linguistic heuristics.
    """
    
    # Combine all abstracts
    all_text = " ".join([
        s.get("abstract", "") or s.get("summary", "") or ""
        for s in sources
    ]).lower()
    
    # Extract themes using keyword clustering
    themes = _extract_themes(all_text, sources, topic)
    
    # Extract research gaps using gap-indicator patterns
    gaps = _extract_gaps(all_text)
    
    # Extract opportunities using opportunity-indicator patterns
    opportunities = _extract_opportunities(all_text)
    
    # Extract research areas from titles and abstracts
    research_areas = _extract_research_areas(sources, topic)
    
    return {
        "abstract": _extract_abstract_summary(sources),
        "themes": themes,
        "research_gaps": gaps,
        "opportunity_areas": opportunities,
        "research_areas": research_areas,
    }


def _extract_themes(text: str, sources: List[Dict], topic: str) -> List[str]:
    """Extract recurring themes from abstracts."""
    themes = set()
    
    # Common theme keywords in academic abstracts
    theme_patterns = [
        r"\b(machine learning|deep learning|neural network|artificial intelligence|ai)\b",
        r"\b(natural language processing|nlp|text analysis)\b",
        r"\b(data mining|big data|analytics|data science)\b",
        r"\b(optimization|efficient|performance|scalability)\b",
        r"\b(classification|regression|prediction|forecasting)\b",
        r"\b(cluster|grouping|segmentation|classification)\b",
        r"\b(model|framework|architecture|system)\b",
        r"\b(health|medical|clinical|diagnosis|treatment)\b",
        r"\b(social|network|community|collaboration)\b",
        r"\b(security|privacy|encryption|protection)\b",
        r"\b(sustainability|environment|green|ecological)\b",
        r"\b(learning|training|education|knowledge)\b",
    ]
    
    for pattern in theme_patterns:
        if re.search(pattern, text):
            # Extract the matched group and clean it
            match = re.search(pattern, text)
            if match:
                theme = match.group(0).strip()
                # Capitalize properly
                if theme.upper() in ["AI", "NLP"]:
                    themes.add(theme.upper())
                else:
                    themes.add(" ".join(word.capitalize() for word in theme.split()))
    
    # Add some structural themes based on abstracts
    if "method" in text or "approach" in text:
        themes.add("Methodological Innovation")
    if "empirical" in text or "experiment" in text:
        themes.add("Empirical Validation")
    if "systematic" in text or "comprehensive" in text:
        themes.add("Comprehensive Analysis")
    if "survey" in text or "review" in text:
        themes.add("Literature Review")
    
    # Return up to 5 unique themes
    return sorted(list(themes))[:5] if themes else ["Research Methodology", "Systematic Analysis"]


def _extract_gaps(text: str) -> List[str]:
    """Extract research gaps using gap-indicator patterns."""
    gaps = set()
    
    gap_patterns = [
        (r"(?:lack|insufficient|limited|gap|missing)\s+(?:in|of|evidence|research|understanding|knowledge|data|focus|attention)", "Limited Research Focus"),
        (r"(?:not\s+)(?:well|thoroughly|fully|completely)\s+(?:explored|studied|understood|investigated|examined)", "Underexplored Research Area"),
        (r"(?:remain|remains)\s+(?:unclear|unknown|unexplored|unanswered|open)", "Open Research Questions"),
        (r"(?:scalability|efficiency|performance)\s+(?:challenges|limitations|issues|problems)", "Scalability Challenges"),
        (r"(?:interpretability|explainability|transparency)\s+(?:challenges|limitations|issues|problems)", "Interpretability Concerns"),
        (r"(?:generalization|applicability)\s+(?:challenges|limitations|issues|across)", "Generalization Challenges"),
        (r"(?:integration|interoperability)\s+(?:challenges|issues|problems)", "Integration Challenges"),
    ]
    
    for pattern, gap_label in gap_patterns:
        if re.search(pattern, text):
            gaps.add(gap_label)
    
    # Return up to 3 gaps
    return sorted(list(gaps))[:3] if gaps else ["Limited Understanding of Key Mechanisms", "Scalability and Applicability Concerns"]


def _extract_opportunities(text: str) -> List[str]:
    """Extract research opportunities using opportunity-indicator patterns."""
    opportunities = set()
    
    opp_patterns = [
        (r"(?:potential|promising|opportunity|could|may|might)\s+(?:improve|enhance|advance|accelerate)", "Performance Improvement"),
        (r"(?:efficient|optimization|streamline|speed up|reduce|minimize)", "Efficiency Gains"),
        (r"(?:novel|innovative|new)\s+(?:approach|method|framework|technique)", "Novel Approaches"),
        (r"(?:practical|real-world|practical)\s+(?:application|deployment|implementation|use)", "Practical Application"),
        (r"(?:cost|budget|resource)-(?:effective|efficient|saving)", "Cost-Effectiveness"),
        (r"(?:cross-domain|interdisciplinary|transfer)\s+(?:learning|application)", "Cross-Domain Learning"),
        (r"(?:end-to-end|integrated|unified|holistic)", "Integrated Solutions"),
    ]
    
    for pattern, opp_label in opp_patterns:
        if re.search(pattern, text):
            opportunities.add(opp_label)
    
    # Return up to 3 opportunities
    return sorted(list(opportunities))[:3] if opportunities else ["Improved Methodologies", "Enhanced Efficiency and Scalability"]


def _extract_research_areas(sources: List[Dict], topic: str) -> List[str]:
    """Extract research areas from source titles and abstracts."""
    areas = set()
    
    # Use topic as base area
    areas.add(topic.split()[0].capitalize() if topic else "Research")
    
    # Look for common research area keywords
    domain_keywords = {
        "machine learning": ["ML", "AI/ML applications"],
        "healthcare": ["Clinical Applications", "Health Systems"],
        "education": ["Learning Systems", "Educational Technology"],
        "sustainability": ["Environmental Studies", "Green Technologies"],
        "security": ["Cybersecurity", "Data Protection"],
    }
    
    for source in sources[:5]:
        title = (source.get("title") or "").lower()
        abstract = (source.get("abstract") or "").lower()
        combined = f"{title} {abstract}"
        
        for domain, area_list in domain_keywords.items():
            if domain in combined:
                areas.update(area_list)
    
    # Return up to 3 areas
    return sorted(list(areas))[:3] if len(areas) > 1 else [topic, "Research Applications"]


def _extract_abstract_summary(sources: List[Dict]) -> str:
    """Create a summary abstract from the first source."""
    if not sources:
        return ""
    
    # Use first source's abstract as base
    first_abstract = sources[0].get("abstract") or sources[0].get("summary") or ""
    
    # Limit to first 2 sentences or 150 characters
    sentences = re.split(r'[.!?]+', first_abstract)
    summary = sentences[0].strip() if sentences else ""
    
    if len(summary) > 150:
        # Truncate at last space before 150 chars
        summary = summary[:150].rsplit(' ', 1)[0] + "..."
    
    return summary
