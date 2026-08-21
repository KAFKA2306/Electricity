# Repository Agent Contract

## Mission

Own official energy-supply observations for this repository, including petroleum and electricity supply/demand series already represented by the project. Convert official source releases into reproducible observations and stable derived views without turning scenarios or market commentary into facts.

## Canonical authority

- Prefer EIA and other official energy/statistical sources appropriate to each series.
- Preserve series identity, geography, period, release/observation time, unit, revision semantics, source URL, retrieval time and source hash where supported.
- Keep raw/official observations distinct from derived growth rates, forecasts, scenarios and investment implications.
- Other finance repositories should reference versioned energy artifacts here rather than maintain duplicate energy series.

## Autonomous execution

1. Inspect current `main`, README, open Issues/PRs, canonical datasets/manifests, workflows/tests and public outputs.
2. Resume one canonical workline before creating a new collector, schema, view, branch or Issue.
3. Prefer newly verified official observations, revision corrections, reproducible supply/demand comparisons, public read-back, then simplification.
4. Materialize and validate source evidence before downstream calculations.
5. Run the smallest relevant checks and verify reviewed/merged/public state when applicable.
6. Stop when the bounded data/capability is verified; if no new official release exists, do not manufacture repository activity.

## Boundaries

- Null is not zero; preliminary/revised/forecast/derived values must remain distinguishable.
- Do not infer missing production, inventory, generation, capacity, price or demand values.
- Do not execute commodity trades, derivatives, transfers or account actions.
- Unobserved external fetches, CI, deployment or market outcomes remain unverified.

## Completion report

Report verified observations/revisions Before -> After, primary source and canonical artifact, Issue/PR/commit/check/public evidence when applicable, manual work removed, and the remaining blocker.