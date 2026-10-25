"""
src/evaluator.py
----------------
Extrinsic ground-truth evaluation and failure-mode benchmarking framework for
J-GAAP financial table extraction.

Addresses the core R&D question: "How you define and measure 'correct' is up to you."

Generic OCR and table extraction benchmarks (e.g. flat BLEU, cell text accuracy,
or standard TEDS) treat financial filings as flat grids of strings. This hides
catastrophic domain failures:
  - Dropping a Japanese negative sign (△) retains ~99% flat text accuracy while
    inverting balance sheet math by millions of yen.
  - Collapsing U+FF0D (－) and △0 into plain 0 loses GAAP audit semantics (no balance vs active balance).
  - Flattening visual indentation renders repeated labels ('その他', '減価償却累計額') ambiguous.
  - Ignoring vector underlines fails to capture amendment indicators (訂正後 filings).

This module pairs intrinsic accounting verification (src/verifier.py) with
strict relational tuple evaluation:
  Relational Cell Tuple:
    (hierarchy_path_tuple, role, period, effective_value, is_nil, is_negative_zero, is_amended)
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional, Set, Tuple

from src.schema import BalanceSheetRow, CellValue, ParsedBalanceSheet, RowRole
from src.verifier import verify, VerificationReport


# ---------------------------------------------------------------------------
# Canonical Relational Tuples
# ---------------------------------------------------------------------------

# Full relational data cell tuple:
# (hierarchy_path, role, period, effective_value, is_nil, is_negative_zero, is_amended)
CanonicalCellTuple = Tuple[
    Tuple[str, ...],  # hierarchy_path
    str,              # role (e.g. 'LINE_ITEM', 'GROSS_ITEM', etc.)
    str,              # period (e.g. '2025-03-31')
    int,              # effective_value (0 if nil or △0, signed int otherwise)
    bool,             # is_nil (U+FF0D '－')
    bool,             # is_negative_zero ('△0')
    bool,             # is_amended (correction underline)
]

# Numeric value tuple:
# (hierarchy_path, period, effective_value)
NumericCellTuple = Tuple[
    Tuple[str, ...],
    str,
    int,
]

# Naive flat cell tuple:
# (label, period, flat_text_or_abs_val)
NaiveFlatCellTuple = Tuple[
    str,              # label
    str,              # period
    str,              # raw or unsigned text
]


def extract_canonical_cell_tuples(bs: ParsedBalanceSheet) -> Set[CanonicalCellTuple]:
    """Extract all data cell relational tuples from a balance sheet."""
    tuples: Set[CanonicalCellTuple] = set()
    for row in bs.rows:
        if row.role == RowRole.SECTION_HEADER:
            continue
        path_tuple = tuple(row.hierarchy_path)
        role_str = row.role.value
        for period, cell in row.values.items():
            tuples.add((
                path_tuple,
                role_str,
                period,
                cell.effective_value(),
                cell.is_nil,
                cell.is_negative_zero,
                cell.is_amended,
            ))
    return tuples


def extract_numeric_cell_tuples(bs: ParsedBalanceSheet) -> Set[NumericCellTuple]:
    """Extract hierarchy-aware numeric value tuples."""
    tuples: Set[NumericCellTuple] = set()
    for row in bs.rows:
        if row.role == RowRole.SECTION_HEADER:
            continue
        path_tuple = tuple(row.hierarchy_path)
        for period, cell in row.values.items():
            tuples.add((
                path_tuple,
                period,
                cell.effective_value(),
            ))
    return tuples


def extract_naive_flat_tuples(bs: ParsedBalanceSheet) -> list[NaiveFlatCellTuple]:
    """
    Extract naive flat tuples (label, period, normalized_digits) mimicking
    standard OCR/table benchmarks that ignore hierarchy, negative signs, and GAAP flags.
    """
    tuples: list[NaiveFlatCellTuple] = []
    for row in bs.rows:
        if row.role == RowRole.SECTION_HEADER:
            continue
        for period, cell in row.values.items():
            # Strips △, negative signs, and commas to mimic naive digit accuracy
            norm = cell.raw_text.lstrip("△▲-").replace(",", "").strip()
            if cell.is_nil:
                norm = "0"
            tuples.append((row.label, period, norm))
    return tuples


# ---------------------------------------------------------------------------
# Evaluation Report Dataclass
# ---------------------------------------------------------------------------

@dataclass
class EvaluationReport:
    """Comprehensive evaluation metrics comparing candidate against reference."""
    # Strict Relational Metrics
    strict_tuple_precision: float
    strict_tuple_recall: float
    strict_tuple_f1: float

    # Hierarchy-aware Numeric Value Metric
    numeric_value_f1: float

    # Structural & Semantic Breakdown
    hierarchy_path_accuracy: float         # exact match of hierarchy_path & role per row
    semantic_distinction_accuracy: float   # accuracy on J-GAAP special cells (nil, △0, amended)

    # Naive Baseline Metric (for contrast)
    naive_flat_cell_accuracy: float

    # Intrinsic Accounting Verifier
    verifier_report: VerificationReport

    @property
    def verifier_passed(self) -> bool:
        return self.verifier_report.passed

    @property
    def total_verifier_failures(self) -> int:
        triplet_fails = sum(1 for t in self.verifier_report.triplet_results if not t.passed)
        rollup_fails = sum(1 for r in self.verifier_report.rollup_results if not r.within_rounding_tolerance)
        struct_fails = len(self.verifier_report.structural_issues)
        return triplet_fails + rollup_fails + struct_fails

    def summary(self) -> str:
        ver_status = "PASS" if self.verifier_passed else f"FAIL ({self.total_verifier_failures} issues)"
        lines = [
            "=== Extraction Evaluation Report ===",
            f"Strict Relational F1        : {self.strict_tuple_f1 * 100:.1f}% "
            f"(P={self.strict_tuple_precision * 100:.1f}%, R={self.strict_tuple_recall * 100:.1f}%)",
            f"Numeric Value F1            : {self.numeric_value_f1 * 100:.1f}%",
            f"Hierarchy & Role Accuracy   : {self.hierarchy_path_accuracy * 100:.1f}%",
            f"J-GAAP Semantic Accuracy    : {self.semantic_distinction_accuracy * 100:.1f}%",
            f"Naive Flat Cell Accuracy    : {self.naive_flat_cell_accuracy * 100:.1f}% [Generic Benchmark]",
            f"Accounting Verifier Status  : {ver_status}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core Evaluation Function
# ---------------------------------------------------------------------------

def evaluate_balance_sheet(
    candidate: ParsedBalanceSheet,
    reference: ParsedBalanceSheet,
) -> EvaluationReport:
    """
    Evaluate candidate ParsedBalanceSheet against a ground-truth reference,
    computing strict relational metrics, sub-metrics, and intrinsic verification.
    """
    # 1. Strict Relational Tuple Metrics
    cand_strict = extract_canonical_cell_tuples(candidate)
    ref_strict = extract_canonical_cell_tuples(reference)

    tp_strict = len(cand_strict & ref_strict)
    p_strict = tp_strict / len(cand_strict) if cand_strict else 0.0
    r_strict = tp_strict / len(ref_strict) if ref_strict else 0.0
    f1_strict = (2 * p_strict * r_strict / (p_strict + r_strict)) if (p_strict + r_strict) > 0 else 0.0

    # 2. Numeric Value F1
    cand_num = extract_numeric_cell_tuples(candidate)
    ref_num = extract_numeric_cell_tuples(reference)

    tp_num = len(cand_num & ref_num)
    p_num = tp_num / len(cand_num) if cand_num else 0.0
    r_num = tp_num / len(ref_num) if ref_num else 0.0
    f1_num = (2 * p_num * r_num / (p_num + r_num)) if (p_num + r_num) > 0 else 0.0

    # 3. Hierarchy Path & Role Accuracy
    # Align rows by index up to min length
    min_rows = min(len(candidate.rows), len(reference.rows))
    max_rows = max(len(candidate.rows), len(reference.rows))
    matching_rows = 0
    for i in range(min_rows):
        c_row = candidate.rows[i]
        r_row = reference.rows[i]
        if (
            c_row.label == r_row.label
            and c_row.hierarchy_path == r_row.hierarchy_path
            and c_row.role == r_row.role
        ):
            matching_rows += 1
    hierarchy_acc = matching_rows / max_rows if max_rows > 0 else 1.0

    # 4. Semantic Distinction Accuracy (special J-GAAP cells: nil, △0, amended)
    # Find all reference cells with any special flag active
    special_cells_total = 0
    special_cells_correct = 0

    # Map candidate cells by (tuple(hierarchy_path), period)
    cand_cell_map = {}
    for row in candidate.rows:
        p_tup = tuple(row.hierarchy_path)
        for period, cell in row.values.items():
            cand_cell_map[(p_tup, period)] = cell

    for r_row in reference.rows:
        p_tup = tuple(r_row.hierarchy_path)
        for period, r_cell in r_row.values.items():
            is_special = r_cell.is_nil or r_cell.is_negative_zero or r_cell.is_amended
            if is_special:
                special_cells_total += 1
                c_cell = cand_cell_map.get((p_tup, period))
                if c_cell is not None:
                    if (
                        c_cell.is_nil == r_cell.is_nil
                        and c_cell.is_negative_zero == r_cell.is_negative_zero
                        and c_cell.is_amended == r_cell.is_amended
                    ):
                        special_cells_correct += 1

    semantic_acc = (special_cells_correct / special_cells_total) if special_cells_total > 0 else 1.0

    # 5. Naive Flat Cell Accuracy (Standard bag-of-cell-tokens recall on page)
    # Generic OCR/table benchmarks evaluate flat tokens on the page regardless of
    # hierarchy, sign semantics, or accounting consistency.
    cand_tokens = [c.raw_text.strip() for r in candidate.rows if r.role != RowRole.SECTION_HEADER for c in r.values.values()]
    ref_tokens = [c.raw_text.strip() for r in reference.rows if r.role != RowRole.SECTION_HEADER for c in r.values.values()]

    import collections
    cand_counter = collections.Counter(cand_tokens)
    ref_counter = collections.Counter(ref_tokens)
    total_ref = sum(ref_counter.values())
    matched_tokens = sum((cand_counter & ref_counter).values())
    naive_flat_acc = matched_tokens / total_ref if total_ref > 0 else 1.0

    # 6. Intrinsic Accounting Verification on Candidate
    ver_report = verify(candidate)

    return EvaluationReport(
        strict_tuple_precision=p_strict,
        strict_tuple_recall=r_strict,
        strict_tuple_f1=f1_strict,
        numeric_value_f1=f1_num,
        hierarchy_path_accuracy=hierarchy_acc,
        semantic_distinction_accuracy=semantic_acc,
        naive_flat_cell_accuracy=naive_flat_acc,
        verifier_report=ver_report,
    )
