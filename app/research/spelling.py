import re
from typing import List, Dict, Set


# Common research, technology, and academic lexicon
_KNOWN_TERMS = {
    # AI / LLM / NLP / ML terms
    "token", "tokens", "tokenization", "tokenizer", "optimization", "optimizations", "optimizing", "optimized",
    "techniques", "technique", "resilient", "resilience", "cost", "costs", "control", "deployment", "deployments",
    "deploying", "artificial", "intelligence", "machine", "learning", "deep", "neural", "network", "networks",
    "transformer", "transformers", "attention", "prompt", "prompts", "compression", "pruning", "quantization",
    "inference", "latency", "throughput", "bandwidth", "memory", "cache", "kv", "context", "window",
    "embedding", "embeddings", "vector", "database", "retrieval", "augmented", "generation", "rag",
    "fine-tuning", "pretraining", "distillation", "alignment", "evaluation", "benchmark", "benchmarks",
    "scalability", "scalable", "distributed", "parallel", "gpu", "tpu", "hardware", "acceleration",
    "architecture", "architectures", "framework", "frameworks", "pipeline", "pipelines", "infrastructure",
    # Research / Academic terms
    "empirical", "methodology", "methodologies", "experiment", "experiments", "experimental",
    "literature", "systematic", "review", "synthesis", "qualitative", "quantitative",
    "analysis", "analyses", "analytical", "algorithm", "algorithms", "algorithmic",
    "parameter", "parameters", "parametric", "performance", "efficiency", "efficient",
    "accuracy", "precision", "recall", "metrics", "measurement", "validation", "verification",
    "hypothesis", "hypotheses", "investigation", "exploration", "comparative", "study", "studies",
    # Common English words often in topics
    "the", "of", "and", "in", "to", "for", "with", "on", "at", "from", "by", "about", "as",
    "into", "like", "through", "after", "over", "between", "out", "against", "during", "without",
    "before", "under", "around", "among", "using", "use", "used", "based", "driven", "aware",
    "scale", "large", "small", "high", "low", "fast", "slow", "multi", "cross", "open", "source",
}

# Explicit lookup for high-frequency domain misspellings / truncated words
_COMMON_TYPOS: Dict[str, str] = {
    "oken": "token",
    "okens": "tokens",
    "ptimization": "optimization",
    "ptimizations": "optimizations",
    "echnique": "technique",
    "echniques": "techniques",
    "esilient": "resilient",
    "eployment": "deployment",
    "eployments": "deployments",
    "omputation": "computation",
    "nference": "inference",
    "ransformer": "transformer",
    "ransformers": "transformers",
    "uantization": "quantization",
    "istillation": "distillation",
    "enchmark": "benchmark",
    "enchmarks": "benchmarks",
    "rchitecture": "architecture",
    "rchitectures": "architectures",
    "lgorithm": "algorithm",
    "lgorithms": "algorithms",
    "mispelling": "misspelling",
    "mispelled": "misspelled",
    "ommitted": "omitted",
}


def _levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def correct_word(word: str) -> str:
    """Correct a single word if it is a known misspelling or within small edit distance to a domain term."""
    if not word:
        return word

    is_upper = word.isupper()
    is_title = word.istitle()
    lower = word.casefold()

    # Direct common typo mapping
    if lower in _COMMON_TYPOS:
        corrected = _COMMON_TYPOS[lower]
        if is_upper:
            return corrected.upper()
        if is_title:
            return corrected.capitalize()
        return corrected

    # Already valid
    if lower in _KNOWN_TERMS:
        return word

    # Omitted leading letter check against known vocabulary
    for known in _KNOWN_TERMS:
        if len(known) == len(lower) + 1 and known[1:] == lower:
            if is_upper:
                return known.upper()
            if is_title:
                return known.capitalize()
            return known

    # Edit distance 1 for words of length >= 4
    if len(lower) >= 4:
        best_match = None
        best_dist = 2
        for known in _KNOWN_TERMS:
            if abs(len(known) - len(lower)) <= 1:
                dist = _levenshtein_distance(lower, known)
                if dist < best_dist:
                    best_dist = dist
                    best_match = known
        if best_dist <= 1 and best_match:
            if is_upper:
                return best_match.upper()
            if is_title:
                return best_match.capitalize()
            return best_match

    return _dictionary_correct(word)


_spell_checker = None
_MIN_DICTIONARY_WORD_LENGTH = 6
_MIN_CANDIDATE_FREQUENCY = 1e-6


def _get_spell_checker():
    global _spell_checker
    if _spell_checker is None:
        from spellchecker import SpellChecker
        _spell_checker = SpellChecker(distance=1)
    return _spell_checker


def _dictionary_correct(word: str) -> str:
    """Fix an unknown, lowercase word against a general English dictionary.

    Deliberately conservative: short words, acronyms, capitalised names and anything
    with digits are left alone so valid technical terms are never rewritten.
    """
    if not word.isalpha() or not word.islower() or len(word) < _MIN_DICTIONARY_WORD_LENGTH:
        return word
    try:
        spell = _get_spell_checker()
    except ImportError:
        return word
    if spell.known([word]):
        return word

    candidates = spell.known(spell.edit_distance_1(word))
    if not candidates and len(word) >= 8:
        candidates = spell.known(spell.edit_distance_2(word))
    candidates = {
        candidate for candidate in candidates
        if candidate[0] == word[0]
        and spell.word_usage_frequency(candidate) >= _MIN_CANDIDATE_FREQUENCY
    }
    if not candidates:
        return word
    # A dropped letter is the most common typo, so prefer candidates that restore one
    # over equally close substitutions ("screning" -> "screening", not "screwing").
    return max(
        candidates,
        key=lambda candidate: (len(candidate) > len(word), spell.word_usage_frequency(candidate)),
    )


def normalize_topic_spelling(topic: str) -> str:
    """
    Normalize and fix spelling/typos in user-provided research topics or queries.
    Preserves casing style, punctuation, and structure while correcting misspelled terms
    such as 'oken' -> 'token', 'ptimization' -> 'optimization', etc.
    """
    if not topic or not str(topic).strip():
        return ""

    text = str(topic).strip()

    is_first_token = True

    def replace_token(match: re.Match) -> str:
        nonlocal is_first_token
        word = match.group(0)
        corrected = correct_word(word)
        if is_first_token and corrected == word and word.istitle():
            # Sentence-initial words are capitalised by position, not because they are names.
            fixed = _dictionary_correct(word.lower())
            corrected = fixed.capitalize() if fixed != word.lower() else word
        is_first_token = False
        return corrected

    # Replace word tokens preserving spacing and punctuation
    normalized = re.sub(r"[a-zA-Z]+(?:'[a-zA-Z]+)?", replace_token, text)
    return normalized
