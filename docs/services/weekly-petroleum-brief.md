# Weekly Petroleum Stock Brief

## Purpose

This service turns the repository's verified U.S. Energy Information Administration (EIA) weekly petroleum stock snapshot into an auditable operational brief. It reports observed inventory changes only. It does **not** forecast prices, recommend securities, or provide investment advice.

## Canonical inputs and outputs

The builder uses only:

- `data/official/eia-weekly-stocks-*.json`: verified, immutable source snapshot
- `config/watchlists/*.json`: versioned watchlist and alert thresholds

Run:

```bash
python scripts/build_weekly_brief.py \
  --watchlist config/watchlists/weekly-petroleum-sample.json \
  --output build/weekly-brief
```

The command writes `brief.json`, `brief.md`, and `brief.html`. Every series record carries the stable series ID, observation date, official EIA source URL, source snapshot path, and snapshot SHA-256 through the brief-level provenance block.

For each configured series, the builder calculates:

- latest observed stock value
- change from the immediately preceding observation
- percentage change from the preceding observation when the denominator is non-zero
- difference between the latest value and the mean of the configured comparison window (sample: four observations)
- threshold-based alert reasons

Missing history, a zero denominator, an unknown series, or an invalid watchlist is never filled by estimation. Computations that cannot be performed are emitted as `NOT_COMPUTABLE` or fail closed when the configuration itself is invalid.

## Sample and PoC boundary

**Free sample**

- Repository watchlist example: `config/watchlists/weekly-petroleum-sample.json`
- CI-generated Markdown and HTML sample brief
- Existing static EIA API artifacts

**Potential four-week PoC**

- customer-selected series from the verified EIA inventory set
- customer-selected absolute and percentage thresholds
- selected delivery adapter after the core brief is generated
- auditable weekly brief history

No customer name, SLA, labor saving, forecast accuracy, paid-pilot count, or other commercial result is claimed until there is evidence for it.

## Calls to action

- **サンプルブリーフを見る:** run the command above or download the `weekly-petroleum-brief-sample` Actions artifact from a successful workflow run.
- **監視系列を相談する:** open a repository issue describing only the desired EIA series and alert conditions; do not include private business data.
- **4週間PoCを相談する:** open a repository issue describing the desired monitoring scope and delivery format; commercial or personal details should be exchanged outside the public repository.

## Evidence and source boundary

The source publisher is the **U.S. Energy Information Administration (EIA)**. The repository snapshot stores the official source URLs, confirmed observation period, confirmed release date, capture time, and the factual weekly stock observations used by the builder.

Official references:

- Weekly Petroleum Status Report: https://www.eia.gov/petroleum/supply/weekly/
- Weekly Petroleum Status Report schedule: https://www.eia.gov/petroleum/supply/weekly/schedule.php
- Commercial crude stocks: https://www.eia.gov/dnav/pet/PET_STOC_WSTK_A_EPC0_SAX_MBBL_W.htm

The value proposition is the monitoring configuration, deterministic calculations, alerts, delivery, and auditable history. It is not exclusive ownership of EIA source data.

## Commercial validation state

The product-demand metrics in Issue #4 remain validation targets, not achieved results. No repository value should convert an unmeasured event into zero or a successful customer outcome. Real outreach, qualified inquiries, demos, pilots, paid pilots, and continuation requests must be recorded only when supported by actual evidence.
