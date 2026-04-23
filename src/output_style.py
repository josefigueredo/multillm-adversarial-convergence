"""Run-mode synthesis output style contracts."""

from __future__ import annotations

VALID_OUTPUT_STYLES = (
    "default",
    "paper",
    "technical_doc",
    "executive_brief",
    "decision_memo",
)


def summarize_output_style_overrides(overrides: object | None) -> list[str]:
    """Return compact human-readable labels for active style overrides."""
    if overrides is None:
        return []

    summary: list[str] = []
    include_executive_summary = getattr(overrides, "include_executive_summary", None)
    include_comparison_table = getattr(overrides, "include_comparison_table", None)
    include_methodology = getattr(overrides, "include_methodology", None)
    include_limitations = getattr(overrides, "include_limitations", None)
    include_next_actions = getattr(overrides, "include_next_actions", None)
    section_order = getattr(overrides, "section_order", "")
    recommendation_mode = getattr(overrides, "recommendation_mode", "")
    citation_mode = getattr(overrides, "citation_mode", "")

    if include_executive_summary is False:
        summary.append("no executive summary")
    elif include_executive_summary is True:
        summary.append("force executive summary")

    if include_comparison_table is False:
        summary.append("no comparison table")
    elif include_comparison_table is True:
        summary.append("include comparison table")

    if include_methodology is False:
        summary.append("no methodology section")
    elif include_methodology is True:
        summary.append("include methodology section")

    if include_limitations is False:
        summary.append("no limitations section")
    elif include_limitations is True:
        summary.append("include limitations section")

    if include_next_actions is False:
        summary.append("no next actions section")
    elif include_next_actions is True:
        summary.append("include next actions")

    if section_order == "recommendation_first":
        summary.append("recommendation-first ordering")
    elif section_order == "evidence_first":
        summary.append("evidence-first ordering")
    elif section_order == "standard":
        summary.append("standard ordering")

    if recommendation_mode == "decision_only":
        summary.append("decision-only recommendations")
    elif recommendation_mode == "ranked":
        summary.append("ranked recommendations")

    if citation_mode == "references_section":
        summary.append("references section")
    elif citation_mode == "inline_links":
        summary.append("inline links")

    return summary


def build_output_style_presentation(style: str) -> dict[str, str]:
    """Return presentation-facing labels for the selected run output style."""
    if style == "default":
        return {
            "style_label": "Default Style",
            "methods_heading": "Methods",
            "synthesis_heading": "Synthesis",
            "pdf_title_suffix": "",
        }
    if style == "paper":
        return {
            "style_label": "Paper Style",
            "methods_heading": "Methodology",
            "synthesis_heading": "Paper Draft",
            "pdf_title_suffix": " (Paper Style)",
        }
    if style == "technical_doc":
        return {
            "style_label": "Technical Documentation Style",
            "methods_heading": "Technical Approach",
            "synthesis_heading": "Technical Document",
            "pdf_title_suffix": " (Technical Documentation)",
        }
    if style == "executive_brief":
        return {
            "style_label": "Executive Brief",
            "methods_heading": "Approach",
            "synthesis_heading": "Executive Brief",
            "pdf_title_suffix": " (Executive Brief)",
        }
    if style == "decision_memo":
        return {
            "style_label": "Decision Memo",
            "methods_heading": "Decision Context",
            "synthesis_heading": "Decision Memo",
            "pdf_title_suffix": " (Decision Memo)",
        }
    raise ValueError(f"Unknown output style: {style}")


