import json

from evals.eval_result import EvalResult
from app.extraction.extractor import (
    EvidenceExtractor
)

def run():

    with open(
        "benchmarks/extraction.json",
        "r"
    ) as f:

        benchmark = json.load(f)

    abstract = benchmark["abstract"]

    extractor = EvidenceExtractor()

    evidence = extractor.extract(
        abstract
    )
# Create score
    score = 0
# Methodology
    if evidence.methodology:
        score += 0.25

# Findings
    if evidence.findings:
        score += 0.25
# Limitations
    if evidence.limitations:
        score += 0.25
# Future work
    if evidence.future_work:
        score += 0.25

    passed = score >= 0.75

    return EvalResult(
        name="extraction_quality",
        passed=passed,
        score= score,
        details= str(evidence)
    )


if __name__ == "__main__":
    print(run())