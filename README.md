# Oil — EIA energy supply evidence

[![EIA data integrity](https://github.com/KAFKA2306/oil/actions/workflows/eia-data.yml/badge.svg)](https://github.com/KAFKA2306/oil/actions/workflows/eia-data.yml)
[![EIA electricity source](https://github.com/KAFKA2306/oil/actions/workflows/eia-electricity-source.yml/badge.svg)](https://github.com/KAFKA2306/oil/actions/workflows/eia-electricity-source.yml)

**EIA一次情報を、石油と電力を混ぜずに、再利用可能な証跡・viewへ変換します。**

## 正準データ

- Energy supply index: [`api/v1/energy-supply.json`](api/v1/energy-supply.json)
- Electricity index: [`api/v1/electricity/index.json`](api/v1/electricity/index.json)
- Demand: [`api/v1/electricity/demand.json`](api/v1/electricity/demand.json)
- Net generation: [`api/v1/electricity/generation.json`](api/v1/electricity/generation.json)
- Interchange: [`api/v1/electricity/interchange.json`](api/v1/electricity/interchange.json)
- Generation mix: [`api/v1/electricity/generation-mix.json`](api/v1/electricity/generation-mix.json)
- Generator capacity: [`api/v1/electricity/capacity.json`](api/v1/electricity/capacity.json)
- Planned / retired capacity: [`api/v1/electricity/capacity-additions.json`](api/v1/electricity/capacity-additions.json)
- Petroleum latest: [`api/v1/latest.json`](api/v1/latest.json)

電力は EIA U.S. Electric System Operating Data のhourly actualからUTC日次・週次を生成し、EIA-860MからOperating / Planned / Retired generator capacityを取得します。raw evidenceはsource URL・SHA-256・取得時刻とともに `data/electricity/official/` へ保存します。forecastはactualへ混ぜません。

`api/v1/energy-supply.json` はpetroleumとelectricityの参照先だけを結びます。barrels / bpd / MW / MWh等の値やunitを同じtableへ混ぜません。

## 石油週次ブリーフ

EIAの週次石油snapshotから、watchlist対象について最新値、前週差、前週比、比較期間平均との差、threshold alert、EIA公式source URLを生成します。

```bash
python scripts/build_weekly_brief.py \
  --watchlist config/watchlists/weekly-petroleum-sample.json \
  --output build/weekly-brief
```

生成物:

```text
build/weekly-brief/
├── brief.html
├── brief.md
└── brief.json
```

監視系列とalert条件は `config/watchlists/*.json` に分離しています。履歴不足、0除算、未知系列は推測で補完せず計算不能として扱います。

## 検証と運用

`EIA data integrity` はclean checkoutで既存petroleum distribution・weekly brief・unit testsと、live electricity sourceを検証します。

`EIA electricity source` は日次でEIA公式sourceを取得し、90日以上のactual demand / generation / interchange、generation by fuel、Operating / Planned / Retired capacity、daily / weekly view、provenanceを検証して変更時だけcommitします。

- Integrity workflow: [`.github/workflows/eia-data.yml`](.github/workflows/eia-data.yml)
- Electricity refresh: [`.github/workflows/eia-electricity-source.yml`](.github/workflows/eia-electricity-source.yml)
- Petroleum service: [`docs/services/weekly-petroleum-brief.md`](docs/services/weekly-petroleum-brief.md)

## 一次情報

- EIA Open Data: https://www.eia.gov/opendata/
- EIA bulk downloads: https://www.eia.gov/opendata/bulkfiles.php
- EIA-860M: https://www.eia.gov/electricity/data/eia860m/
- Weekly Petroleum Status Report: https://www.eia.gov/petroleum/supply/weekly/

## 価格分析の研究資産

`src/` と `data/oil.csv` には、原油先物、石油関連企業、商社、電力、海運、化学、航空、energy ETF、為替の過去の探索コードがあります。これはEIA一次情報datasetとは別レイヤーで、価格予測や証券推奨の正準データにはしません。

![4-Year Rolling Sharpe Ratio](output/4-year_rolling_sharpe_ratio.png)

![Correlation Heatmap of All Stocks](output/correlation_heatmap.png)

![4-Year Rolling Annual Returns](output/4-year_rolling_annual_returns.png)

![Rolling Correlation with Crude Oil Futures](output/rolling_correlation_with_crude_oil_futures.png)

![Stock Selection: Oil Correlation vs Sharpe Ratio](output/stock_selection_oil_correlation_vs_sharpe_ratio.png)
