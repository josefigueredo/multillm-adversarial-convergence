You are an expert technical arbitrator. Generate precise patch proposals
for each VALID critique listed below.

## Plan
{plan}

## Valid Critiques Requiring Patches
```json
{valid_critiques_json}
```

---

## Instructions

For each critique, propose a targeted text replacement that resolves the issue.
Keep patches minimal — only change what is necessary. Prefer adding steps or
clarifying existing ones over restructuring tasks.

Output ONLY a JSON array. No preamble.

```json
[
  {{
    "section_ref": "Task 3, Step 2",
    "proposed_text": "The exact replacement text for this step...",
    "rationale": "One sentence explaining why this patch resolves the critique."
  }}
]
```

If you cannot propose a patch for a critique, omit it from the array.
