# Financial Table Extraction: Failure-Mode Evaluation Benchmark

> **Core R&D Finding**: Standard OCR/table metrics (like flat cell accuracy, BLEU, or naive TEDS) report **>97% accuracy** on models with critical accounting corruption (e.g. inverted signs, shifted columns, or lost section hierarchy). Combining **Strict Relational Relational Tuple Matching** with an **Intrinsic Accounting Verifier** exposes 100% of these failure modes.

| Scenario | Naive Flat Acc | Strict Tuple F1 | Numeric Val F1 | Hierarchy Acc | GAAP Semantic Acc | Accounting Verifier |
| --- | --- | --- | --- | --- | --- | --- |
| **Hybrid Anchor Parser (Ours)** | 100.0% | **100.0%** | 100.0% | 100.0% | 100.0% | **PASS** |
| **Mutation 1: Dropped △ Sign** | 98.6% | **98.6%** | 98.6% | 100.0% | 100.0% | **FAIL** (1) |
| **Mutation 2: Nil Cell Shift** | 98.6% | **96.6%** | 96.6% | 100.0% | 80.0% | **FAIL** (2) |
| **Mutation 3: Flattened Hierarchy** | 100.0% | **0.0%** | 0.0% | 2.3% | 0.0% | **FAIL** (12) |
| **Mutation 4: Triplet Role Blindness** | 100.0% | **78.4%** | 100.0% | 81.4% | 100.0% | **FAIL** (2) |
| **Mutation 5: J-GAAP Nil/△0 Collapse** | 95.9% | **95.9%** | 100.0% | 100.0% | 40.0% | **PASS** |
| **Mutation 6: Vector Underline Blindness** | 100.0% | **97.3%** | 100.0% | 100.0% | 60.0% | **PASS** |

## Scenario Failure Analysis

### Hybrid Anchor Parser (Ours)
- **Description**: Ground-truth anchor parser with vector underline extraction & hierarchy tree
- **Naive Flat Accuracy**: 100.0%
- **Strict Relational F1**: 100.0%
- **Accounting Verifier**: PASS

### Mutation 1: Dropped △ Sign
- **Description**: 貸倒引当金 (-2,979 -> +2,979); inverts sign, causing -5,955 subtotal drift
- **Naive Flat Accuracy**: 98.6%
- **Strict Relational F1**: 98.6%
- **Accounting Verifier**: FAIL
- **Verifier Failures Captured**:
  - Rollup `流動資産合計` [2025-03-31]: drift=-5955 (tolerance ±10)

### Mutation 2: Nil Cell Shift
- **Description**: 長期貸付金 '－' dropped, shifting subsequent values up by 1 row
- **Naive Flat Accuracy**: 98.6%
- **Strict Relational F1**: 96.6%
- **Accounting Verifier**: FAIL
- **Verifier Failures Captured**:
  - Structural issue at row 39 'その他': Missing value needed for '投資その他の資産合計' rollup check.
  - Structural issue at row 39 'その他': Missing CellValue for period '2025-03-31'.

### Mutation 3: Flattened Hierarchy
- **Description**: Indentation ignored; all 4 'その他' and 4 '減価償却累計額' lose section ancestry
- **Naive Flat Accuracy**: 100.0%
- **Strict Relational F1**: 0.0%
- **Accounting Verifier**: FAIL
- **Verifier Failures Captured**:
  - Rollup `流動資産合計` [2025-03-31]: drift=-5011276 (tolerance ±5)
  - Rollup `流動資産合計` [2026-03-31]: drift=-5273524 (tolerance ±5)
  - Rollup `有形固定資産合計` [2025-03-31]: drift=-13880456 (tolerance ±5)
  - Rollup `有形固定資産合計` [2026-03-31]: drift=-9323118 (tolerance ±5)
  - Rollup `無形固定資産合計` [2025-03-31]: drift=-16650122 (tolerance ±5)
  - Rollup `無形固定資産合計` [2026-03-31]: drift=-11956600 (tolerance ±5)
  - Rollup `投資その他の資産合計` [2025-03-31]: drift=-16344506 (tolerance ±5)
  - Rollup `投資その他の資産合計` [2026-03-31]: drift=-11289614 (tolerance ±5)
  - Rollup `固定資産合計` [2025-03-31]: drift=-13397792 (tolerance ±5)
  - Rollup `固定資産合計` [2026-03-31]: drift=-8512656 (tolerance ±5)
  - Rollup `資産合計` [2025-03-31]: drift=-1670424 (tolerance ±5)
  - Rollup `資産合計` [2026-03-31]: drift=-1757840 (tolerance ±5)

### Mutation 4: Triplet Role Blindness
- **Description**: Gross & depr rows misclassified as LINE_ITEM, causing rollup to double-count
- **Naive Flat Accuracy**: 100.0%
- **Strict Relational F1**: 78.4%
- **Accounting Verifier**: FAIL
- **Verifier Failures Captured**:
  - Rollup `有形固定資産合計` [2025-03-31]: drift=-660117 (tolerance ±14)
  - Rollup `有形固定資産合計` [2026-03-31]: drift=-642650 (tolerance ±14)

### Mutation 5: J-GAAP Nil/△0 Collapse
- **Description**: － and △0 both collapsed to plain 0; arithmetic passes but GAAP audit trail is lost
- **Naive Flat Accuracy**: 95.9%
- **Strict Relational F1**: 95.9%
- **Accounting Verifier**: PASS

### Mutation 6: Vector Underline Blindness
- **Description**: Ignores PDF vector drawings; fails to detect amendment markings on 218,836 & 1,123
- **Naive Flat Accuracy**: 100.0%
- **Strict Relational F1**: 97.3%
- **Accounting Verifier**: PASS
