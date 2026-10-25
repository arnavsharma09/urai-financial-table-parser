"""
tests/test_verifier.py
----------------------
Unit tests for src/verifier.py using a small hand-crafted mock balance sheet.

Covers:
  - Gross/depreciation/net triplet check (exact match + failing case)
  - Subtotal roll-up with +3 千円 rounding drift (within_rounding_tolerance=True,
    exact_match=False) and a case that exceeds tolerance
  - Structural checks: missing value, invalid header-with-value, nil vs delta-zero
  - CellValue.effective_value(): nil->0, negative_zero->0, negative->negative int
  - CellValue model_validator: mutual-exclusion rules
"""

import pytest

from src.schema import (
    BalanceSheetMetadata,
    BalanceSheetRow,
    BBox,
    CellValue,
    ParsedBalanceSheet,
    RowRole,
)
from src.verifier import verify


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PERIODS = ["2025-03-31", "2026-03-31"]

def _meta(**kw) -> BalanceSheetMetadata:
    return BalanceSheetMetadata(
        title="連結貸借対照表",
        is_amended_filing=kw.get("is_amended_filing", False),
        unit="千円",
        periods=PERIODS,
    )


def _cell(value=None, *, nil=False, neg_zero=False, amended=False, raw="") -> CellValue:
    raw_text = raw or (
        "－" if nil else
        "△0" if neg_zero else
        f"△{abs(value):,}" if (value is not None and value < 0) else
        f"{value:,}" if value is not None else
        ""
    )
    return CellValue(
        raw_text=raw_text,
        value=value,
        is_nil=nil,
        is_negative_zero=neg_zero,
        is_amended=amended,
    )


def _row(
    idx: int,
    label: str,
    role: RowRole,
    indent: int = 2,
    path: list[str] | None = None,
    vals: dict[str, CellValue] | None = None,
    y: float | None = None,
) -> BalanceSheetRow:
    return BalanceSheetRow(
        row_index=idx,
        label=label,
        indent_level=indent,
        hierarchy_path=path or ["資産の部", label],
        role=role,
        values=vals or {},
        y_coord=y if y is not None else float(idx) * 12.0,
    )


def _vals(p1, p2) -> dict[str, CellValue]:
    """Make a two-period values dict from raw integers (or CellValue objects)."""
    def coerce(v):
        return v if isinstance(v, CellValue) else _cell(v)
    return {PERIODS[0]: coerce(p1), PERIODS[1]: coerce(p2)}


# ---------------------------------------------------------------------------
# CellValue unit tests
# ---------------------------------------------------------------------------

class TestCellValue:
    def test_normal_positive(self):
        c = _cell(1000)
        assert c.effective_value() == 1000
        assert not c.is_nil
        assert not c.is_negative_zero

    def test_normal_negative(self):
        c = _cell(-2979)
        assert c.effective_value() == -2979

    def test_nil(self):
        c = _cell(nil=True)
        assert c.is_nil
        assert c.value is None
        assert c.effective_value() == 0   # nil -> 0 for arithmetic

    def test_negative_zero(self):
        c = _cell(0, neg_zero=True)
        assert c.is_negative_zero
        assert c.value == 0
        assert c.effective_value() == 0

    def test_nil_and_neg_zero_mutually_exclusive(self):
        with pytest.raises(Exception):
            CellValue(raw_text="bad", value=None, is_nil=True, is_negative_zero=True)

    def test_nil_requires_value_none(self):
        with pytest.raises(Exception):
            CellValue(raw_text="bad", value=100, is_nil=True)

    def test_neg_zero_requires_value_zero(self):
        with pytest.raises(Exception):
            CellValue(raw_text="bad", value=5, is_negative_zero=True)

    def test_amended_flag(self):
        c = _cell(218836, amended=True)
        assert c.is_amended
        assert c.effective_value() == 218836


# ---------------------------------------------------------------------------
# Fixture: minimal balance sheet with one gross/dep/net triplet
# ---------------------------------------------------------------------------

