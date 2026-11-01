# Agent fixtures (synthetic)

Small, **synthetic** records used by tests and by the offline API until the Data team's
`benchmark/` artefacts (issue #1) and the Ontology team's `ontology/lookups/` (issue #2) land.

- Lines are composed from common published Chola, Pallava and Pandya formulae (regnal-year
  openings, the perpetual-lamp grant, "as long as moon and sun", the Mahesvara protection
  clause). They are **not** DHARMA editions and carry `FIXTURE_*` ids and `example.invalid`
  URLs, so nothing derived from them can be mistaken for real benchmark numbers.
- Formats follow `contracts/benchmark-item.schema.json` and `contracts/ontology-lookup.schema.json`.
- No eval report may be computed from these files except as an explicitly labelled smoke test.
