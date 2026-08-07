# EIA petroleum data API v1

`data/official/` は、U.S. Energy Information Administration (EIA) の公式公開表から確認した事実データを、取得時点のprovenance付きsnapshotとして保存します。既存の `data/oil.csv` と yfinance 系コードは過去の探索分析として残し、この公式データ層とは混ぜません。

## 現在の収録範囲

- publisher: U.S. Energy Information Administration (EIA)
- frequency: weekly
- unit: thousand barrels
- verified periods: 2026-06-12 through 2026-07-17
- series: 11
- observations: 66
- official sources:
  - https://www.eia.gov/dnav/pet/PET_STOC_WSTK_A_EPC0_SAX_MBBL_W.htm
  - https://www.eia.gov/dnav/pet/pet_stoc_wstk_dcu_nus_w.htm

`latest_period_confirmed` は、このリポジトリが取得時に公式表で確認できた最新periodであり、「現在のEIAサイトにさらに新しい値が存在しない」ことを保証する値ではありません。更新時は必ず公式表を再確認し、新snapshotを追加してください。旧snapshotは削除せず履歴として残します。

## 配布物

`python scripts/build_eia_api.py --output api/v1` は次を決定的に生成します。

- `series.json`: series master。stable ID、area、frequency、unit、source URL、収録期間、観測数。
- `latest.json`: 各seriesの最新確認値。
- `observations.csv`: long-format observations。`series_id, title, area, period, value, unit`。
- `manifest.json`: source snapshot、件数、byte数、SHA-256、cache hint。

GitHub Actionsは同じbuilderをclean environmentで実行し、JSON/CSV件数とchecksumを検証した上で `eia-petroleum-api-v1` artifactを30日保存します。

## 取得例

mainへmerge後、最新値はraw GitHubから直接取得できます。

```bash
curl -fsSL https://raw.githubusercontent.com/KAFKA2306/oil/main/api/v1/latest.json
```

生成artifactを利用する場合は `manifest.json` を先に読み、SHA-256が変わったファイルだけ再取得してください。

## 欠損・改定・更新方針

- EIA側の `NA`、`W` 等を将来取り込む場合、0へ置換せずnull/quality flagで表現します。
- 過去値の改定を検出した場合、旧snapshotを削除せず新snapshotを追加します。
- 外部取得をCIの毎PRに強制しません。公式サイトへの不要な負荷を避け、更新処理と検証処理を分離します。
- API v1の既存fieldは削除・意味変更しません。破壊的変更はv2へ送ります。

## 利用上の注意

EIAの定義、注記、改定、利用条件は公式ページを正準とします。本リポジトリは投資助言ではなく、出典付きデータ配布・研究用の補助基盤です。
