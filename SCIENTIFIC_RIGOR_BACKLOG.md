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
- [ ] decide whether raw backend outputs stay opt-in

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
- [ ] add explicit config if raw capture becomes supported
- [x] document redaction/size constraints if raw capture is enabled

### Batch O1A — orchestrator cleanup

Tasks:
- [ ] extract runtime telemetry aggregation helpers from `src/orchestrator.py`
- [ ] extract reproducibility artifact writing helpers from `src/orchestrator.py`
- [ ] keep orchestration flow focused on control logic, not artifact plumbing

### Batch R4B — richer certainty reporting

Tasks:
- [ ] surface factor-level certainty details in HTML/PDF summaries
- [ ] add portfolio certainty deltas across runs
- [ ] report high-certainty recommendation counts separately from total conclusion counts
