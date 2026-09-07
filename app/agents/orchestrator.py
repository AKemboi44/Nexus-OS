from typing import List, Dict, Any
import re
from .pathfinder_agent import PathfinderAgent
from .synthesis_agent import ScribeAgent
from .reviewer_agent import ReviewerAgent
from .squire_agent import SquireAgent
from models.research_dossier import ResearchDossier
from models.research_memory import ResearchMemoryStore


class NexusOrchestrator:
    def __init__(self, pathfinder, scribe, reviewer, squire, max_retries=2):
        self.pathfinder = pathfinder
        self.scribe = scribe
        self.reviewer = reviewer
        self.squire = squire
        self.max_retries = max_retries
        self.grounding_threshold = 0.85
        self.memory = ResearchMemoryStore()

    def run_research_loop(self, topic: str, custom_prompt: str = None, max_sources: int = 5):
        print(f'\n>>> [Nexus Orchestrator] Starting Iterative Cycle: {topic} (Sources Limit: {max_sources})')

        from models.research_dossier import ResearchDossier
        dossier = ResearchDossier(topic)

        # 1. Query local database memory registries
        print("[Orchestrator ➔ Phase 10]: Interrogating Insight Memory Registry...")
        insight_cache = self.memory.query_historical_insight(topic)

        if insight_cache:
            print(f"[Research Insight Cache Hit]: Instantly retrieved validated insights.")
            dossier.themes = insight_cache["themes"]
            dossier.contradictions = insight_cache["contradictions"]
            dossier.research_gaps = insight_cache["research_gaps"]
            dossier.opportunity_areas = insight_cache["opportunity_areas"]

            generated_insight = insight_cache["insight"]
            audit_file = self.squire.execute(dossier)
            return {
                'topic': topic,
                'insight': generated_insight,
                'review': {'score': 1.0, 'relevance_signal': 1.0},
                'audit_file': audit_file
            }

        print("[Orchestrator ➔ Phase 10]: Interrogating Source Memory Bank...")
        cached_records = self.memory.query_historical_memories(topic, limit=max_sources)

        if cached_records and len(cached_records) >= max_sources:
            print(f"[Research Memory Hit]: Found sufficient matching vectors locally on disk!")
            dossier.included_sources = cached_records[:max_sources]
        else:
            print("[Research Memory Miss]: Routing to live OpenAlex API pipeline...")
            pathfinder_output = self.pathfinder.execute(query=topic, limit=max_sources)

            if isinstance(pathfinder_output, dict):
                dossier.included_sources = pathfinder_output.get('included_sources', [])[:max_sources]
            elif hasattr(pathfinder_output, 'included_sources'):
                dossier.included_sources = pathfinder_output.included_sources[:max_sources]

        # 2. Main Iterative Verification Loop
        attempts = 0
        final_review = None
        generated_insight = None

        while attempts <= self.max_retries:
            attempts += 1
            print(f'[Cycle] Synthesis Attempt {attempts}')

            # FIXED: Pass custom_prompt configurations down into your Scribe Agent execution layer
            synth_result = self.scribe.execute(topic=topic, raw_data=dossier.included_sources,
                                               custom_prompt=custom_prompt)
            generated_insight = synth_result

            review_output = self.reviewer.execute(insight=generated_insight['insight'],
                                                  evidence_items=dossier.included_sources)
            score = review_output.get('score', 0.0)
            final_review = review_output
            if score >= self.grounding_threshold:
                break

        print("\n[Orchestrator ➔ Phase 5]: Launching refined Dossier Generator Engine...")
        from app.reports.dossier_generator import DossierGenerator
        generator = DossierGenerator()

        enriched_dossier = generator.generate_comprehensive_dossier(
            query=topic,
            included_sources=dossier.included_sources,
            custom_prompt=custom_prompt
        )
        dossier.themes = enriched_dossier.themes
        dossier.contradictions = enriched_dossier.contradictions
        dossier.research_gaps = enriched_dossier.research_gaps
        dossier.opportunity_areas = enriched_dossier.opportunity_areas

        if not cached_records:
            self.memory.cache_dossier_sources(topic, dossier.included_sources)

        multidimensional_data = {
            "themes": dossier.themes, "contradictions": dossier.contradictions,
            "research_gaps": dossier.research_gaps, "opportunity_areas": dossier.opportunity_areas
        }
        self.memory.cache_final_insight(topic, generated_insight, multidimensional_data)

        if generated_insight and 'insight' in generated_insight:
            dossier.themes.append(generated_insight['insight'])

        audit_file = self.squire.execute(dossier)

        # =========================================================================
        # RELEVANCE TRACKING SIGNAL ENGINE: Measures literal document hit alignment
        # =========================================================================
        keywords = [w.lower() for w in topic.split() if len(w) > 3]
        total_docs = len(dossier.included_sources)
        matched_docs = 0

        for src in dossier.included_sources:
            src_text = ""
            if isinstance(src, dict):
                src_text = (src.get('title', '') + " " + src.get('abstract', '')).lower()
            else:
                src_text = (getattr(src, 'title', '') + " " + getattr(src, 'abstract', '')).lower()

            if any(kw in src_text for kw in keywords):
                matched_docs += 1

        relevance_signal = round(matched_docs / total_docs, 2) if total_docs > 0 else 0.0

        # Inject the calculated topical metric value into the finalized dictionary
        final_review['relevance_signal'] = relevance_signal
        # =========================================================================

        return {'topic': topic, 'insight': generated_insight, 'review': final_review, 'audit_file': audit_file}
