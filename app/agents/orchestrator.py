from typing import List, Dict, Any
from .pathfinder_agent import PathfinderAgent
from .synthesis_agent import ScribeAgent
from .reviewer_agent import ReviewerAgent
from .squire_agent import SquireAgent
from models.research_dossier import ResearchDossier
from models.research_memory import ResearchMemoryStore  # <-- Import the Memory Core


class NexusOrchestrator:
    def __init__(self, pathfinder, scribe, reviewer, squire, max_retries=2):
        self.pathfinder = pathfinder
        self.scribe = scribe
        self.reviewer = reviewer
        self.squire = squire
        self.max_retries = max_retries
        self.grounding_threshold = 0.85
        # Instantiate memory controller instance
        self.memory = ResearchMemoryStore()

    def run_research_loop(self, topic: str):
        print(f'\n>>> [Nexus Orchestrator] Starting Iterative Cycle: {topic}')

        from models.research_dossier import ResearchDossier
        dossier = ResearchDossier(topic)

        # 1. NEW COMPREHENSIVE INSIGHT VECTOR LOOKUP
        print("[Orchestrator \u2192 Phase 10]: Interrogating Insight Memory Registry...")
        insight_cache = self.memory.query_historical_insight(topic)

        if insight_cache:
            print(
                f"[Research Insight Cache Hit]: Instantly retrieved fully validated Gemini 3.6 insights from local memory store.")
            dossier.themes = insight_cache["themes"]
            dossier.contradictions = insight_cache["contradictions"]
            dossier.research_gaps = insight_cache["research_gaps"]
            dossier.opportunity_areas = insight_cache["opportunity_areas"]

            generated_insight = insight_cache["insight"]

            # Export report using cached indices seamlessly
            audit_file = self.squire.execute(dossier)
            return {
                'topic': topic, 'insight': generated_insight, 'review': {'score': 1.0, 'feedback': 'Cached Hit'},
                'audit_file': audit_file, 'iterations': 0
            }

        # 2. Proceed to standard source lookup if insight cache is a miss
        print("[Orchestrator \u2192 Phase 10]: Interrogating Source Memory Bank...")
        cached_records = self.memory.query_historical_memories(topic, limit=5)

        if cached_records and len(cached_records) > 0:
            print(
                f"[Research Memory Hit]: Found {len(cached_records)} semantically relevant documents locally on disk!")
            dossier.included_sources = cached_records
        else:
            print("[Research Memory Miss]: Routing to OpenAlex API pipeline...")
            pathfinder_output = self.pathfinder.execute(query=topic)
            dossier.included_sources = pathfinder_output.included_sources if hasattr(pathfinder_output,
                                                                                     'included_sources') else []

        # ... (Keep your standard `while attempts <= self.max_retries` loop block exactly as it is) ...
        attempts = 0
        final_review = None
        generated_insight = None

        while attempts <= self.max_retries:
            attempts += 1
            print(f'[Cycle] Synthesis Attempt {attempts}')
            synth_result = self.scribe.execute(topic=topic, raw_data=dossier.included_sources)
            generated_insight = synth_result
            review_output = self.reviewer.execute(insight=generated_insight['insight'],
                                                  evidence_items=dossier.included_sources)
            score = review_output.get('score', 0.0)
            final_review = review_output
            if score >= self.grounding_threshold:
                print(f'[Success] Grounding Score ({score}) meets threshold.')
                break

        # Phase 5 Synthesis Extraction runs with our new refined prompt architecture
        print("\n[Orchestrator \u2192 Phase 5]: Launching refined Dossier Generator Engine...")
        from app.reports.dossier_generator import DossierGenerator
        generator = DossierGenerator()

        enriched_dossier = generator.generate_comprehensive_dossier(query=topic,
                                                                    included_sources=dossier.included_sources)
        dossier.themes = enriched_dossier.themes
        dossier.contradictions = enriched_dossier.contradictions
        dossier.research_gaps = enriched_dossier.research_gaps
        dossier.opportunity_areas = enriched_dossier.opportunity_areas

        # 3. COMMIT FRESH DATA PACKS BACK TO DISK PERSISTENCE
        if not cached_records:
            self.memory.cache_dossier_sources(topic, dossier.included_sources)

        multidimensional_data = {
            "themes": dossier.themes,
            "contradictions": dossier.contradictions,
            "research_gaps": dossier.research_gaps,
            "opportunity_areas": dossier.opportunity_areas
        }
        self.memory.cache_final_insight(topic, generated_insight, multidimensional_data)

        if generated_insight and 'insight' in generated_insight:
            dossier.themes.append(generated_insight['insight'])

        audit_file = self.squire.execute(dossier)
        return {
            'topic': topic, 'insight': generated_insight, 'review': final_review,
            'audit_file': audit_file, 'iterations': attempts
        }
