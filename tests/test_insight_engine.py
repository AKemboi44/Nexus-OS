import unittest
import os
import sys
import json

# Add the project root to the path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.research_insight import ResearchInsight
from app.synthesis.insight_engine import InsightEngine # Now implemented, uncommented

class TestInsightEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Load benchmark data
        benchmark_path = os.path.join(os.path.dirname(__file__), '..', 'benchmarks', 'insights.json')
        with open(benchmark_path, 'r') as f:
            cls.benchmarks = json.load(f)
        cls.insight_engine = InsightEngine() # Initialize InsightEngine here

    def test_insight_generation_with_engine(self):
        # This test now uses the actual InsightEngine.
        self.assertIsNotNone(self.benchmarks)
        self.assertGreater(len(self.benchmarks), 0)
        print(f"Loaded {len(self.benchmarks)} benchmarks for insight engine testing.")

        for benchmark in self.benchmarks:
            theme = benchmark['theme']
            expected_insight_text = benchmark['expected_insight']
            # For now, we'll pass an empty list for supporting evidence as InsightEngine mocks it
            generated_insight = self.insight_engine.generate_insight(theme, [])

            # Assert that the generated insight is not empty and matches a basic pattern
            self.assertIsNotNone(generated_insight.insight)
            self.assertIn(theme.lower(), generated_insight.insight.lower())
            print()
            print(f"Tested Theme: {theme}")
            print(f"Expected Insight Snippet: {expected_insight_text[:50]}...")
            print(f"Generated Insight Snippet: {generated_insight.insight[:50]}...")

            # More robust comparison would be needed for a real system, e.g., semantic similarity

    def test_research_insight_model(self):
        # Test instantiation of ResearchInsight model
        insight_data = self.benchmarks[0]
        insight_obj = ResearchInsight(
            theme=insight_data['theme'],
            insight=insight_data['expected_insight'],
            supported_by=insight_data['supported_by']
        )
        self.assertEqual(insight_obj.theme, insight_data['theme'])
        self.assertEqual(insight_obj.insight, insight_data['expected_insight'])
        self.assertEqual(len(insight_obj.supported_by), len(insight_data['supported_by']))
        self.assertIsInstance(insight_obj.to_dict(), dict)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
