# app/research/scoring_matrix.py
class SourceQualityEvaluator:
    @staticmethod
    def compute_quality_score(normalized_source: dict, relevance_signal: float) -> float:
        """
        Applies data warehouse filtration weights to rank sources algorithmically.
        """
        # 1. Base Citation Magnitude Score (Logarithmic scaling to tame massive citation disparities)
        import math
        citations = normalized_source.get("citation_count", 0)
        citation_score = math.log1p(citations) / 5.0  # Normalized weight cap

        # 2. Strict Peer-Review / Judicial Authority Multiplier
        authority_multiplier = 1.3 if normalized_source.get("is_peer_reviewed") else 0.8

        # 3. Contextual Relevance Weighting
        # Combined composite calculations
        composite_score = (relevance_signal * 0.50) + (citation_score * 0.30)
        final_score = composite_score * authority_multiplier

        return min(round(final_score, 3), 1.0)
