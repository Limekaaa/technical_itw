# Analysis Index — Multimodal Athletic Monitoring Audit

_Generated 2026-09-17 10:50._

| File | Contents |
|---|---|
| `phase1_schema_audit.md` | Phase 1: inventory, Schema Integrity Matrix, Temporal Alignment & Horizon Table |
| `phase2a_fitbit.md` | Phase 2A: minute missingness, non-wear, daily distributions, HR/RHR/zones, sleep architecture |
| `phase2b_subjective.md` | Phase 2B: adherence/cadence, Likert & ceiling effects, intra/inter variance, sRPE monotony/strain, weight, alcohol |
| `phase2c_food_injury.md` | Phase 2C: EXIF/format audit, data-derived 15 s meal threshold + vision validation, injury epidemiology + 1,000 h incidence + class imbalance |
| `phase3_preprocessing_modeling.md` | Phase 3: cleaning checklist, day-grain alignment, feature catalogue, model spec, risks |
| `tables/*.csv` | All machine-readable audit tables (prefix `phase1_*`, `phase2a_*`, `phase2b_*`, `phase2c_*`) |
| `audit_full.py` | Reproducible generator for this whole folder (run `.venv/bin/python analysis/audit_full.py`) |
| `findings.md` | Pre-existing basic report (kept for provenance; superseded by phase files above) |
| `analyze_all.py` | Pre-existing basic generator (kept; not used by this audit) |
