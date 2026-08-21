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
5. Run the smallest relevant checks and verify the exact reviewed revision before merge.
6. Stop when the bounded data/capability is verified; if no new official release exists, do not manufacture repository activity.

## Branch lifecycle

- Aside from the default branch and unavoidable platform-managed/protected branches, a persistent branch is permitted only while it is the head branch of a currently open PR.
- Creating a work branch creates an obligation to open or reuse its canonical PR immediately; do not use branches as backlog, continuation state, backup, archive, or evidence storage.
- After a PR is merged or closed, delete its head branch after verifying PR/main state. A branch with no open PR is an orphan and must be deleted.
- Before and after work, compare repository branches with open PR heads. Do not report cleanup/fixed point while an orphan task branch remains.
- If the available tool cannot delete a branch, record that as a tooling blocker and do not claim cleanup complete. Never create another orphan branch as a workaround.

## Merge and release are separate

### PR merge conditions

A PR may merge when the repository-local energy data contract is correct on the exact head revision: source/series/period/unit semantics are preserved, deterministic tests/audits pass, generated artifacts are reproducible where affected, and no unresolved review or correctness blocker remains.

A future EIA release, post-merge live fetch, public deployment, or market outcome is **not** a merge condition unless the PR specifically changes the release mechanism and pre-merge validation belongs to the bounded change.

### Product/data release conditions

Release is a separate post-merge decision. Treat energy data/views as released only after the merged `main` revision is read back and the release surfaces in scope are actually verified, including fresh official observations when required, published artifacts/API/UI, deployment identity, and rollback/rebuild path where applicable.

A merged PR does not prove a new official release was acquired or published. A release/source blocker may block release without invalidating a correctly merged repository change. Report merge and release independently.

## Boundaries

- Null is not zero; preliminary/revised/forecast/derived values must remain distinguishable.
- Do not infer missing production, inventory, generation, capacity, price or demand values.
- Do not execute commodity trades, derivatives, transfers or account actions.
- Unobserved external fetches, CI, deployment or market outcomes remain unverified.

## Completion report

Report verified observations/revisions Before -> After, primary source and canonical artifact, Issue/PR/commit/check evidence, then report `merged` and `released` separately with direct evidence for each. Include branch cleanup state, manual work removed and the remaining blocker.