from app.research.providers.semantic_scholar_provider import SemanticScholarProvider


def test_semantic_scholar_provider_uses_environment_api_key(monkeypatch):
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "semantic-scholar-test-key")

    assert SemanticScholarProvider().api_key == "semantic-scholar-test-key"


def test_explicit_semantic_scholar_api_key_overrides_environment(monkeypatch):
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "environment-key")

    assert SemanticScholarProvider(api_key="explicit-key").api_key == "explicit-key"
