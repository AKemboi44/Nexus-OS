from evals.eval_result import EvalResult
from app.discovery.openalex import OpenAlexDiscovery

# Evals checks if
      # Returned results i.e Can OpenAlex return results?
      # Returned valid IDs
      # Returned valid titles

def run():

    discovery = OpenAlexDiscovery()

    result = discovery.search(
        "mobile money repayment"
    )

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
    score = min(
        len(result.sources) / 5,
        1.0
    )

    coverage_score = min(
        len(result.sources) / 5,
        1.0
    )

    details = (
        f"{len(result.sources)} "
        "normalized sources returned"
    )

    return EvalResult(
        name = "openalex_connectivity",
        passed = passed,
        score = score,
        details = details,
        # details = f"Returned {len(results['results'])} results" + (" (✅)" if passed else "❌")

    )


if __name__ == "__main__":
    print(run())