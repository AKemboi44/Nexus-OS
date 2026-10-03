"""Integration tests for proposal generation, validation, and DOCX rendering."""

import pytest
import tempfile
from pathlib import Path
from app.reports.proposal_builder import build_proposal_from_research
from app.reports.proposal_validation import validate_proposal_draft
from app.reports.proposal_renderer import render_proposal_docx
from app.reports.evidence_preparation import prepare_proposal_evidence, SourceRecord
from app.reports.metadata_extractor import extract_research_metadata


@pytest.fixture
def test_sources():
    """Create realistic test sources."""
    return [
        {
            "source_id": "S1",
            "title": "Machine Learning: Theory and Practice",
            "authors": "Smith et al.",
            "year": "2023",
            "publication": "IEEE AI Review",
            "doi_or_url": "10.1234/ieee.2023",
            "abstract": "This comprehensive review examines modern machine learning architectures and their applications. We identify gaps in interpretability and scalability. Novel approaches show promise for efficient training. Our systematic analysis reveals opportunities for cross-domain learning and practical deployment."
        },
        {
            "source_id": "S2",
            "title": "Deep Learning for Natural Language Processing",
            "authors": "Johnson, M.",
            "year": "2022",
            "publication": "ACM Transactions",
            "doi_or_url": "10.1234/acm.2022",
            "abstract": "We explore deep learning approaches for NLP tasks. Our empirical study demonstrates limitations in current methods. We propose novel methodologies addressing these gaps. Results show significant improvements in performance and efficiency."
        },
        {
            "source_id": "S3",
            "title": "Neural Networks: Architecture and Optimization",
            "authors": "Brown, Chen, Davis",
            "year": "2021",
            "publication": "Journal of ML",
            "doi_or_url": "10.1234/jml.2021",
            "abstract": "This paper surveys neural network architectures across domains. We systematically investigate optimization techniques. Key findings reveal underexplored areas in generalization. Integration of emerging methods offers opportunities for enhanced real-world deployment."
        }
    ]


def test_proposal_end_to_end_generation_and_rendering(test_sources):
    """Test full pipeline: build -> validate -> render -> file creation."""
    
    # Extract metadata from sources
    metadata = extract_research_metadata(test_sources, "Machine Learning and AI")
    assert metadata["themes"], "Should extract themes"
    assert metadata["research_gaps"], "Should extract gaps"
    assert metadata["opportunity_areas"], "Should extract opportunities"
    
    # Create evidence packet
    packet = prepare_proposal_evidence(
        "Machine Learning and AI",
        "technology",
        test_sources
    )
    assert len(packet.sources) == 3
    assert len(packet.sent_source_ids) == 3
    
    # Build proposal
    draft = build_proposal_from_research(
        topic="Machine Learning and AI",
        domain="technology",
        dossier=metadata,
        packet=packet
    )
    
    # Validate
    validation = validate_proposal_draft(draft, packet, min_words=800, max_words=2000)
    assert validation.passed, f"Validation failed: {validation.errors}"
    assert validation.word_count >= 800, f"Word count too low: {validation.word_count}"
    print(f"✓ Draft validation passed: {validation.word_count} words")
    
    # Render to DOCX
    with tempfile.TemporaryDirectory(prefix="test-proposal-") as tmpdir:
        doc_path = Path(tmpdir) / "proposal.docx"
        
        # This should not raise
        render_proposal_docx(draft, packet, doc_path)
        
        # Verify file exists and has content
        assert doc_path.exists(), "DOCX file should be created"
        file_size = doc_path.stat().st_size
        assert file_size > 1000, f"DOCX file too small ({file_size} bytes)"
        print(f"✓ DOCX rendered successfully: {file_size} bytes")
        
        # Read back to verify it's valid
        doc_bytes = doc_path.read_bytes()
        assert len(doc_bytes) == file_size
        assert b"PK" in doc_bytes[:10], "DOCX should be ZIP-format (start with PK)"
        print(f"✓ DOCX file integrity verified")


def test_proposal_handles_empty_optional_fields(test_sources):
    """Test proposal generation with minimal metadata (graceful degradation)."""
    
    # Create minimal dossier (some fields empty)
    minimal_dossier = {
        "abstract": "",
        "themes": [],  # Empty themes
        "research_gaps": ["Gap in understanding"],
        "opportunity_areas": [],  # Empty opportunities
        "research_areas": ["Research"],
    }
    
    packet = prepare_proposal_evidence("Test Topic", "scholarly", test_sources)
    
    # Should still generate valid proposal
    draft = build_proposal_from_research(
        topic="Test Topic",
        domain="scholarly",
        dossier=minimal_dossier,
        packet=packet
    )
    
    validation = validate_proposal_draft(draft, packet, min_words=800, max_words=2000)
    assert validation.passed, f"Should pass with minimal data: {validation.errors}"
    print(f"✓ Minimal dossier produces valid proposal: {validation.word_count} words")


def test_proposal_word_count_targets(test_sources):
    """Verify proposal meets graduate-level word count targets."""
    
    metadata = extract_research_metadata(test_sources, "AI Research")
    packet = prepare_proposal_evidence("AI Research", "technology", test_sources)
    
    draft = build_proposal_from_research(
        topic="AI Research",
        domain="technology",
        dossier=metadata,
        packet=packet
    )
    
    validation = validate_proposal_draft(draft, packet, min_words=1000, max_words=2000)
    assert validation.passed, f"Should meet 1000+ word target: {validation.word_count} words"
    assert validation.word_count >= 1000, "Should reach 1000-word minimum"
    print(f"✓ Proposal word count: {validation.word_count} (target: 1000+)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
