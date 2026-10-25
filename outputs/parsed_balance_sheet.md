# 連結貸借対照表 (Parsed Output)

- **Unit**: 千円
- **Is Amended Filing**: True
- **Periods**: 2025-03-31, 2026-03-31
- **Verification**: PASS

## Verification Report

```text
=== Verification Report ===
Triplets   : PASS (8/8 passed)
Rollups    : PASS (12/12 within tolerance)
Structural : CLEAN (0 issues)
Overall    : PASS

Triplet details:
  [OK] 建物及び構築物 [2025-03-31]  gross=2,121,360  depr=-1,923,585  net_printed=197,775  net_computed=197,775  exact
  [OK] 建物及び構築物 [2026-03-31]  gross=1,880,082  depr=-1,640,253  net_printed=239,828  net_computed=239,829  drift=-1
  [OK] 機械装置及び運搬具 [2025-03-31]  gross=4,024,922  depr=-3,634,165  net_printed=390,757  net_computed=390,757  exact
  [OK] 機械装置及び運搬具 [2026-03-31]  gross=2,250,799  depr=-1,914,091  net_printed=336,708  net_computed=336,708  exact
  [OK] リース資産 [2025-03-31]  gross=210,746  depr=-147,599  net_printed=63,146  net_computed=63,147  drift=-1
  [OK] リース資産 [2026-03-31]  gross=213,939  depr=-172,066  net_printed=41,872  net_computed=41,873  drift=-1
  [OK] その他 [2025-03-31]  gross=848,814  depr=-840,375  net_printed=8,439  net_computed=8,439  exact
  [OK] その他 [2026-03-31]  gross=446,126  depr=-421,883  net_printed=24,243  net_computed=24,243  exact

Rollup details:
  [OK] 流動資産合計 [2025-03-31]  printed=5,863,684  computed=5,863,681  drift=+3  tolerance=±10
  [OK] 流動資産合計 [2026-03-31]  printed=3,377,407  computed=3,377,405  drift=+2  tolerance=±10
  [OK] 有形固定資産合計 [2025-03-31]  printed=1,429,094  computed=1,429,093  drift=+1  tolerance=±6
  [OK] 有形固定資産合計 [2026-03-31]  printed=1,352,610  computed=1,352,607  drift=+3  tolerance=±6
  [OK] 無形固定資産合計 [2025-03-31]  printed=44,261  computed=44,260  drift=+1  tolerance=±2
  [OK] 無形固定資産合計 [2026-03-31]  printed=35,869  computed=35,868  drift=+1  tolerance=±2
  [OK] 投資その他の資産合計 [2025-03-31]  printed=197,069  computed=197,068  drift=+1  tolerance=±5
  [OK] 投資その他の資産合計 [2026-03-31]  printed=369,362  computed=369,361  drift=+1  tolerance=±5
  [OK] 固定資産合計 [2025-03-31]  printed=1,670,426  computed=1,670,424  drift=+2  tolerance=±3
  [OK] 固定資産合計 [2026-03-31]  printed=1,757,841  computed=1,757,841  exact  tolerance=±3
  [OK] 資産合計 [2025-03-31]  printed=7,534,110  computed=7,534,110  exact  tolerance=±2
  [OK] 資産合計 [2026-03-31]  printed=5,135,249  computed=5,135,248  drift=+1  tolerance=±2
```

## Extracted Table

