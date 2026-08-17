# Oil — 石油在庫の変化を「読む」ための週次ブリーフ

[![EIA data integrity](https://github.com/KAFKA2306/oil/actions/workflows/eia-data.yml/badge.svg)](https://github.com/KAFKA2306/oil/actions/workflows/eia-data.yml)

**EIAの週次石油データを、監視対象・変化量・アラート・出所が1画面で分かるブリーフに変換します。**

原油や石油製品のデータは公開されていても、毎週必要なのは「全部の表」ではなく、**自分が見ている系列で何が動いたか**です。このリポジトリは、U.S. Energy Information Administration (EIA) の検証済みsnapshotから、設定した系列だけを抽出し、前週差・前週比・直近平均との差・閾値アラートを自動生成します。

## 顧客に返す価値

| やりたいこと | このリポジトリが返すもの |
|---|---|
| 毎週、大量の石油統計から重要な変化だけ見たい | watchlistに登録した系列だけを週次ブリーフ化 |
| 「増えた / 減った」だけでなく変化の大きさを比較したい | 最新値、前週差、前週比、設定期間平均との差 |
| 大きな変化を見落としたくない | 系列ごとの絶対値・変化率thresholdによるalert |
| 数字の出所を後から確認したい | EIA公式URL、観測日、snapshot、SHA-256を保持 |
| 人・システムの両方で使いたい | `brief.html` / `brief.md` / `brief.json` を同時生成 |

つまり、**「データを探す」ためのrepositoryではなく、「今週どこを見るべきか」を短くするためのrepository**です。

## こんな人向け

- 原油・石油製品の在庫変化を定点観測するリサーチ担当
- エネルギー関連企業や市場を追う投資・分析担当
- 公開データから定例レポートを作るデータ担当
- EIAデータを社内監視やdashboardへ組み込みたい開発者

## まず試す

```bash
python scripts/build_weekly_brief.py \
  --watchlist config/watchlists/weekly-petroleum-sample.json \
  --output build/weekly-brief
```

生成物:

```text
build/weekly-brief/
├── brief.html   # 人がそのまま読む
├── brief.md     # GitHub / Slack等へ転記しやすい
└── brief.json   # API・agent・dashboardへ渡しやすい
```

ブリーフでは各系列について次を計算します。

- 最新観測値
- 直前観測からの変化量
- 直前観測からの変化率
- 設定したcomparison window平均との差
- threshold超過の有無と理由
- EIA公式source URL

履歴不足・0除算・未知の系列などは推測で補完せず、計算不能として扱います。

## 自分用の監視に変える

`config/watchlists/*.json` で、監視したい系列とalert条件を設定できます。

```json
{
  "comparison_window": 4,
  "series": [
    {
      "id": "...",
      "label": "...",
      "absolute_change_threshold": 5000,
      "percentage_change_threshold": 2.0
    }
  ]
}
```

用途に応じて、**「何を見るか」と「どの変化を通知対象にするか」**をコード本体から分離できます。

## 現在、実装済みの範囲

GitHub Actions の `EIA data integrity` workflowでは、clean checkoutから次を検証しています。

- EIA由来の配布データ: **11系列 / 99観測**
- weekly brief sample: **7系列**
- snapshot SHA-256とfile hashの検証
- `brief.json` / `brief.md` / `brief.html` の生成
- 各brief系列のEIA公式URL保持
- unit test と smoke test

workflow: [`.github/workflows/eia-data.yml`](.github/workflows/eia-data.yml)

サービス仕様: [`docs/services/weekly-petroleum-brief.md`](docs/services/weekly-petroleum-brief.md)

## データの根拠

一次情報は **U.S. Energy Information Administration (EIA)** です。

- Weekly Petroleum Status Report: https://www.eia.gov/petroleum/supply/weekly/
- Release Schedule: https://www.eia.gov/petroleum/supply/weekly/schedule.php
- Petroleum & Other Liquids Data: https://www.eia.gov/petroleum/data.php
- EIA Open Data: https://www.eia.gov/opendata/

このrepositoryの価値はEIAデータそのものではなく、**監視対象の設定、決定的な差分計算、alert、共有形式、provenanceを一つの反復可能なworkflowにまとめること**です。

## 価格分析の研究資産

`src/` と `data/oil.csv` には、原油先物、石油関連企業、商社、電力、海運、化学、航空、energy ETF、為替を横断して、return・volatility・Sharpe ratio・correlation・rolling指標を比較する過去の探索コードも残しています。

これは現在の週次EIAブリーフとは別の研究資産です。特に `src/stats.py` では、原油との相関、risk-adjusted return、rolling correlation等を比較できます。

### 過去の探索図

以下は旧READMEで紹介していた探索的価格分析の図です。現在のEIA週次データや現在の投資判断を表すものではなく、過去の研究成果として保持します。

![4-Year Rolling Sharpe Ratio](output/4-year_rolling_sharpe_ratio.png)

![Correlation Heatmap of All Stocks](output/correlation_heatmap.png)

![4-Year Rolling Annual Returns](output/4-year_rolling_annual_returns.png)

![Rolling Correlation with Crude Oil Futures](output/rolling_correlation_with_crude_oil_futures.png)

![Stock Selection: Oil Correlation vs Sharpe Ratio](output/stock_selection_oil_correlation_vs_sharpe_ratio.png)

## 次に顧客仕様へ変えられる部分

現在のcoreは、監視系列とthresholdを外部設定にしています。そのため、PoCでは主に次を顧客ごとに変えられます。

1. 監視するEIA系列
2. alertの絶対値・変化率threshold
3. comparison window
4. HTML / Markdown / JSONの利用先
5. 生成後のdelivery adapter

監視したい系列や出力先がある場合は、[Issue](https://github.com/KAFKA2306/oil/issues/new) に公開可能な要件だけを書いてください。

## Scope

このrepositoryが直接観測・計算するのは、主にEIAの石油在庫系列とmarket-price研究データです。価格予測、企業財務の評価、証券の推奨は生成しません。過去の相関やrisk-adjusted returnを将来のperformance保証として扱わないでください。