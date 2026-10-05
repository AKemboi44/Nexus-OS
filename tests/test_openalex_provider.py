"""OpenAlex normalization: abstracts rebuilt by word position, and an honest peer-review flag."""

import pytest

from app.research.providers.openalex_provider import OpenAlexProvider, reconstruct_abstract

SENTENCE = (
    "The integration of artificial intelligence (AI) into point-of-care testing (POCT) represents a "
    "transformative leap in modern healthcare, addressing critical challenges in diagnostic accuracy and "
    "workflow efficiency, while the promise of AI depends on the quality of the data and of the tests."
)


def invert(sentence):
    """What OpenAlex sends: {word: [every position the word occurs at]}."""
    index = {}
    for position, word in enumerate(sentence.split()):
        index.setdefault(word, []).append(position)
    return index


def work(**overrides):
    base = {
        "id": "https://openalex.org/W1",
        "title": "Artificial intelligence in point-of-care testing",
        "publication_year": 2025,
        "cited_by_count": 36,
        "doi": "https://doi.org/10.1016/j.cca.2025.120341",
        "authorships": [{"author": {"display_name": "Tahir S. Pillay"}}],
        "primary_location": {"is_published": True, "source": {"display_name": "Clinica Chimica Acta", "type": "journal"}},
        "abstract_inverted_index": invert(SENTENCE),
    }
    base.update(overrides)
    return base


# --- abstracts ----------------------------------------------------------------------------------------

def test_a_repeated_word_is_placed_at_each_of_its_own_positions_not_clumped_together():
    assert reconstruct_abstract(invert(SENTENCE)) == SENTENCE


def test_the_old_clumping_output_is_gone():
    text = reconstruct_abstract(invert(SENTENCE))
    for clumped in ("of of", "AI AI", "the the", "and and"):
        assert clumped not in text


def test_the_text_survives_a_real_normalization_round_trip():
    normalized = OpenAlexProvider().normalize_schema(work())
    assert normalized["abstract"] == SENTENCE and len(normalized["abstract"].split()) == len(SENTENCE.split())


@pytest.mark.parametrize("index", [None, {}, [], "text", 7])
def test_a_missing_or_malformed_index_gives_the_existing_placeholder_not_an_error(index):
    assert reconstruct_abstract(index) == "No description."


def test_gaps_and_odd_positions_are_tolerated_and_order_is_kept():
    assert reconstruct_abstract({"b": [5], "a": [0], "c": [9]}) == "a b c"
    assert reconstruct_abstract({"a": [0], "bad": ["x", None], "b": [1]}) == "a b"
    assert reconstruct_abstract({"a": None, "b": [0]}) == "b"


def test_an_abstract_with_no_index_keeps_the_placeholder_the_pipeline_already_expects():
    assert OpenAlexProvider().normalize_schema(work(abstract_inverted_index=None))["abstract"] == "No description."


# --- the peer-review flag ----------------------------------------------------------------------------

@pytest.mark.parametrize("location, expected", [
    ({"is_published": True, "source": {"type": "journal", "display_name": "J"}}, True),
    ({"is_published": None, "source": {"type": "journal", "display_name": "J"}}, True),
    ({"is_published": False, "source": {"type": "journal", "display_name": "J"}}, False),
    ({"is_published": True, "source": {"type": "book series", "display_name": "Lecture Notes"}}, False),
    ({"is_published": True, "source": {"type": "repository", "display_name": "arXiv"}}, False),
    ({"is_published": True, "source": None}, False),
    (None, False),
])
def test_journal_published_works_are_flagged_and_everything_else_is_not(location, expected):
    assert OpenAlexProvider().normalize_schema(work(primary_location=location))["is_peer_reviewed"] is expected


def test_the_flag_no_longer_depends_on_a_field_openalex_does_not_have():
    location = {"is_published": True, "source": {"type": "journal", "display_name": "J", "is_peer_reviewed": False}}
    assert OpenAlexProvider().normalize_schema(work(primary_location=location))["is_peer_reviewed"] is True


def test_the_other_fields_are_unchanged():
    normalized = OpenAlexProvider().normalize_schema(work())
    assert normalized["uid"] == "https://openalex.org/W1" and normalized["year"] == 2025
    assert normalized["authors"] == ["Tahir S. Pillay"] and normalized["venue"] == "Clinica Chimica Acta"
    assert normalized["citation_count"] == 36 and normalized["url"] == "https://doi.org/10.1016/j.cca.2025.120341"
