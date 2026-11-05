# Editing the knowledge folder

For agronomists and developers. Everything under `knowledge/` is data, reviewed like code.

## Files
- `crops/<id>.yaml`: one crop. Climate limits are `[absolute min, optimum min, optimum max, absolute max]`.
  `rain_mm` means effective water supply (season rain plus stored soil water at sowing).
  `min_gap_same_family_seasons` overrides the default family gap for disease-prone crops.
- `rules/hard_rules.yaml`: rules that exclude an option (same-crop gap, family gap, exempt families).
- `rules/soft_rules.yaml`: score adjustments for soil and pest (effects are added to a 0.5 neutral base).
- `simulation/crop_sim_params.yaml`: crop coefficients, stage lengths, root depth, depletion fraction, yield response
  factor and sowing dates used by the deep-tier simulator.
- `regions/<id>.yaml`: bounding box, grid size, season windows and the weather years used for a district.
- `sources.yaml`, `CHANGELOG.md`: where each value comes from and who reviewed it.

## Review status
Every value is a placeholder until an agronomist fills `reviewed_by` in the crop file (and `status`/`reviewed_by` in the
simulation file). The engine reports `KNOWLEDGE_NOT_REVIEWED` in `notes` until then. Do not release to farmers before.

## After any change
1. `python scripts/validate_rules.py` (every crop needs simulation parameters and a sowing date for each of its seasons).
2. `pytest` (the scenario cases in `tests/scenarios/cases/` must still pass; add a case for the rule you changed).
3. Log the change and the reviewer in `knowledge/CHANGELOG.md`.

Editing `crops/` or `simulation/` changes `params_version`, and editing `rules/` changes `rules_version`. Both are part of
the cache key, so old simulation results are not reused after a change.

## Scenario cases
`tests/scenarios/cases/*.yaml`: a `request` and an `expect` block (`excluded_includes`, `first_crop_never`,
`confidence_at_most`, `needs_human_review`, `missing_includes`, `notes_include`, `any_option_reason`, `min_options`).
The target is 50-100 cases approved by the agronomists.
