"""
tests/test_parser.py
--------------------
Integration tests for src/parser.py on data/balance_sheet_after_correction.pdf.
Validates:
- 100% pass on domain verifier verify() (triplets, rollups, structural integrity)
- Physical amendment detection (is_amended=True on exact corrected cells)
- Nil marker handling (is_nil=True, value=None on 建設仮勘定 and 長期貸付金)
- Negative zero distinction (is_negative_zero=True, value=0 on 貸倒引当金)
- Precise hierarchy_path and RowRole assignments
"""

from __future__ import annotations

import pathlib
import pytest

from src.parser import parse_balance_sheet
from src.schema import ParsedBalanceSheet, RowRole
from src.verifier import verify


PDF_PATH = pathlib.Path("data/balance_sheet_after_correction.pdf")


@pytest.fixture(scope="module")
def parsed_bs() -> ParsedBalanceSheet:
    assert PDF_PATH.exists(), f"Target PDF not found at {PDF_PATH}"
    return parse_balance_sheet(PDF_PATH)


def test_parse_and_verify_all_pass(parsed_bs: ParsedBalanceSheet):
    """The real balance sheet must pass all accounting verification checks 100%."""
    report = verify(parsed_bs)
    assert report.passed, f"Verification failed:\n{report.summary()}"
    assert report.all_triplets_passed
    assert report.all_rollups_within_tolerance
    assert report.structurally_clean
    assert len(report.structural_issues) == 0


def test_document_metadata(parsed_bs: ParsedBalanceSheet):
    meta = parsed_bs.metadata
    assert meta.title == "連結貸借対照表"
    assert meta.is_amended_filing is True
    assert meta.unit == "千円"
    assert meta.periods == ["2025-03-31", "2026-03-31"]


def test_total_row_count(parsed_bs: ParsedBalanceSheet):
    # 6 section headers + 11 current assets + 15 tangible + 3 intangible + 6 investments + 1 fixed total + 1 grand total
    assert len(parsed_bs.rows) == 43


def test_amendment_detection(parsed_bs: ParsedBalanceSheet):
    """
    Physical amendment underlines should mark exactly:
    - 投資有価証券 current period (2026-03-31) = 218,836
    - 関係会社株式 current period (2026-03-31) = 1,123
    All other cells in both periods must have is_amended=False.
    """
    p1, p2 = parsed_bs.metadata.periods

    row_inv = parsed_bs.row_by_path("投資その他の資産", "投資有価証券")
    assert row_inv is not None
    assert row_inv.values[p1].is_amended is False
    assert row_inv.values[p2].is_amended is True
    assert row_inv.values[p2].value == 218_836

    row_affil = parsed_bs.row_by_path("投資その他の資産", "関係会社株式")
    assert row_affil is not None
    assert row_affil.values[p1].is_amended is False
    assert row_affil.values[p2].is_amended is True
    assert row_affil.values[p2].value == 1_123

    # Ensure no other cell has is_amended=True
    amended_cells = []
    for r in parsed_bs.rows:
        for p, cell in r.values.items():
            if cell.is_amended:
                amended_cells.append((r.label, p, cell.value))

    assert len(amended_cells) == 2
    assert set(amended_cells) == {
        ("投資有価証券", p2, 218_836),
        ("関係会社株式", p2, 1_123),
    }


def test_nil_cells(parsed_bs: ParsedBalanceSheet):
    """
    U+FF0D '－' indicates no balance (nil), distinct from 0.
    - 建設仮勘定: prior period is nil, current period has balance 4,553
    - 長期貸付金: prior period is nil, current period has balance 62,000
    """
    p1, p2 = parsed_bs.metadata.periods

    row_cip = parsed_bs.row_by_path("有形固定資産", "建設仮勘定")
    assert row_cip is not None
    c_cip_p1 = row_cip.values[p1]
    assert c_cip_p1.is_nil is True
    assert c_cip_p1.value is None
    assert c_cip_p1.effective_value() == 0
    c_cip_p2 = row_cip.values[p2]
    assert c_cip_p2.is_nil is False
    assert c_cip_p2.value == 4_553

    row_loan = parsed_bs.row_by_path("投資その他の資産", "長期貸付金")
    assert row_loan is not None
    c_loan_p1 = row_loan.values[p1]
    assert c_loan_p1.is_nil is True
    assert c_loan_p1.value is None
    assert c_loan_p1.effective_value() == 0
    c_loan_p2 = row_loan.values[p2]
    assert c_loan_p2.is_nil is False
    assert c_loan_p2.value == 62_000