def _make_triplet_sheet(
    *,
    gross_p1=100_000,
    depr_p1=-30_000,
    net_p1=70_000,   # correct: 100000 + (-30000) = 70000
    gross_p2=120_000,
    depr_p2=-40_000,
    net_p2=80_000,   # correct
) -> ParsedBalanceSheet:
    rows = [
        _row(0, "資産の部", RowRole.SECTION_HEADER, indent=0, path=["資産の部"]),
        _row(1, "固定資産", RowRole.SECTION_HEADER, indent=1, path=["資産の部", "固定資産"]),
        _row(2, "有形固定資産", RowRole.SECTION_HEADER, indent=2,
             path=["資産の部", "固定資産", "有形固定資産"]),
        _row(3, "建物及び構築物", RowRole.GROSS_ITEM, indent=3,
             path=["資産の部", "固定資産", "有形固定資産", "建物及び構築物"],
             vals=_vals(gross_p1, gross_p2)),
        _row(4, "減価償却累計額", RowRole.ACCUM_DEPR, indent=4,
             path=["資産の部", "固定資産", "有形固定資産", "建物及び構築物", "減価償却累計額"],
             vals=_vals(depr_p1, depr_p2)),
        _row(5, "建物及び構築物（純額）", RowRole.NET_ITEM, indent=4,
             path=["資産の部", "固定資産", "有形固定資産", "建物及び構築物", "建物及び構築物（純額）"],
             vals=_vals(net_p1, net_p2)),
    ]
    return ParsedBalanceSheet(metadata=_meta(), rows=rows)


class TestTripletCheck:
    def test_triplet_exact_pass(self):
        bs = _make_triplet_sheet()
        report = verify(bs)
        assert len(report.triplet_results) == 2   # one triplet × two periods
        assert report.all_triplets_passed

    def test_triplet_fail_wrong_net(self):
        # net_p1 is off by 5 — should fail
        bs = _make_triplet_sheet(net_p1=70_005)
        report = verify(bs)
        failed = [r for r in report.triplet_results if not r.passed]
        assert len(failed) == 1
        assert failed[0].period == PERIODS[0]
        assert failed[0].diff == 5

    def test_triplet_negative_depr_semantics(self):
        # Depreciation is negative in the schema; gross + depr = net
        bs = _make_triplet_sheet(gross_p1=2_121_360, depr_p1=-1_923_585, net_p1=197_775)
        report = verify(bs)
        r = [t for t in report.triplet_results if t.period == PERIODS[0]][0]
        assert r.passed
        assert r.net_computed == 197_775

    def test_triplet_neg_zero_in_net(self):
        # △0 net — gross=5, depr=-5, net=0 (printed as △0)
        gross_cell = _cell(5)
        depr_cell  = _cell(-5)
        net_cell   = _cell(0, neg_zero=True)
        rows = [
            _row(0, "有形固定資産", RowRole.SECTION_HEADER, indent=0, path=["有形固定資産"]),
            _row(1, "その他", RowRole.GROSS_ITEM, indent=1,
                 path=["有形固定資産", "その他"],
                 vals={PERIODS[0]: gross_cell, PERIODS[1]: gross_cell}),
            _row(2, "減価償却累計額", RowRole.ACCUM_DEPR, indent=2,
                 path=["有形固定資産", "その他", "減価償却累計額"],
                 vals={PERIODS[0]: depr_cell, PERIODS[1]: depr_cell}),
            _row(3, "その他（純額）", RowRole.NET_ITEM, indent=2,
                 path=["有形固定資産", "その他", "その他（純額）"],
                 vals={PERIODS[0]: net_cell, PERIODS[1]: net_cell}),
        ]
        bs = ParsedBalanceSheet(
            metadata=BalanceSheetMetadata(title="T", periods=PERIODS),
            rows=rows,
        )
        report = verify(bs)
        assert report.all_triplets_passed


# ---------------------------------------------------------------------------
# Fixture: minimal roll-up sheet (流動資産 section)
# ---------------------------------------------------------------------------

def _make_rollup_sheet(
    *,
    line_items: list[tuple[str, int, int]],   # (label, p1, p2)
    total_p1: int,
    total_p2: int,
) -> ParsedBalanceSheet:
    """
    Build a sheet with only 流動資産 section → N line items → 流動資産合計.
    """
    rows: list[BalanceSheetRow] = [
        _row(0, "資産の部", RowRole.SECTION_HEADER, indent=0, path=["資産の部"]),
        _row(1, "流動資産", RowRole.SECTION_HEADER, indent=1,
             path=["資産の部", "流動資産"]),
    ]
    for i, (lbl, p1, p2) in enumerate(line_items):
        rows.append(_row(
            2 + i, lbl, RowRole.LINE_ITEM, indent=2,
            path=["資産の部", "流動資産", lbl],
            vals=_vals(p1, p2),
        ))
    rows.append(_row(
        2 + len(line_items), "流動資産合計", RowRole.SUBTOTAL, indent=1,
        path=["資産の部", "流動資産", "流動資産合計"],
        vals=_vals(total_p1, total_p2),
    ))
    return ParsedBalanceSheet(metadata=_meta(), rows=rows)