def build_output_style_contract(style: str, overrides: object | None = None) -> str:
    """Return prompt instructions for the requested synthesis output style."""
    include_executive_summary = getattr(overrides, "include_executive_summary", None)
    include_comparison_table = getattr(overrides, "include_comparison_table", None)
    include_methodology = getattr(overrides, "include_methodology", None)
    include_limitations = getattr(overrides, "include_limitations", None)
    include_next_actions = getattr(overrides, "include_next_actions", None)
    section_order = getattr(overrides, "section_order", "")
    recommendation_mode = getattr(overrides, "recommendation_mode", "")
    citation_mode = getattr(overrides, "citation_mode", "")
    if style == "default":
        base = (
            "Use the standard decision-support report structure.\n"
            "- Start with an executive summary.\n"
            "- Include a comparison table when multiple options are evaluated.\n"
            "- Emphasize trade-offs, decision criteria, and ranked recommendations.\n"
            "- Close with gaps, unresolved questions, and confidence framing."
        )
    elif style == "paper":
        base = (
            "Use a formal paper-style structure.\n"
            "- Include sections resembling: Abstract, Research Question, Methodology, Findings, Discussion, Limitations, Conclusion.\n"
            "- Prefer formal analytical prose over imperative recommendation language.\n"
            "- Make limitations and evidence quality explicit."
        )
    elif style == "technical_doc":
        base = (
            "Use an internal technical documentation structure.\n"
            "- Include sections resembling: Context, Problem Statement, Options Considered, Technical Analysis, Decision, Implementation Considerations, Risks, Open Questions.\n"
            "- Prefer direct, implementation-oriented language.\n"
            "- Keep recommendations actionable for engineering teams."
        )
    elif style == "executive_brief":
        base = (
            "Use an executive-brief structure for a busy decision-maker.\n"
            "- Lead with a headline recommendation and the reasoning in a few high-signal paragraphs.\n"
            "- Keep sections compact: Recommendation, Why Now, Key Trade-offs, Key Risks, Next Actions.\n"
            "- Optimize for clarity, brevity, and fast decision support rather than exhaustive discussion."
        )
    elif style == "decision_memo":
        base = (
            "Use a decision memo structure.\n"
            "- Include sections resembling: Context, Decision to Make, Options, Recommended Option, Rationale, Consequences, Risks, Follow-up Questions.\n"
            "- Make the recommended option explicit and justified.\n"
            "- Emphasize trade-offs, consequences, and decision ownership."
        )
    else:
        raise ValueError(f"Unknown output style: {style}")

    extra: list[str] = []
    if include_executive_summary is False:
        extra.append("- Do not include an executive summary.")
    elif include_executive_summary is True:
        extra.append("- Include an executive summary even if the selected style would normally omit it.")

    if include_comparison_table is False:
        extra.append("- Do not include a comparison table.")
    elif include_comparison_table is True:
        extra.append("- Include a comparison table when more than one option is discussed.")

    if include_methodology is False:
        extra.append("- Do not include a standalone Methodology section.")
    elif include_methodology is True:
        extra.append("- Include a Methodology section even if the selected style would normally keep methods implicit.")

    if include_limitations is False:
        extra.append("- Do not include a standalone Limitations section.")
    elif include_limitations is True:
        extra.append("- Include a Limitations section explicitly.")

    if include_next_actions is False:
        extra.append("- Do not include a Next Actions section.")
    elif include_next_actions is True:
        extra.append("- Include a Next Actions section with concrete follow-up steps.")

    if section_order == "recommendation_first":
        extra.append("- Lead with the recommendation before supporting evidence and detail.")
    elif section_order == "evidence_first":
        extra.append("- Present evidence and findings before stating the recommendation.")
    elif section_order == "standard":
        extra.append("- Use the standard section ordering implied by the selected style.")

    if recommendation_mode == "decision_only":
        extra.append("- Collapse recommendations into a single Decision section instead of ranked recommendation bullets.")
    elif recommendation_mode == "ranked":
        extra.append("- Present recommendations as a ranked list with explicit confidence.")

    if citation_mode == "references_section":
        extra.append("- In addition to inline citations where useful, include a dedicated References section collecting cited sources.")
    elif citation_mode == "inline_links":
        extra.append("- Prefer inline markdown links as the primary citation style instead of a separate references list.")

    return base if not extra else f"{base}\n" + "\n".join(extra)