def test_negative_zero(parsed_bs: ParsedBalanceSheet):
    """
    '△0' in 貸倒引当金 current period represents an active account balance
    that rounds to 0 at the 千円 level, distinct from nil.
    """
    p1, p2 = parsed_bs.metadata.periods

    row_allowance = parsed_bs.row_by_path("流動資産", "貸倒引当金")
    assert row_allowance is not None

    c_p1 = row_allowance.values[p1]
    assert c_p1.value == -2_979
    assert c_p1.is_nil is False
    assert c_p1.is_negative_zero is False

    c_p2 = row_allowance.values[p2]
    assert c_p2.value == 0
    assert c_p2.is_negative_zero is True
    assert c_p2.is_nil is False
    assert c_p2.effective_value() == 0
    assert c_p2.raw_text == "△0"


def test_tangible_triplets(parsed_bs: ParsedBalanceSheet):
    """
    The 4 gross/depr/net triplets under 有形固定資産 must:
    - Have distinct hierarchy paths (disambiguating 減価償却累計額)
    - Have roles GROSS_ITEM, ACCUM_DEPR, NET_ITEM
    - Satisfy gross + depr == net within ±1 千円 rounding drift in both periods
    """
    p1, p2 = parsed_bs.metadata.periods
    triplet_names = [
        "建物及び構築物",
        "機械装置及び運搬具",
        "リース資産",
        "その他",
    ]

    depr_paths = set()
    for name in triplet_names:
        gross_row = parsed_bs.row_by_path("有形固定資産", name)
        assert gross_row is not None
        assert gross_row.role == RowRole.GROSS_ITEM

        depr_row = parsed_bs.row_by_path("有形固定資産", name, "減価償却累計額")
        assert depr_row is not None
        assert depr_row.role == RowRole.ACCUM_DEPR
        depr_path_tuple = tuple(depr_row.hierarchy_path)
        assert depr_path_tuple not in depr_paths
        depr_paths.add(depr_path_tuple)

        net_row = parsed_bs.row_by_path("有形固定資産", name, f"{name}（純額）")
        assert net_row is not None
        assert net_row.role == RowRole.NET_ITEM

        for p in (p1, p2):
            gross_val = gross_row.values[p].value
            depr_val = depr_row.values[p].value
            net_val = net_row.values[p].value
            assert abs((gross_val + depr_val) - net_val) <= 1

    assert len(depr_paths) == 4


def test_subtotal_and_grand_total_paths(parsed_bs: ParsedBalanceSheet):
    """Verify that hierarchy_path of subtotals and grand totals correctly reflect section ancestry."""
    st_tests = [
        ("流動資産合計", ["資産の部", "流動資産", "流動資産合計"], RowRole.SUBTOTAL),
        ("有形固定資産合計", ["資産の部", "固定資産", "有形固定資産", "有形固定資産合計"], RowRole.SUBTOTAL),
        ("無形固定資産合計", ["資産の部", "固定資産", "無形固定資産", "無形固定資産合計"], RowRole.SUBTOTAL),
        ("投資その他の資産合計", ["資産の部", "固定資産", "投資その他の資産", "投資その他の資産合計"], RowRole.SUBTOTAL),
        ("固定資産合計", ["資産の部", "固定資産", "固定資産合計"], RowRole.SUBTOTAL),
        ("資産合計", ["資産の部", "資産合計"], RowRole.GRAND_TOTAL),
    ]

    for label, expected_path, expected_role in st_tests:
        row = next(r for r in parsed_bs.rows if r.label == label)
        assert row.hierarchy_path == expected_path
        assert row.role == expected_role

    # Grand total values
    p1, p2 = parsed_bs.metadata.periods
    grand_total = next(r for r in parsed_bs.rows if r.label == "資産合計")
    assert grand_total.values[p1].value == 7_534_110
    assert grand_total.values[p2].value == 5_135_249
