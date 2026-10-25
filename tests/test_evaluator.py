"""
tests/test_evaluator.py
-----------------------
Unit and integration tests for src/evaluator.py and the benchmark mutations.
"""

from __future__ import annotations

import pathlib
import pytest

from scripts.run_eval_benchmark import (
    mutate_dropped_negative_sign,
    mutate_nil_cell_shift,
    mutate_flattened_hierarchy,
    mutate_triplet_role_blindness,
    mutate_nil_neg_zero_collapse,
    mutate_vector_underline_blindness,
)
from src.evaluator import evaluate_balance_sheet
from src.parser import parse_balance_sheet
from src.schema import ParsedBalanceSheet


PDF_PATH = pathlib.Path("data/balance_sheet_after_correction.pdf")


@pytest.fixture(scope="module")
def reference_bs() -> ParsedBalanceSheet:
    assert PDF_PATH.exists(), f"Target PDF not found at {PDF_PATH}"
    return parse_balance_sheet(PDF_PATH)


def test_evaluator_clean_reference(reference_bs: ParsedBalanceSheet):
    """Clean reference against itself must achieve 100% on all metrics and pass verification."""
    rep = evaluate_balance_sheet(reference_bs, reference_bs)
    assert rep.strict_tuple_f1 == 1.0
    assert rep.numeric_value_f1 == 1.0
    assert rep.hierarchy_path_accuracy == 1.0
    assert rep.semantic_distinction_accuracy == 1.0
    assert rep.naive_flat_cell_accuracy == 1.0
    assert rep.verifier_passed is True
    assert rep.total_verifier_failures == 0


def test_mutation_dropped_negative_sign(reference_bs: ParsedBalanceSheet):
    """
    Dropped △ sign retains ~98.6% naive flat accuracy, but strict F1 < 1.0
    and accounting verifier immediately fails on subtotal drift.
    """
    cand = mutate_dropped_negative_sign(reference_bs)
    rep = evaluate_balance_sheet(cand, reference_bs)

    assert rep.naive_flat_cell_accuracy >= 0.98
    assert rep.strict_tuple_f1 < 1.0
    assert rep.verifier_passed is False
    # Check that 流動資産合計 fails due to drift = -5,955
    failed_rollups = [r for r in rep.verifier_report.rollup_results if not r.within_rounding_tolerance]
    assert any(r.subtotal_label == "流動資産合計" for r in failed_rollups)


def test_mutation_nil_cell_shift(reference_bs: ParsedBalanceSheet):
    """
    Nil cell dropped shifts subsequent rows up, dropping strict F1
    and failing verifier.
    """
    cand = mutate_nil_cell_shift(reference_bs)
    rep = evaluate_balance_sheet(cand, reference_bs)

    assert rep.strict_tuple_f1 < 0.98
    assert rep.verifier_passed is False


def test_mutation_flattened_hierarchy(reference_bs: ParsedBalanceSheet):
    """
    Flattened hierarchy keeps 100% naive flat accuracy, but hierarchy accuracy drops near 0.
    """
    cand = mutate_flattened_hierarchy(reference_bs)
    rep = evaluate_balance_sheet(cand, reference_bs)

    assert rep.naive_flat_cell_accuracy == 1.0
    assert rep.hierarchy_path_accuracy < 0.1
    assert rep.strict_tuple_f1 == 0.0  # hierarchy tuple mismatch


def test_mutation_triplet_role_blindness(reference_bs: ParsedBalanceSheet):
    """
    Triplet role blindness misclassifies gross & depr as LINE_ITEM,
    failing rollup checks.
    """
    cand = mutate_triplet_role_blindness(reference_bs)
    rep = evaluate_balance_sheet(cand, reference_bs)

    assert rep.hierarchy_path_accuracy < 1.0
    assert rep.verifier_passed is False


def test_mutation_nil_neg_zero_collapse(reference_bs: ParsedBalanceSheet):
    """
    Collapsing nil and △0 into plain 0 passes arithmetic verifier, but
    is caught by semantic distinction accuracy and strict relational F1.
    """
    cand = mutate_nil_neg_zero_collapse(reference_bs)
    rep = evaluate_balance_sheet(cand, reference_bs)

    # Arithmetic passes!
    assert rep.verifier_passed is True
    assert rep.numeric_value_f1 == 1.0
    # But J-GAAP semantic distinction drops!
    assert rep.semantic_distinction_accuracy < 1.0
    assert rep.strict_tuple_f1 < 1.0


def test_mutation_vector_underline_blindness(reference_bs: ParsedBalanceSheet):
    """
    Ignoring vector underlines drops semantic distinction accuracy and strict F1.
    """
    cand = mutate_vector_underline_blindness(reference_bs)
    rep = evaluate_balance_sheet(cand, reference_bs)

    assert rep.semantic_distinction_accuracy < 1.0
    assert rep.strict_tuple_f1 < 1.0
    # Exactly 2 amended cells were missed
    assert len(extract_canonical_cell_tuples(reference_bs) - extract_canonical_cell_tuples(cand)) == 2


from src.evaluator import extract_canonical_cell_tuples
