from typing import List, Dict, Any
from .pathfinder_agent import PathfinderAgent

from .synthesis_agent import ScribeAgent
from .reviewer_agent import ReviewerAgent
from .squire_agent import SquireAgent
from models.research_dossier import ResearchDossier

class NexusOrchestrator:
    def __init__(self, pathfinder, scribe, reviewer, squire, max_retries=2):
        self.pathfinder = pathfinder
        self.scribe = scribe
        self.reviewer = reviewer
        self.squire = squire
        self.max_retries = max_retries
        self.grounding_threshold = 0.85

    def run_research_loop(self, topic: str):
        print(f'\n>>> [Nexus Orchestrator] Starting Iterative Cycle: {topic}')

        # 1. Let the Pathfinder execute and return its discovery payload (whether a model or a dict)
        pathfinder_output = self.pathfinder.execute(query=topic)

        # 2. Re-instantiate or populate a structural ResearchDossier object safely
        from models.research_dossier import ResearchDossier

        if isinstance(pathfinder_output, dict):
            # Extract fields out of dictionary keys if pathfinder returns a raw dict
            dossier = ResearchDossier(topic)
            dossier.included_sources = pathfinder_output.get('included_sources', [])
            dossier.excluded_sources = pathfinder_output.get('excluded_sources', [])
            dossier.evidence_summary = pathfinder_output.get('evidence_summary', [])
        elif pathfinder_output is not None:
            # Use the object directly if it is already a model class instance
            dossier = pathfinder_output
        else:
            # Emergency fallback safety net
            dossier = ResearchDossier(topic)

        # Initialize tracking state variables before entering loop block
        attempts = 0
        final_review = None
        generated_insight = None

        # 3. Enter the iterative synthesis refinement review loop
        while attempts <= self.max_retries:
            attempts += 1
            print(f'[Cycle] Synthesis Attempt {attempts}')

            # Call Scribe Synthesizer to process discovered sources
            synth_result = self.scribe.execute(topic=topic, raw_data=dossier.included_sources)
            generated_insight = synth_result  # Captures the full insight output dictionary

            # Execute factual grounding review via Reviewer Agent
            review_output = self.reviewer.execute(
                insight=generated_insight['insight'],
                evidence_items=dossier.included_sources
            )

            score = review_output.get('score', 0.0)
            final_review = review_output

            if score >= self.grounding_threshold:
                print(f'[Success] Grounding Score ({score}) meets threshold.')
                break

            print(f'[Refinement] Score {score} too low. Retrying...')

        # 4. Save the finalized verified insight back to themes and generate the Squire excel report
        dossier.themes.append(generated_insight['insight'])
        audit_file = self.squire.execute(dossier)

        return {
            'topic': topic,
            'insight': generated_insight,
            'review': final_review,
            'audit_file': audit_file,
            'iterations': attempts
        }