class TestRollupCheck:
    def test_exact_match(self):
        bs = _make_rollup_sheet(
            line_items=[("現金及び預金", 1000, 2000), ("売掛金", 500, 600)],
            total_p1=1500,
            total_p2=2600,
        )
        report = verify(bs)
        r = [x for x in report.rollup_results
             if x.subtotal_label == "流動資産合計" and x.period == PERIODS[0]][0]
        assert r.exact_match
        assert r.within_rounding_tolerance
        assert r.diff == 0

    def test_rounding_drift_within_tolerance(self):
        """
        Classic 千円 truncation: 10 line items sum to 5,863,681 but
        printed total is 5,863,684 — drift +3, tolerance = ±10 -> PASS.
        """
        items = [
            ("現金及び預金", 2_002_429, 608_281),
            ("受取手形", 20_659, 26_333),
            ("売掛金", 2_019_476, 884_339),
            ("電子記録債権", 564_667, 370_468),
            ("商品及び製品", 589_488, 1_019_663),
            ("仕掛品", 186_748, 55_344),
            ("原材料及び貯蔵品", 370_403, 136_082),
            ("短期貸付金", 7_530, 30_000),
            ("その他", 105_260, 246_895),
            ("貸倒引当金", -2_979, 0),   # △0 in right col, but use int for simplicity
        ]
        # Real printed total (前期)
        total_p1 = 5_863_684
        # Sum of line items (前期) = 5_863_681  -> drift +3
        computed_p1 = sum(v for _, v, _ in items)
        assert computed_p1 == 5_863_681

        bs = _make_rollup_sheet(
            line_items=items,
            total_p1=total_p1,
            total_p2=3_377_407,
        )
        report = verify(bs)
        r_p1 = [x for x in report.rollup_results
                if x.subtotal_label == "流動資産合計" and x.period == PERIODS[0]][0]
        assert not r_p1.exact_match
        assert r_p1.within_rounding_tolerance
        assert r_p1.diff == 3

    def test_rounding_drift_exceeds_tolerance(self):
        """
        A drift of +50 with only 3 summands should FAIL within_rounding_tolerance.
        """
        bs = _make_rollup_sheet(
            line_items=[("A", 1000, 2000), ("B", 500, 600), ("C", 300, 400)],
            total_p1=1850,   # actual sum = 1800, drift = +50
            total_p2=3000,
        )
        report = verify(bs)
        r = [x for x in report.rollup_results
             if x.subtotal_label == "流動資産合計" and x.period == PERIODS[0]][0]
        assert not r.exact_match
        assert not r.within_rounding_tolerance
        assert r.diff == 50

    def test_nil_treated_as_zero_in_rollup(self):
        """A nil cell should contribute 0 to the rollup sum."""
        nil_cell = _cell(nil=True)
        normal_cell = _cell(1000)
        rows: list[BalanceSheetRow] = [
            _row(0, "資産の部", RowRole.SECTION_HEADER, indent=0, path=["資産の部"]),
            _row(1, "流動資産", RowRole.SECTION_HEADER, indent=1,
                 path=["資産の部", "流動資産"]),
            _row(2, "長期貸付金", RowRole.LINE_ITEM, indent=2,
                 path=["資産の部", "流動資産", "長期貸付金"],
                 vals={PERIODS[0]: nil_cell, PERIODS[1]: normal_cell}),
            _row(3, "その他", RowRole.LINE_ITEM, indent=2,
                 path=["資産の部", "流動資産", "その他"],
                 vals={PERIODS[0]: _cell(500), PERIODS[1]: _cell(500)}),
            _row(4, "流動資産合計", RowRole.SUBTOTAL, indent=1,
                 path=["資産の部", "流動資産", "流動資産合計"],
                 vals={PERIODS[0]: _cell(500), PERIODS[1]: _cell(1500)}),
        ]
        bs = ParsedBalanceSheet(metadata=_meta(), rows=rows)
        report = verify(bs)
        r_p1 = [x for x in report.rollup_results
                if x.subtotal_label == "流動資産合計" and x.period == PERIODS[0]][0]
        assert r_p1.sum_computed == 500   # nil(0) + 500
        assert r_p1.exact_match