| Idx | Role | Indent | Account Label | Prior (2025-03-31) | Current (2026-03-31) | Hierarchy Path |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | SECTION_HEADER | 0 | 資産の部 | — | — | `資産の部` |
| 1 | SECTION_HEADER | 1 | &nbsp;&nbsp;流動資産 | — | — | `資産の部 > 流動資産` |
| 2 | LINE_ITEM | 2 | &nbsp;&nbsp;&nbsp;&nbsp;現金及び預金 | 2,002,429 | 608,281 | `資産の部 > 流動資産 > 現金及び預金` |
| 3 | LINE_ITEM | 2 | &nbsp;&nbsp;&nbsp;&nbsp;受取手形 | 20,659 | 26,333 | `資産の部 > 流動資産 > 受取手形` |
| 4 | LINE_ITEM | 2 | &nbsp;&nbsp;&nbsp;&nbsp;売掛金 | 2,019,476 | 884,339 | `資産の部 > 流動資産 > 売掛金` |
| 5 | LINE_ITEM | 2 | &nbsp;&nbsp;&nbsp;&nbsp;電子記録債権 | 564,667 | 370,468 | `資産の部 > 流動資産 > 電子記録債権` |
| 6 | LINE_ITEM | 2 | &nbsp;&nbsp;&nbsp;&nbsp;商品及び製品 | 589,488 | 1,019,663 | `資産の部 > 流動資産 > 商品及び製品` |
| 7 | LINE_ITEM | 2 | &nbsp;&nbsp;&nbsp;&nbsp;仕掛品 | 186,748 | 55,344 | `資産の部 > 流動資産 > 仕掛品` |
| 8 | LINE_ITEM | 2 | &nbsp;&nbsp;&nbsp;&nbsp;原材料及び貯蔵品 | 370,403 | 136,082 | `資産の部 > 流動資産 > 原材料及び貯蔵品` |
| 9 | LINE_ITEM | 2 | &nbsp;&nbsp;&nbsp;&nbsp;短期貸付金 | 7,530 | 30,000 | `資産の部 > 流動資産 > 短期貸付金` |
| 10 | LINE_ITEM | 2 | &nbsp;&nbsp;&nbsp;&nbsp;その他 | 105,260 | 246,895 | `資産の部 > 流動資産 > その他` |
| 11 | LINE_ITEM | 2 | &nbsp;&nbsp;&nbsp;&nbsp;貸倒引当金 | △2,979 | △0 *(△0)* | `資産の部 > 流動資産 > 貸倒引当金` |
| 12 | SUBTOTAL | 2 | &nbsp;&nbsp;&nbsp;&nbsp;流動資産合計 | 5,863,684 | 3,377,407 | `資産の部 > 流動資産 > 流動資産合計` |
| 13 | SECTION_HEADER | 1 | &nbsp;&nbsp;固定資産 | — | — | `資産の部 > 固定資産` |
| 14 | SECTION_HEADER | 2 | &nbsp;&nbsp;&nbsp;&nbsp;有形固定資産 | — | — | `資産の部 > 固定資産 > 有形固定資産` |
| 15 | GROSS_ITEM | 3 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;建物及び構築物 | 2,121,360 | 1,880,082 | `資産の部 > 固定資産 > 有形固定資産 > 建物及び構築物` |
| 16 | ACCUM_DEPR | 4 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;減価償却累計額 | △1,923,585 | △1,640,253 | `資産の部 > 固定資産 > 有形固定資産 > 建物及び構築物 > 減価償却累計額` |
| 17 | NET_ITEM | 4 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;建物及び構築物（純額） | 197,775 | 239,828 | `資産の部 > 固定資産 > 有形固定資産 > 建物及び構築物 > 建物及び構築物（純額）` |
| 18 | GROSS_ITEM | 3 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;機械装置及び運搬具 | 4,024,922 | 2,250,799 | `資産の部 > 固定資産 > 有形固定資産 > 機械装置及び運搬具` |
| 19 | ACCUM_DEPR | 4 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;減価償却累計額 | △3,634,165 | △1,914,091 | `資産の部 > 固定資産 > 有形固定資産 > 機械装置及び運搬具 > 減価償却累計額` |
| 20 | NET_ITEM | 4 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;機械装置及び運搬具（純額） | 390,757 | 336,708 | `資産の部 > 固定資産 > 有形固定資産 > 機械装置及び運搬具 > 機械装置及び運搬具（純額）` |
| 21 | LINE_ITEM | 3 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;土地 | 768,976 | 705,403 | `資産の部 > 固定資産 > 有形固定資産 > 土地` |
| 22 | GROSS_ITEM | 3 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;リース資産 | 210,746 | 213,939 | `資産の部 > 固定資産 > 有形固定資産 > リース資産` |
| 23 | ACCUM_DEPR | 4 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;減価償却累計額 | △147,599 | △172,066 | `資産の部 > 固定資産 > 有形固定資産 > リース資産 > 減価償却累計額` |
| 24 | NET_ITEM | 4 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;リース資産（純額） | 63,146 | 41,872 | `資産の部 > 固定資産 > 有形固定資産 > リース資産 > リース資産（純額）` |
| 25 | LINE_ITEM | 3 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;建設仮勘定 | － *(nil)* | 4,553 | `資産の部 > 固定資産 > 有形固定資産 > 建設仮勘定` |
| 26 | GROSS_ITEM | 3 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;その他 | 848,814 | 446,126 | `資産の部 > 固定資産 > 有形固定資産 > その他` |
| 27 | ACCUM_DEPR | 4 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;減価償却累計額 | △840,375 | △421,883 | `資産の部 > 固定資産 > 有形固定資産 > その他 > 減価償却累計額` |
| 28 | NET_ITEM | 4 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;その他（純額） | 8,439 | 24,243 | `資産の部 > 固定資産 > 有形固定資産 > その他 > その他（純額）` |
| 29 | SUBTOTAL | 3 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;有形固定資産合計 | 1,429,094 | 1,352,610 | `資産の部 > 固定資産 > 有形固定資産 > 有形固定資産合計` |
| 30 | SECTION_HEADER | 2 | &nbsp;&nbsp;&nbsp;&nbsp;無形固定資産 | — | — | `資産の部 > 固定資産 > 無形固定資産` |
| 31 | LINE_ITEM | 3 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;リース資産 | 34,190 | 21,402 | `資産の部 > 固定資産 > 無形固定資産 > リース資産` |
| 32 | LINE_ITEM | 3 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;その他 | 10,070 | 14,466 | `資産の部 > 固定資産 > 無形固定資産 > その他` |
| 33 | SUBTOTAL | 3 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;無形固定資産合計 | 44,261 | 35,869 | `資産の部 > 固定資産 > 無形固定資産 > 無形固定資産合計` |
| 34 | SECTION_HEADER | 2 | &nbsp;&nbsp;&nbsp;&nbsp;投資その他の資産 | — | — | `資産の部 > 固定資産 > 投資その他の資産` |
| 35 | LINE_ITEM | 3 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;投資有価証券 | 44,180 | **218,836** *(amended)* | `資産の部 > 固定資産 > 投資その他の資産 > 投資有価証券` |
| 36 | LINE_ITEM | 3 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;関係会社株式 | 1,123 | **1,123** *(amended)* | `資産の部 > 固定資産 > 投資その他の資産 > 関係会社株式` |
| 37 | LINE_ITEM | 3 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;長期貸付金 | － *(nil)* | 62,000 | `資産の部 > 固定資産 > 投資その他の資産 > 長期貸付金` |
| 38 | LINE_ITEM | 3 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;退職給付に係る資産 | 18,404 | 16,435 | `資産の部 > 固定資産 > 投資その他の資産 > 退職給付に係る資産` |
| 39 | LINE_ITEM | 3 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;その他 | 133,361 | 70,967 | `資産の部 > 固定資産 > 投資その他の資産 > その他` |
| 40 | SUBTOTAL | 3 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;投資その他の資産合計 | 197,069 | 369,362 | `資産の部 > 固定資産 > 投資その他の資産 > 投資その他の資産合計` |
| 41 | SUBTOTAL | 2 | &nbsp;&nbsp;&nbsp;&nbsp;固定資産合計 | 1,670,426 | 1,757,841 | `資産の部 > 固定資産 > 固定資産合計` |
| 42 | GRAND_TOTAL | 1 | &nbsp;&nbsp;資産合計 | 7,534,110 | 5,135,249 | `資産の部 > 資産合計` |
