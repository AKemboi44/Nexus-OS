# import research definitions from the source model
from models.source import Source


def main():
    pipeline = ResearchPipeline()

    dossier = pipeline.run_research(
        "Impact of mobile money on loan repayment"
    )

    print(dossier.model_dump())


if __name__ == "__main__":
    main()
