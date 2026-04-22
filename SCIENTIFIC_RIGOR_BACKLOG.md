# Scientific Rigor Backlog

## Current batch

### Batch R1A — search and screening logs

Tasks:
- [x] add TDD coverage for search log helper
- [x] add TDD coverage for screening log helper
- [x] wire provenance finalization to write:
  - `search_log.json`
  - `screening_log.json`
- [ ] surface the new artifacts in reporting/docs
- [ ] add dashboard/report summaries if useful

## Next batch

### Batch R2A — methodology expansion

Tasks:
- [ ] extend `MethodologyConfig`
- [ ] validate new fields from YAML
- [ ] render new fields into `methods.md`
- [ ] include them in manifest snapshots

### Batch R3A — reproducibility snapshots

Tasks:
- [ ] snapshot prompt inputs per run
- [ ] add rerun command artifact
- [ ] decide whether raw backend outputs stay opt-in

### Batch R4A — certainty tables

Tasks:
- [ ] define a conclusion-level certainty schema
- [ ] map current provenance/evidence data into first-pass certainty factors
- [ ] add `certainty_tables.json`
