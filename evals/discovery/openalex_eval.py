from evals.eval_result import EvalResult
from app import OpenAlexDiscovery

# Evals checks if
      # Returned results i.e Can OpenAlex return results?
      # Returned valid IDs
      # Returned valid titles

def run():

    discovery = OpenAlexDiscovery()

    result = discovery.search(
        "mobile money repayment"
    )
    # result = discovery.search(
    #     "financial inclusion mobile money"
    # )

    all_have_titles = all(
        source.title
        for source in result.sources
    )

    all_have_ids = all(
        source.id
        for source in result.sources
    )

    for source in result.sources:
        print(source.title)

    passed = (
            len(result.sources) > 0
            and all_have_titles
            and all_have_ids
    )

# Discovery coverage score
    coverage_score = min(
        len(result.sources) / 5,
        1.0
    )

# Expected keywords for this benchmark
    keywords = [
        "mobile",
        "money",
        "financial",
        "loan",
        "repayment"
    ]

    matches =  0
    for source in result.sources:
        title = source.title.lower()
        for keyword in keywords:
            if keyword in title:
                matches += 1

# Discovery relevance score calculation
    relevance_score = (
        matches /
        (
            len(result.sources) * len(keywords)
        )

    )

# combined discovery quality score calculation
    score = (coverage_score + relevance_score)/ 2

    details = (
        f"{len(result.sources)} "
        "normalized sources returned"
    )

    print(f"\n------Discovery Metrics------")

    print(
        f"Coverage Score: {coverage_score:.2f}"
    )
    print(
        f"Relevance Score: {relevance_score:.2f}"
    )
    print(
        f"Keyword Matcches: {matches}"
    )
    print("---------------------------------")

    return EvalResult(
        name = "openalex_connectivity",
        passed = passed,
        score = score,
        details = details,
        # details = f"Returned {len(results['results'])} results" + (" (✅)" if passed else "❌")

    )


if __name__ == "__main__":
    print(run())