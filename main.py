# import research definitions from the source model
from models.source import Source


def main():
    source = Source(
        id="1",
        title='impact of mobile loans on loan repayments',
        authors=['John Doe'],
        year=2025,
        abstract='A study on mobile money and repayment behaviour.',
        url="https://example.com/paper",
        source_type="academic"
    )

    print(source.model_dump())


if __name__ == "__main__":
    main()
