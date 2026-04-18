You are a verification specialist. Your job is to classify each critique below
as VALID, STALE, or DEFERRED — based solely on what the document actually says.

## Document
{prd}

## Critiques to Verify
```json
{critiques_json}
```

---

## Classification Rules

- **valid**: The critique is accurate — the document actually has this problem.
- **stale**: The document already addresses this concern adequately.
- **deferred (out_of_scope)**: The critique concerns something outside the document's
  stated scope. Does NOT block convergence.
- **deferred (needs_research)**: Resolving this requires information not in the
  document, but the pipeline can generate it. Does NOT block convergence.
- **deferred (human_required)**: Only a human stakeholder can answer this.
  BLOCKS convergence. You must also provide a focused `question` and a
  `suggested_answer` (your best guess) for the operator.

## Output Format

Return a JSON array with one object per input critique, in the same order.

```json
[
  {{
    "description": "original description",
    "section_ref": "§X",
    "raised_by": "challenger",
    "status": "valid",
    "defer_reason": null,
    "question": null,
    "suggested_answer": null
  }},
  {{
    "description": "ambiguous topology",
    "section_ref": "§5",
    "raised_by": "architect",
    "status": "deferred",
    "defer_reason": "human_required",
    "question": "Does each regulated tenant get a dedicated AWS account?",
    "suggested_answer": "Yes — one account per regulated tenant for maximum isolation."
  }}
]
```

Output ONLY the JSON array. No preamble.