# ---------------------------------------------------------------------------
# Structural checks
# ---------------------------------------------------------------------------

class TestStructuralChecks:
    def test_clean_sheet_no_issues(self):
        bs = _make_triplet_sheet()
        report = verify(bs)
        assert report.structurally_clean

    def test_missing_period_value_flagged(self):
        # Row has values only for p1, not p2
        rows = [
            _row(0, "資産の部", RowRole.SECTION_HEADER, indent=0, path=["資産の部"]),
            _row(1, "流動資産", RowRole.SECTION_HEADER, indent=1,
                 path=["資産の部", "流動資産"]),
            _row(2, "現金及び預金", RowRole.LINE_ITEM, indent=2,
                 path=["資産の部", "流動資産", "現金及び預金"],
                 vals={PERIODS[0]: _cell(1000)}),   # p2 missing!
            _row(3, "流動資産合計", RowRole.SUBTOTAL, indent=1,
                 path=["資産の部", "流動資産", "流動資産合計"],
                 vals={PERIODS[0]: _cell(1000), PERIODS[1]: _cell(1000)}),
        ]
        bs = ParsedBalanceSheet(metadata=_meta(), rows=rows)
        report = verify(bs)
        assert not report.structurally_clean
        issue_labels = [i.label for i in report.structural_issues]
        assert "現金及び預金" in issue_labels

    def test_section_header_with_values_flagged(self):
        # Parser bug: SECTION_HEADER row erroneously has values
        with pytest.raises(Exception):
            # The model_validator on BalanceSheetRow should already reject this
            _row(0, "資産の部", RowRole.SECTION_HEADER, indent=0, path=["資産の部"],
                 vals={PERIODS[0]: _cell(999)})

    def test_nil_vs_neg_zero_preserved_separately(self):
        """
        Confirm that nil (－) and △0 produce distinct CellValue states
        and are NOT collapsed at the schema level.
        """
        nil_cell   = _cell(nil=True)
        neg0_cell  = _cell(0, neg_zero=True)
        zero_cell  = _cell(0)

        assert nil_cell.is_nil
        assert not nil_cell.is_negative_zero
        assert nil_cell.value is None

        assert neg0_cell.is_negative_zero
        assert not neg0_cell.is_nil
        assert neg0_cell.value == 0

        assert not zero_cell.is_nil
        assert not zero_cell.is_negative_zero
        assert zero_cell.value == 0

        # All three have effective_value() == 0 for arithmetic
        assert nil_cell.effective_value()  == 0
        assert neg0_cell.effective_value() == 0
        assert zero_cell.effective_value() == 0

    def test_row_by_path_disambiguation(self):
        """hierarchy_path must disambiguate repeated labels like その他."""
        bs = _make_triplet_sheet()
        # row_by_path should work for unambiguous path
        row = bs.row_by_path("有形固定資産", "建物及び構築物")
        assert row is not None
        assert row.label == "建物及び構築物"

    def test_amended_flag_preserved(self):
        amended_cell = _cell(218_836, amended=True)
        rows = [
            _row(0, "資産の部", RowRole.SECTION_HEADER, indent=0, path=["資産の部"]),
            _row(1, "流動資産", RowRole.SECTION_HEADER, indent=1,
                 path=["資産の部", "流動資産"]),
            _row(2, "投資有価証券", RowRole.LINE_ITEM, indent=2,
                 path=["資産の部", "流動資産", "投資有価証券"],
                 vals={PERIODS[0]: _cell(44_180), PERIODS[1]: amended_cell}),
            _row(3, "流動資産合計", RowRole.SUBTOTAL, indent=1,
                 path=["資産の部", "流動資産", "流動資産合計"],
                 vals={PERIODS[0]: _cell(44_180), PERIODS[1]: _cell(218_836)}),
        ]
        bs = ParsedBalanceSheet(metadata=_meta(), rows=rows)
        row = bs.row_by_path("投資有価証券")
        assert row.values[PERIODS[1]].is_amended

