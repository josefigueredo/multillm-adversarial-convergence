# Scientific Rigor Backlog

## Completed batches

### Batch R1A — search and screening logs

Tasks:
- [x] add TDD coverage for search log helper
- [x] add TDD coverage for screening log helper
- [x] wire provenance finalization to write:
  - `search_log.json`
  - `screening_log.json`
- [x] surface the new artifacts in reporting/docs
- [x] add dashboard/report summaries if useful

### Batch R2A — methodology expansion

Tasks:
- [x] extend `MethodologyConfig`
- [x] validate new fields from YAML
- [x] render new fields into `methods.md`
- [x] include them in manifest snapshots

## Current batch

### Batch R3A — reproducibility snapshots

Tasks:
- [x] snapshot prompt inputs per run
- [x] add rerun command artifact
- [x] decide whether raw backend outputs stay opt-in

### Batch R4A — certainty tables

Tasks:
- [x] define a conclusion-level certainty schema
- [x] map current provenance/evidence data into first-pass certainty factors
- [x] add `certainty_tables.json`
- [x] surface certainty summary in dashboard/reporting

## Next batch

### Batch R5A — raw backend output policy

Tasks:
- [x] decide whether raw backend outputs stay opt-in
- [x] add explicit config if raw capture becomes supported
- [x] document redaction/size constraints if raw capture is enabled

### Batch O1A — orchestrator cleanup

Tasks:
- [x] extract runtime telemetry aggregation helpers from `src/orchestrator.py`
- [x] extract reproducibility artifact writing helpers from `src/orchestrator.py`
- [x] keep orchestration flow focused on control logic, not artifact plumbing

### Batch O1B — provenance pipeline extraction

Tasks:
- [x] extract core provenance/evidence computation into a helper module
- [x] extract provenance artifact persistence/write sequencing fully out of `src/orchestrator.py`

### Batch O1C — report/export coordination extraction

Tasks:
- [x] extract dashboard/report/tool-trace/portfolio export coordination into a helper module
- [x] decide whether manifest/metrics writing should also move out of `src/orchestrator.py`

### Batch O1D — run metadata extraction

Tasks:
- [x] move manifest/metrics writing behind a shared helper module
- [x] decide whether agreement artifact writing should also move out of `src/orchestrator.py`

### Batch O1E — agreement artifact extraction

Tasks:
- [x] move agreement artifact persistence behind a shared helper module
- [x] decide whether evaluation artifact writing should also move out of `src/orchestrator.py`

### Batch O1F — evaluation artifact extraction

Tasks:
- [x] move evaluation/comparison/strategy-summary persistence behind a shared helper module

### Batch R4B — richer certainty reporting

Tasks:
- [x] surface factor-level certainty details in HTML/PDF summaries
- [x] add portfolio certainty deltas across runs
- [x] report high-certainty recommendation counts separately from total conclusion counts
