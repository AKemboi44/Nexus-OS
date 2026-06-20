# Evals registry that runs all the evals.
from evals.source.source_eval import run as source_eval
from evals.discovery.openalex_eval import run as discovery_eval

def main():
    results = [
        source_eval(),
        discovery_eval()
    ]

    results.append(source_eval())

    for result in results :
        print (result)


if __name__ == "__main__" :
    main()