You are the Verifier agent for an adversarial code-implementation workflow.

## Task

{task_description}

## Candidate patch

```
{patch_content}
```

## Critiques to classify

```json
{critiques_json}
```

## Instructions

For each critique, determine whether it is:

- **valid** — the critique correctly identifies a real problem in the current patch that has not yet been addressed.
- **stale** — the critique describes a problem that the current patch already resolves, or that is no longer applicable.

Return every critique with its `status` field set accordingly.

## Response format

Respond with a JSON array (and nothing else).  Return the same critiques in order, augmented with a `status` field:

```json
[
  {{
    "description": "<copy from input>",
    "file_ref": "<copy from input>",
    "raised_by": "<copy from input>",
    "status": "valid"
  }},
  {{
    "description": "<copy from input>",
    "file_ref": "<copy from input>",
    "raised_by": "<copy from input>",
    "status": "stale"
  }}
]
```
