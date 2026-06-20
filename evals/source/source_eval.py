import json

from models.source import Source
from evals.eval_result import EvalResult

# Test system behavior to see if it matches expectations i.e can open source_creation.json and print source title?.
def run():

    with open(
        "benchmarks/source_creation.json",
        "r"
    ) as f:

        benchmark = json.load(f)

    source = Source(**benchmark)

    # print("PASSED")
    # print (source.title)
    # Test system behavior to see if it matches expectations i.e can open source_creation.json and print source title?.
    result = EvalResult(
        name = "source_creation",
        passed = True,
        score= 1.0,
        details = "Source created successfully"
    )
    print(result.model_dump_json(indent=2))



if __name__ == "__main__":
    run()