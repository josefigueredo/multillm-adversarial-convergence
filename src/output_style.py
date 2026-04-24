"""Run-mode synthesis output style contracts."""

from __future__ import annotations

VALID_OUTPUT_STYLES = (
    "default",
    "paper",
    "technical_doc",
    "executive_brief",
    "decision_memo",
)


def _style_defaults(style: str) -> dict[str, object]:
    """Return opinionated defaults for a given output style profile."""
    if style == "default":
        return {}
    if style == "paper":
        return {
            "include_executive_summary": False,
            "include_comparison_table": False,
            "include_methodology": True,
            "include_limitations": True,
            "include_next_actions": False,
            "section_order": "evidence_first",
            "recommendation_mode": "decision_only",
            "citation_mode": "references_section",
        }
    if style == "technical_doc":
        return {
            "include_executive_summary": False,
            "include_comparison_table": False,
            "include_methodology": False,
            "include_limitations": False,
            "include_next_actions": False,
            "section_order": "standard",
            "recommendation_mode": "decision_only",
            "citation_mode": "inline_links",
        }
    if style == "executive_brief":
        return {
            "include_executive_summary": True,
            "include_comparison_table": False,
            "include_methodology": False,
            "include_limitations": False,
            "include_next_actions": True,
            "section_order": "recommendation_first",
            "recommendation_mode": "decision_only",
            "citation_mode": "inline_links",
        }
    if style == "decision_memo":
        return {
            "include_executive_summary": False,
            "include_comparison_table": False,
            "include_methodology": False,
            "include_limitations": False,
            "include_next_actions": True,
            "section_order": "recommendation_first",
            "recommendation_mode": "decision_only",
            "citation_mode": "inline_links",
        }
    raise ValueError(f"Unknown output style: {style}")


def _resolve_style_overrides(style: str, overrides: object | None) -> dict[str, object]:
    """Merge style profile defaults with optional user overrides."""
    resolved = dict(_style_defaults(style))
    fields = (
        "include_executive_summary",
        "include_comparison_table",
        "include_methodology",
        "include_limitations",
        "include_next_actions",
        "section_order",
        "recommendation_mode",
        "citation_mode",
    )
    if overrides is None:
        return resolved
    for field in fields:
        value = getattr(overrides, field, None)
        if value is None or value == "":
            continue
        resolved[field] = value
    return resolved


def build_output_style_report_policy(style: str) -> dict[str, bool]:
    """Return report rendering visibility rules for the selected style."""
    base = {
        "show_run_summary": True,
        "show_dimensions": True,
        "show_style_section": True,
        "show_methods": True,
        "show_synthesis": True,
        "show_evidence_quality": True,
        "show_rubric": True,
        "show_semantic": True,
        "show_semantic_review": True,
        "show_certainty": True,
        "show_search_screening": True,
        "show_retry": True,
        "show_tool_usage": True,
        "show_tool_trace": True,
        "show_dashboard": True,
        "show_evaluation": True,
        "show_comparison": True,
    }
    if style == "paper":
        base.update(
            {
                "show_run_summary": False,
                "show_dimensions": False,
                "show_style_section": False,
                "show_semantic": False,
                "show_semantic_review": False,
                "show_retry": False,
                "show_tool_usage": False,
                "show_tool_trace": False,
                "show_dashboard": False,
                "show_evaluation": False,
                "show_comparison": False,
            }
        )
        return base
    if style == "technical_doc":
        base.update(
            {
                "show_run_summary": False,
                "show_style_section": False,
                "show_retry": False,
                "show_tool_usage": False,
                "show_tool_trace": False,
                "show_dashboard": False,
            }
        )
        return base
    if style in VALID_OUTPUT_STYLES:
        return base
    raise ValueError(f"Unknown output style: {style}")


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


