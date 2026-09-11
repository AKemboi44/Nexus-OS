"""
Tests configuration loading.
"""

from config.settings import OPENALEX_API_KEY


def test_openalex_key_loaded():

    assert OPENALEX_API_KEY is not None

    assert len(OPENALEX_API_KEY) > 0