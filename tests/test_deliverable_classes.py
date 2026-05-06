"""Tests for Deliverable class pipelines.

Covers:
- DeliverableClass: enum values for paper, technical_doc, executive_brief, decision_memo
- DeliverableClassConfig: fields, frozen, per-class defaults
- Pre-built configs: PAPER_CONFIG, TECHNICAL_DOC_CONFIG, EXECUTIVE_BRIEF_CONFIG, DECISION_MEMO_CONFIG
- validate_synthesis_for_class: valid synthesis passes, missing sections fail, word limit enforced
- create_pipeline: returns DeliverablePipeline configured for the given class
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# DeliverableClass
# ---------------------------------------------------------------------------

class TestDeliverableClass:
    def test_paper_value(self):
        from src.deliverables.classes import DeliverableClass
        assert DeliverableClass.PAPER.value == "paper"

    def test_technical_doc_value(self):
        from src.deliverables.classes import DeliverableClass
        assert DeliverableClass.TECHNICAL_DOC.value == "technical_doc"

    def test_executive_brief_value(self):
        from src.deliverables.classes import DeliverableClass
        assert DeliverableClass.EXECUTIVE_BRIEF.value == "executive_brief"

    def test_decision_memo_value(self):
        from src.deliverables.classes import DeliverableClass
        assert DeliverableClass.DECISION_MEMO.value == "decision_memo"

    def test_exactly_four_classes(self):
        from src.deliverables.classes import DeliverableClass
        assert len(list(DeliverableClass)) == 4


# ---------------------------------------------------------------------------
# DeliverableClassConfig
# ---------------------------------------------------------------------------

class TestDeliverableClassConfig:
    def _make(self, **kw):
        from src.deliverables.classes import DeliverableClass, DeliverableClassConfig
        defaults = dict(
            deliverable_class=DeliverableClass.PAPER,
            default_format="latex",
            required_sections=("abstract",),
        )
        return DeliverableClassConfig(**{**defaults, **kw})

    def test_has_deliverable_class_field(self):
        from src.deliverables.classes import DeliverableClass
        c = self._make()
        assert c.deliverable_class == DeliverableClass.PAPER

    def test_has_default_format_field(self):
        c = self._make(default_format="markdown")
        assert c.default_format == "markdown"

    def test_has_required_sections_field(self):
        c = self._make(required_sections=("intro", "conclusion"))
        assert c.required_sections == ("intro", "conclusion")

    def test_max_body_words_defaults_to_none(self):
        c = self._make()
        assert c.max_body_words is None

    def test_requires_citations_defaults_to_false(self):
        c = self._make()
        assert c.requires_citations is False

    def test_default_revision_cycles_defaults_to_one(self):
        c = self._make()
        assert c.default_revision_cycles == 1

    def test_is_frozen(self):
        from dataclasses import FrozenInstanceError
        c = self._make()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            c.default_format = "pdf"  # type: ignore[misc]

    def test_to_dict_has_expected_keys(self):
        c = self._make()
        d = c.to_dict()
        assert {
            "deliverable_class", "default_format", "required_sections",
            "max_body_words", "requires_citations", "default_revision_cycles",
        } <= d.keys()

    def test_to_dict_from_dict_round_trip(self):
        from src.deliverables.classes import DeliverableClass, DeliverableClassConfig
        c = self._make(
            required_sections=("abstract", "methods"),
            max_body_words=500,
            requires_citations=True,
        )
        c2 = DeliverableClassConfig.from_dict(c.to_dict())
        assert c2 == c


# ---------------------------------------------------------------------------
# Pre-built configs
# ---------------------------------------------------------------------------

class TestPaperConfig:
    def test_class_is_paper(self):
        from src.deliverables.classes import PAPER_CONFIG, DeliverableClass
        assert PAPER_CONFIG.deliverable_class == DeliverableClass.PAPER

    def test_format_is_latex(self):
        from src.deliverables.classes import PAPER_CONFIG
        assert PAPER_CONFIG.default_format == "latex"

    def test_requires_citations(self):
        from src.deliverables.classes import PAPER_CONFIG
        assert PAPER_CONFIG.requires_citations is True

    def test_has_expected_sections(self):
        from src.deliverables.classes import PAPER_CONFIG
        sections = PAPER_CONFIG.required_sections
        assert "abstract" in sections
        assert "introduction" in sections


class TestTechnicalDocConfig:
    def test_class_is_technical_doc(self):
        from src.deliverables.classes import TECHNICAL_DOC_CONFIG, DeliverableClass
        assert TECHNICAL_DOC_CONFIG.deliverable_class == DeliverableClass.TECHNICAL_DOC

    def test_format_is_markdown(self):
        from src.deliverables.classes import TECHNICAL_DOC_CONFIG
        assert TECHNICAL_DOC_CONFIG.default_format == "markdown"

    def test_does_not_require_citations(self):
        from src.deliverables.classes import TECHNICAL_DOC_CONFIG
        assert TECHNICAL_DOC_CONFIG.requires_citations is False

    def test_has_expected_sections(self):
        from src.deliverables.classes import TECHNICAL_DOC_CONFIG
        sections = TECHNICAL_DOC_CONFIG.required_sections
        assert "overview" in sections


class TestExecutiveBriefConfig:
    def test_class_is_executive_brief(self):
        from src.deliverables.classes import EXECUTIVE_BRIEF_CONFIG, DeliverableClass
        assert EXECUTIVE_BRIEF_CONFIG.deliverable_class == DeliverableClass.EXECUTIVE_BRIEF

    def test_has_max_body_words(self):
        from src.deliverables.classes import EXECUTIVE_BRIEF_CONFIG
        assert EXECUTIVE_BRIEF_CONFIG.max_body_words is not None
        assert EXECUTIVE_BRIEF_CONFIG.max_body_words > 0

    def test_does_not_require_citations(self):
        from src.deliverables.classes import EXECUTIVE_BRIEF_CONFIG
        assert EXECUTIVE_BRIEF_CONFIG.requires_citations is False

    def test_has_key_takeaways_section(self):
        from src.deliverables.classes import EXECUTIVE_BRIEF_CONFIG
        assert "key_takeaways" in EXECUTIVE_BRIEF_CONFIG.required_sections


class TestDecisionMemoConfig:
    def test_class_is_decision_memo(self):
        from src.deliverables.classes import DECISION_MEMO_CONFIG, DeliverableClass
        assert DECISION_MEMO_CONFIG.deliverable_class == DeliverableClass.DECISION_MEMO

    def test_has_recommendation_section(self):
        from src.deliverables.classes import DECISION_MEMO_CONFIG
        assert "recommendation" in DECISION_MEMO_CONFIG.required_sections

    def test_has_rationale_section(self):
        from src.deliverables.classes import DECISION_MEMO_CONFIG
        assert "rationale" in DECISION_MEMO_CONFIG.required_sections

    def test_has_max_body_words(self):
        from src.deliverables.classes import DECISION_MEMO_CONFIG
        assert DECISION_MEMO_CONFIG.max_body_words is not None


# ---------------------------------------------------------------------------
# validate_synthesis_for_class
# ---------------------------------------------------------------------------

class TestValidateSynthesisForClass:
    def _synthesis(self, body: str, title: str = "T"):
        from src.deliverables.pipeline import SynthesisArtifact
        return SynthesisArtifact(title=title, body=body)

    def test_valid_synthesis_returns_empty_list(self):
        from src.deliverables.classes import DeliverableClass, validate_synthesis_for_class
        from src.deliverables.classes import TECHNICAL_DOC_CONFIG
        body = "## Overview\nContent\n## Installation\nSteps\n## Usage\nHow to use\n## api_reference\nAPI"
        synthesis = self._synthesis(body)
        violations = validate_synthesis_for_class(synthesis, TECHNICAL_DOC_CONFIG)
        assert violations == []

    def test_missing_required_section_reported(self):
        from src.deliverables.classes import validate_synthesis_for_class
        from src.deliverables.classes import TECHNICAL_DOC_CONFIG
        synthesis = self._synthesis("## Overview\nContent only")
        violations = validate_synthesis_for_class(synthesis, TECHNICAL_DOC_CONFIG)
        assert any("installation" in v.lower() for v in violations)

    def test_all_missing_sections_reported(self):
        from src.deliverables.classes import validate_synthesis_for_class
        from src.deliverables.classes import TECHNICAL_DOC_CONFIG
        synthesis = self._synthesis("Nothing relevant here")
        violations = validate_synthesis_for_class(synthesis, TECHNICAL_DOC_CONFIG)
        assert len(violations) == len(TECHNICAL_DOC_CONFIG.required_sections)

    def test_word_limit_exceeded_is_reported(self):
        from src.deliverables.classes import validate_synthesis_for_class
        from src.deliverables.classes import EXECUTIVE_BRIEF_CONFIG
        max_w = EXECUTIVE_BRIEF_CONFIG.max_body_words
        long_body = (
            "key_takeaways recommendations " + ("word " * (max_w + 10))
        )
        synthesis = self._synthesis(long_body)
        violations = validate_synthesis_for_class(synthesis, EXECUTIVE_BRIEF_CONFIG)
        assert any("words" in v.lower() or "word" in v.lower() for v in violations)

    def test_word_limit_not_exceeded_no_word_violation(self):
        from src.deliverables.classes import validate_synthesis_for_class
        from src.deliverables.classes import EXECUTIVE_BRIEF_CONFIG
        short_body = "key_takeaways recommendations brief content"
        synthesis = self._synthesis(short_body)
        violations = validate_synthesis_for_class(synthesis, EXECUTIVE_BRIEF_CONFIG)
        assert not any("word" in v.lower() for v in violations)

    def test_no_word_limit_for_paper(self):
        from src.deliverables.classes import PAPER_CONFIG, validate_synthesis_for_class
        long_body = " ".join(
            ["abstract introduction methodology results conclusion"] * 200
        )
        synthesis = self._synthesis(long_body)
        violations = validate_synthesis_for_class(synthesis, PAPER_CONFIG)
        assert not any("word" in v.lower() for v in violations)


# ---------------------------------------------------------------------------
# create_pipeline
# ---------------------------------------------------------------------------

class TestCreatePipeline:
    def test_returns_deliverable_pipeline(self):
        from src.deliverables.classes import DeliverableClass, create_pipeline
        from src.deliverables.pipeline import DeliverablePipeline
        p = create_pipeline("LLM Safety", DeliverableClass.PAPER)
        assert isinstance(p, DeliverablePipeline)

    def test_topic_is_set(self):
        from src.deliverables.classes import DeliverableClass, create_pipeline
        p = create_pipeline("AI Ethics", DeliverableClass.EXECUTIVE_BRIEF)
        assert p.topic == "AI Ethics"

    def test_pipeline_starts_at_pending(self):
        from src.deliverables.classes import DeliverableClass, create_pipeline
        from src.deliverables.pipeline import PipelineStage
        p = create_pipeline("Topic", DeliverableClass.TECHNICAL_DOC)
        assert p.completed_stage == PipelineStage.PENDING

    def test_all_classes_can_create_pipeline(self):
        from src.deliverables.classes import DeliverableClass, create_pipeline
        for cls in DeliverableClass:
            p = create_pipeline("topic", cls)
            assert p.topic == "topic"

    def test_paper_pipeline_remembers_it_is_paper(self):
        from src.deliverables.classes import DeliverableClass, create_pipeline
        p = create_pipeline("LLM Safety", DeliverableClass.PAPER)
        assert p.deliverable_class == DeliverableClass.PAPER.value

    def test_executive_brief_pipeline_remembers_class(self):
        from src.deliverables.classes import DeliverableClass, create_pipeline
        p = create_pipeline("AI Ethics", DeliverableClass.EXECUTIVE_BRIEF)
        assert p.deliverable_class == DeliverableClass.EXECUTIVE_BRIEF.value

    def test_config_retrievable_from_pipeline_without_resupplying_class(self):
        from src.deliverables.classes import (
            DeliverableClass, create_pipeline, get_config_for_pipeline, PAPER_CONFIG,
        )
        p = create_pipeline("T", DeliverableClass.PAPER)
        config = get_config_for_pipeline(p)
        assert config == PAPER_CONFIG

    def test_all_classes_config_retrievable(self):
        from src.deliverables.classes import DeliverableClass, create_pipeline, get_config_for_pipeline, CLASS_CONFIGS
        for cls in DeliverableClass:
            p = create_pipeline("topic", cls)
            config = get_config_for_pipeline(p)
            assert config == CLASS_CONFIGS[cls]

    def test_pipeline_without_class_returns_none_config(self):
        from src.deliverables.classes import get_config_for_pipeline
        from src.deliverables.pipeline import DeliverablePipeline
        p = DeliverablePipeline(topic="bare pipeline")
        assert get_config_for_pipeline(p) is None
