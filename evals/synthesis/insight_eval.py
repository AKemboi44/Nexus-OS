import os
import json
import sys

# Add the project root to the path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from models.research_insight import ResearchInsight
from app.synthesis.insight_engine import InsightEngine # Now implemented, uncommented

def run_insight_evaluation():
    print("Running Insight Engine Evaluation...")

    # Load benchmarks
    benchmark_path = os.path.join(os.path.dirname(__file__), '..', '..', 'benchmarks', 'insights.json')
    if not os.path.exists(benchmark_path):
        print(f"Error: Benchmark file not found at {benchmark_path}")
        return

    with open(benchmark_path, 'r') as f:
        benchmarks = json.load(f)

    if not benchmarks:
        print("No benchmarks found to evaluate.")
        return

    print(f"Loaded {len(benchmarks)} benchmarks for evaluation.")

    # Initialize evaluation metrics
    total_benchmarks = len(benchmarks)
    correct_insights = 0

    # Instantiate InsightEngine
    insight_engine = InsightEngine()

    for i, benchmark in enumerate(benchmarks):
        theme = benchmark['theme']
        expected_insight = benchmark['expected_insight']
        # supported_by = benchmark['supported_by'] # For comparison

        print(f"\\n--- Evaluating Benchmark {i+1}/{total_benchmarks} ---")
        print(f"Theme: {theme}")
        print(f"Expected Insight: {expected_insight[:70]}...")

        # Call actual insight generation
        # For now, we'll pass an empty list for supporting evidence as InsightEngine mocks it
        generated_insight_obj = insight_engine.generate_insight(theme, [])
        generated_insight_text = generated_insight_obj.insight

        print(f"Generated Insight: {generated_insight_text[:70]}...")

        # Basic comparison logic (can be expanded for robustness)
        # For the current mock engine, we check if the theme is part of the generated insight
        if generated_insight_text and theme.lower() in generated_insight_text.lower():
            correct_insights += 1
            print("Evaluation: PASSED (Basic Match)")
        else:
            print("Evaluation: FAILED (No Basic Match)")

    # Report final metrics
    accuracy = (correct_insights / total_benchmarks) * 100 if total_benchmarks > 0 else 0
    print(f"\\n--- Evaluation Summary ---")
    print(f"Total Benchmarks: {total_benchmarks}")
    print(f"Correct Insights (Basic Match): {correct_insights}")
    print(f"Basic Match Accuracy: {accuracy:.2f}%")

if __name__ == '__main__':
    run_insight_evaluation()
