You are an expert technical arbitrator. Your job is to generate precise patch
proposals for each VALID critique listed below.

## Document
{prd}

## Valid Critiques Requiring Patches
```json
{valid_critiques_json}
```

---

## Instructions

For each critique, propose a targeted text replacement that resolves the issue
without altering unrelated sections. Keep patches minimal and focused.

Output ONLY a JSON array. No preamble.

```json
[
  {{
    "section_ref": "§3",
    "proposed_text": "The exact replacement text for this section...",
    "rationale": "One sentence explaining why this patch resolves the critique."
  }}
]
```

If you cannot propose a patch for a critique, omit it from the array.