def build_output_style_theme(style: str) -> dict[str, str]:
    """Return HTML/CSS theming metadata for the selected run output style."""
    if style == "paper":
        return {
            "report_class": "report report-paper",
            "style_css": (
                '.report-paper { font-family: Georgia, "Times New Roman", serif; max-width: 820px; color: #222222; }\n'
                ".report-paper header { border-bottom: 1px solid #d6d0c4; margin-bottom: 2rem; padding-bottom: 1rem; }\n"
                ".report-paper .subtitle { font-style: italic; letter-spacing: 0.02em; }\n"
                ".report-paper .meta { font-size: 0.92rem; color: #5d564f; }\n"
                ".report-paper .toc { background: #fffdf9; border: 1px solid #e2dbd0; box-shadow: none; }\n"
                ".report-paper .markdown-body { font-size: 1.03rem; line-height: 1.72; }\n"
                ".report-paper .markdown-body h1, .report-paper .markdown-body h2, .report-paper .markdown-body h3 { font-family: Georgia, \"Times New Roman\", serif; }\n"
                ".report-paper .markdown-body h1 { border-bottom: 2px solid #d6d0c4; }\n"
                ".report-paper .markdown-body h2 { border-bottom: 1px solid #e2dbd0; }\n"
                ".report-paper .markdown-body table { font-size: 0.96rem; }\n"
                ".report-paper .markdown-body th { background: #f7f2ea; }\n"
                ".report-paper pre, .report-paper code { font-family: \"SFMono-Regular\", Consolas, monospace; }\n"
            ),
        }
    if style == "technical_doc":
        return {
            "report_class": "report report-technical_doc",
            "style_css": (
                ".report-technical_doc { font-family: Inter, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif; max-width: none; color: #172033; background: #f5f7fb; }\n"
                ".report-technical_doc .page-shell { max-width: 1180px; margin: 0 auto; padding: 1.5rem 1.5rem 3rem; display: grid; grid-template-columns: minmax(0, 1fr); gap: 1.25rem; }\n"
                ".report-technical_doc header { background: #ffffff; border: 1px solid #dbe4f0; border-radius: 14px; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06); margin-bottom: 0.25rem; padding: 1.25rem 1.5rem; }\n"
                ".report-technical_doc .subtitle { font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: #3d5a80; font-size: 0.82rem; }\n"
                ".report-technical_doc .meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.6rem 1rem; font-size: 0.95rem; }\n"
                ".report-technical_doc .toc { background: #ffffff; border: 1px solid #dbe4f0; border-radius: 14px; box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05); }\n"
                ".report-technical_doc section { margin-bottom: 0; background: #ffffff; border: 1px solid #dbe4f0; border-radius: 14px; box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04); padding: 1.1rem 1.25rem; }\n"
                ".report-technical_doc section > h2 { margin-top: 0; }\n"
                ".report-technical_doc .markdown-body h1, .report-technical_doc .markdown-body h2 { font-family: Inter, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif; }\n"
                ".report-technical_doc .markdown-body h1 { border-bottom: 2px solid #c8d5e6; margin-top: 0.25rem; }\n"
                ".report-technical_doc .markdown-body h2 { border-bottom: 1px solid #dbe4f0; }\n"
                ".report-technical_doc .markdown-body table { font-size: 0.95rem; }\n"
                ".report-technical_doc .markdown-body th { background: #eef4fb; }\n"
                ".report-technical_doc .markdown-body blockquote { background: #f8fbff; border-left: 4px solid #7aa2d6; border-radius: 0 10px 10px 0; }\n"
                ".report-technical_doc pre { border-left: 4px solid #7aa2d6; background: #f6f9fc; border-radius: 10px; }\n"
            ),
        }
    if style in VALID_OUTPUT_STYLES:
        return {
            "report_class": f"report report-{style}",
            "style_css": "",
        }
    raise ValueError(f"Unknown output style: {style}")


def build_output_style_contract(style: str, overrides: object | None = None) -> str:
    """Return prompt instructions for the requested synthesis output style."""
    effective = _resolve_style_overrides(style, overrides)
    include_executive_summary = effective.get("include_executive_summary", None)
    include_comparison_table = effective.get("include_comparison_table", None)
    include_methodology = effective.get("include_methodology", None)
    include_limitations = effective.get("include_limitations", None)
    include_next_actions = effective.get("include_next_actions", None)
    section_order = effective.get("section_order", "")
    recommendation_mode = effective.get("recommendation_mode", "")
    citation_mode = effective.get("citation_mode", "")
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
            "- Make limitations and evidence quality explicit.\n"
            "- Follow scholarly conventions: let the abstract and findings carry the narrative, keep operational metadata out of the main body, and end with references."
        )
    elif style == "technical_doc":
        base = (
            "Use an internal technical documentation structure.\n"
            "- Include sections resembling: Context, Problem Statement, Options Considered, Technical Analysis, Decision, Implementation Considerations, Risks, Open Questions.\n"
            "- Prefer direct, implementation-oriented language.\n"
            "- Keep recommendations actionable for engineering teams.\n"
            "- Follow engineering-document conventions: avoid academic framing, prefer explicit decisions, and keep operational details only when they support implementation."
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
