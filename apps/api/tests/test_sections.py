"""Tests for document section definitions."""

import pytest

from src.documents.sections import DOCUMENT_SECTIONS, get_sections


def test_all_doc_types_have_sections() -> None:
    """All 4 document types are defined."""
    assert set(DOCUMENT_SECTIONS.keys()) == {
        "vision",
        "architecture",
        "glossary",
        "design",
    }


def test_vision_has_6_sections() -> None:
    """Vision document has exactly 6 sections."""
    sections = get_sections("vision")
    assert len(sections) == 6
    assert sections[0].title == "Problem Statement"
    assert sections[5].title == "Non-Goals"


def test_architecture_has_7_sections() -> None:
    """Architecture document has exactly 7 sections."""
    sections = get_sections("architecture")
    assert len(sections) == 7


def test_glossary_has_5_sections() -> None:
    """Glossary document has exactly 5 sections."""
    sections = get_sections("glossary")
    assert len(sections) == 5


def test_design_has_6_sections() -> None:
    """Design system document has exactly 6 sections."""
    sections = get_sections("design")
    assert len(sections) == 6


def test_unknown_type_raises() -> None:
    """Unknown document type raises ValueError."""
    with pytest.raises(ValueError, match="Unknown document type"):
        get_sections("invalid")


def test_all_sections_have_required_fields() -> None:
    """Every section has non-empty id, title, question, description."""
    for doc_type, sections in DOCUMENT_SECTIONS.items():
        for section in sections:
            assert section.id, f"{doc_type}: section missing id"
            assert section.title, f"{doc_type}: section missing title"
            assert section.question, f"{doc_type}: section missing question"
            assert section.description, f"{doc_type}: section missing description"
