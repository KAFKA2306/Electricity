# 石油関連asset価格分析snapshot

> **状態: 過去に作成された探索的market-price分析です。現在の企業財務、投資適性、推奨銘柄を示すものではありません。**

このリポジトリは、原油先物、石油関連企業、商社、電力、海運、化学、航空、energy ETF、為替の価格系列をyfinanceから取得し、return・volatility・Sharpe ratio・correlation等を可視化した研究snapshotです。

## 現在確認できる構成

| パス | 役割 |
|---|---|
| `src/yf.py` | yfinanceからcloseを取得し、日本株をUSD/JPYでドル換算 |
| `src/stats.py` | return、volatility、Sharpe ratio、correlation、rolling指標を計算 |
| `data/oil.csv` | 過去に保存された価格data |
| `output/` | 過去に生成されたchart・report |

`src/yf.py`は2000年1月1日から実行時点までのデータ取得を試みます。ただし、committed dataや画像が現在まで更新されていること、同じ結果を再生成できることは確認していません。

## 分析対象

対象には次のような異なるinstrumentが混在します。

- WTI・Brent原油先物
- 米国・日本の石油関連企業
- 総合商社、電力、海運、化学、航空会社
- energy・oil service ETF
- USD/JPY

これは探索的比較用の集合であり、同一asset class・同一通貨・同一risk構造のcross-sectional universeではありません。

## 旧READMEの結論について

旧READMEは、特定企業のSharpe ratioや原油相関を固定値で示し、risk管理、事業多角化、安定性、投資適性まで解釈していました。これらは次の理由から、現在有効な企業評価や投資結論として使用できません。

- data as-ofと生成commitが明示されていない
- 価格系列だけでは財務、事業構成、hedge、規制、資本政策を識別できない
- Sharpe ratioのrisk-free rate、return頻度、欠損処理、評価期間が正準契約として固定されていない
- tickerの上場廃止、社名変更、株式分割、配当調整、survivorship biasをpoint-in-timeで管理していない
- 異なるasset classと通貨を単純比較している

したがって、旧READMEの固定数値と投資上の断定は撤回します。既存画像は過去の探索結果としてのみ扱ってください。

## データ処理上の制約

### yfinance

yfinanceは便利な研究用interfaceですが、企業・取引所・data vendorの公式開示そのものではありません。API応答、schema、価格補正、取得可能期間が変わる可能性があります。

### 為替換算

日本株のcloseを同日のUSD/JPY closeで除算しています。企業の報告通貨、海外売上、hedge、intraday timingを反映したeconomic exposureではありません。

### 欠損処理

取得後にforward fillを行います。休日が異なる市場間では、異なる時点の価格を同じ行で比較する可能性があります。

### financial analysisではない

repository名や旧READMEの表現にかかわらず、中心はmarket-price analysisです。財務諸表、cash flow、reserve、production、refining margin、hedge、debt等を統合した企業財務modelではありません。

## 現在できること

- 過去の価格分析codeと図表を研究履歴として確認する
- asset universeや指標候補を再設計する材料にする
- provenance・point-in-time設計が必要な箇所を把握する

## 現在できないこと

- 最新の原油・企業価格を保証する
- 現在の企業財務・事業品質を評価する
- 銘柄推奨、portfolio配分、risk管理効果を証明する
- 再現可能なperformance比較やbacktestを提供する

## 再開する場合の最低条件

1. instrument masterにticker、取引所、asset class、通貨、valid periodを保持する
2. raw dataへprovider、取得日時、timezone、adjustment、hashを付与する
3. return、volatility、Sharpe ratio、beta、correlationの数式と期間を固定する
4. market holidayとmissing data policyをtestする
5. survivorship biasとcorporate actionをpoint-in-timeで扱う
6. 企業財務を扱う場合は公式開示と価格dataを分離する
7. chartごとにdata as-of、code commit、設定hashを表示する
8. clean environmentからCIで再生成する

## 注意

このリポジトリのcode・data・画像・文章は投資助言ではありません。過去の相関やrisk-adjusted returnは将来のperformanceを保証しません。

**README監査日:** 2026-08-05
