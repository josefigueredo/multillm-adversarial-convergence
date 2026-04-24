"""Tests for run-mode synthesis output style contracts."""

import pytest

from src.config import OutputStyleOverrides
from src.output_style import (
    VALID_OUTPUT_STYLES,
    build_output_style_contract,
    build_output_style_report_policy,
    summarize_output_style_overrides,
)


def test_valid_output_styles_are_exposed():
    assert VALID_OUTPUT_STYLES == (
        "default",
        "paper",
        "technical_doc",
        "executive_brief",
        "decision_memo",
    )


def test_default_output_style_contract_mentions_default_report_shape():
    contract = build_output_style_contract("default")
    assert "executive summary" in contract.lower()
    assert "comparison table" in contract.lower()


def test_paper_output_style_contract_mentions_formal_sections():
    contract = build_output_style_contract("paper")
    lowered = contract.lower()
    assert "abstract" in lowered
    assert "methodology" in lowered
    assert "limitations" in lowered
    assert "do not include an executive summary" in lowered
    assert "do not include a comparison table" in lowered
    assert "references section" in lowered
    assert "present evidence and findings before stating the recommendation" in lowered


def test_technical_doc_output_style_contract_mentions_operational_sections():
    contract = build_output_style_contract("technical_doc")
    lowered = contract.lower()
    assert "problem statement" in lowered
    assert "implementation considerations" in lowered
    assert "open questions" in lowered
    assert "do not include an executive summary" in lowered
    assert "do not include a comparison table" in lowered
    assert "single decision section" in lowered


def test_unknown_output_style_raises():
    with pytest.raises(ValueError, match="Unknown output style"):
        build_output_style_contract("brochure")


def test_executive_brief_style_contract_mentions_short_decision_framing():
    contract = build_output_style_contract("executive_brief")
    lowered = contract.lower()
    assert "busy decision-maker" in lowered
    assert "headline recommendation" in lowered
    assert "key risks" in lowered


def test_decision_memo_style_contract_mentions_memo_sections():
    contract = build_output_style_contract("decision_memo")
    lowered = contract.lower()
    assert "decision memo" in lowered
    assert "recommended option" in lowered
    assert "consequences" in lowered


def test_output_style_contract_applies_boolean_overrides():
    contract = build_output_style_contract(
        "default",
        OutputStyleOverrides(
            include_executive_summary=False,
            include_comparison_table=True,
        ),
    )
    lowered = contract.lower()
    assert "do not include an executive summary" in lowered
    assert "include a comparison table" in lowered


def test_output_style_contract_applies_enum_overrides():
    contract = build_output_style_contract(
        "technical_doc",
        OutputStyleOverrides(
            recommendation_mode="decision_only",
            citation_mode="references_section",
        ),
    )
    lowered = contract.lower()
    assert "single decision section" in lowered
    assert "references section" in lowered


def test_output_style_contract_applies_section_toggles():
    contract = build_output_style_contract(
        "paper",
        OutputStyleOverrides(
            include_methodology=False,
            include_limitations=True,
            include_next_actions=True,
        ),
    )
    lowered = contract.lower()
    assert "do not include a standalone methodology section" in lowered
    assert "include a limitations section" in lowered
    assert "next actions section" in lowered


def test_output_style_contract_applies_section_order_override():
    contract = build_output_style_contract(
        "executive_brief",
        OutputStyleOverrides(section_order="recommendation_first"),
    )
    assert "lead with the recommendation before supporting evidence" in contract.lower()


def test_summarize_output_style_overrides_returns_human_readable_labels():
    summary = summarize_output_style_overrides(
        OutputStyleOverrides(
            include_executive_summary=False,
            include_methodology=True,
            include_next_actions=True,
            section_order="recommendation_first",
            recommendation_mode="decision_only",
            citation_mode="references_section",
        )
    )

    assert "no executive summary" in summary
    assert "include methodology section" in summary
    assert "include next actions" in summary
    assert "recommendation-first ordering" in summary
    assert "decision-only recommendations" in summary
    assert "references section" in summary


def test_paper_report_policy_hides_operational_sections():
    policy = build_output_style_report_policy("paper")

    assert policy["show_run_summary"] is False
    assert policy["show_dimensions"] is False
    assert policy["show_style_section"] is False
    assert policy["show_dashboard"] is False
    assert policy["show_retry"] is False
    assert policy["show_tool_usage"] is False
    assert policy["show_tool_trace"] is False


def test_technical_report_policy_hides_style_metadata_but_keeps_evidence_sections():
    policy = build_output_style_report_policy("technical_doc")

    assert policy["show_style_section"] is False
    assert policy["show_run_summary"] is False
    assert policy["show_dimensions"] is True
    assert policy["show_evidence_quality"] is True
    assert policy["show_rubric"] is True
