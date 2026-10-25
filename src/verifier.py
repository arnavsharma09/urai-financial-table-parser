"""
src/verifier.py
---------------
Generalised domain-level accounting verifier for J-GAAP balance sheets.

Key features:
1. Gross / Depreciation / Net triplet verification under 有形固定資産:
   - Validates gross + accumulated_depreciation == net (with ±1 千円 rounding drift tolerance)
2. Generalised subtotal roll-up verification:
   - Uses hierarchy_path and RowRole directly rather than hard-coding account names.
   - For any SUBTOTAL (or GRAND_TOTAL) row S with hierarchy_path P:
       parent_path = P[:-1]  (the section S closes)
       child_subtotals = SUBTOTAL rows whose path starts with parent_path and is strictly deeper
       if child_subtotals:
           summands = child_subtotals at the shallowest level (avoids double-counting nested subtotals)
       else:
           summands = all LINE_ITEM + NET_ITEM rows whose path starts with parent_path
   - Checks rollup sum against printed subtotal with 千円-truncation tolerance (± summand_count).
3. Structural completeness checks:
   - SECTION_HEADER rows must have empty values dict.
   - Non-header rows must have valid CellValues for each declared period.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.schema import (
    BalanceSheetRow,
    CellValue,
    ParsedBalanceSheet,
    RowRole,
)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class TripletResult:
    """Result of one gross/dep/net triplet check (per period)."""
    triplet_label: str          # e.g. '建物及び構築物'
    period: str
    gross: int
    accum_depr: int             # negative in schema
    net_printed: int            # what the PDF says
    net_computed: int           # gross + accum_depr
    diff: int                   # net_printed - net_computed (0 = exact)
    exact_match: bool
    within_rounding_tolerance: bool   # abs(diff) <= 1 (千円 truncation/rounding)
    passed: bool


@dataclass
class RollupResult:
    """Result of one subtotal roll-up check (per period)."""
    subtotal_label: str         # e.g. '流動資産合計'
    period: str
    summand_labels: list[str]
    summand_count: int
    sum_computed: int
    sum_printed: int
    diff: int                   # sum_printed - sum_computed
    exact_match: bool
    within_rounding_tolerance: bool   # abs(diff) <= summand_count


@dataclass
class StructuralIssue:
    row_index: int
    label: str
    role: RowRole
    period: Optional[str]
    issue: str


@dataclass
class VerificationReport:
    """Aggregated result of all verifier checks."""
    triplet_results: list[TripletResult] = field(default_factory=list)
    rollup_results: list[RollupResult] = field(default_factory=list)
    structural_issues: list[StructuralIssue] = field(default_factory=list)

    @property
    def all_triplets_passed(self) -> bool:
        return all(r.passed for r in self.triplet_results)

    @property
    def all_rollups_within_tolerance(self) -> bool:
        return all(r.within_rounding_tolerance for r in self.rollup_results)

    @property
    def structurally_clean(self) -> bool:
        return len(self.structural_issues) == 0

    @property
    def passed(self) -> bool:
        return (
            self.all_triplets_passed
            and self.all_rollups_within_tolerance
            and self.structurally_clean
        )

    def summary(self) -> str:
        lines = [
            "=== Verification Report ===",
            f"Triplets   : {'PASS' if self.all_triplets_passed else 'FAIL'} "
            f"({sum(r.passed for r in self.triplet_results)}/{len(self.triplet_results)} passed)",
            f"Rollups    : {'PASS' if self.all_rollups_within_tolerance else 'FAIL'} "
            f"({sum(r.within_rounding_tolerance for r in self.rollup_results)}/{len(self.rollup_results)} within tolerance)",
            f"Structural : {'CLEAN' if self.structurally_clean else 'ISSUES'} "
            f"({len(self.structural_issues)} issues)",
            f"Overall    : {'PASS' if self.passed else 'FAIL'}",
        ]
        if self.triplet_results:
            lines.append("\nTriplet details:")
            for t in self.triplet_results:
                tag = "OK" if t.passed else "FAIL"
                exact = "exact" if t.exact_match else f"drift={t.diff:+d}"
                lines.append(
                    f"  [{tag}] {t.triplet_label} [{t.period}]  "
                    f"gross={t.gross:,}  depr={t.accum_depr:,}  "
                    f"net_printed={t.net_printed:,}  net_computed={t.net_computed:,}  "
                    f"{exact}"
                )
        if self.rollup_results:
            lines.append("\nRollup details:")
            for r in self.rollup_results:
                tag = "OK" if r.within_rounding_tolerance else "FAIL"
                exact = "exact" if r.exact_match else f"drift={r.diff:+d}"
                lines.append(
                    f"  [{tag}] {r.subtotal_label} [{r.period}]  "
                    f"printed={r.sum_printed:,}  computed={r.sum_computed:,}  "
                    f"{exact}  tolerance=±{r.summand_count}"
                )
        if self.structural_issues:
            lines.append("\nStructural issues:")
            for s in self.structural_issues:
                lines.append(
                    f"  row[{s.row_index}] '{s.label}' ({s.role})"
                    + (f" period={s.period}" if s.period else "")
                    + f": {s.issue}"
                )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _ev(row: BalanceSheetRow, period: str) -> Optional[int]:
    """Return effective_value() for the cell, or None if missing."""
    cell = row.values.get(period)
    if cell is None:
        return None
    return cell.effective_value()


def _path_prefix(path: list[str], prefix: list[str]) -> bool:
    """Return True if path starts with prefix."""
    return len(path) >= len(prefix) and path[:len(prefix)] == prefix


# ---------------------------------------------------------------------------
# Check 1 — Gross / Depreciation / Net triplets
# ---------------------------------------------------------------------------

def _check_triplets(
    bs: ParsedBalanceSheet,
    report: VerificationReport,
) -> None:
    """
    For each gross/dep/net triplet under 有形固定資産, verify:
        GROSS_ITEM.effective_value() + ACCUM_DEPR.effective_value() ≈ NET_ITEM.effective_value()
    Allows ±1 千円 rounding drift tolerance.
    """
    rows = bs.rows
    n = len(rows)
    periods = bs.metadata.periods

    i = 0
    while i < n:
        row = rows[i]
        if row.role != RowRole.GROSS_ITEM:
            i += 1
            continue
        if i + 2 >= n:
            i += 1
            continue
        depr_row = rows[i + 1]
        net_row = rows[i + 2]
        if depr_row.role != RowRole.ACCUM_DEPR or net_row.role != RowRole.NET_ITEM:
            i += 1
            continue

        triplet_label = row.label

        for period in periods:
            gross = _ev(row, period)
            depr = _ev(depr_row, period)
            net = _ev(net_row, period)

            if gross is None or depr is None or net is None:
                report.structural_issues.append(StructuralIssue(
                    row_index=row.row_index,
                    label=triplet_label,
                    role=RowRole.GROSS_ITEM,
                    period=period,
                    issue="Missing value in triplet — cannot verify gross/dep/net.",
                ))
                continue

            computed = gross + depr
            diff = net - computed
            exact = (diff == 0)
            within_tol = (abs(diff) <= 1)

            report.triplet_results.append(TripletResult(
                triplet_label=triplet_label,
                period=period,
                gross=gross,
                accum_depr=depr,
                net_printed=net,
                net_computed=computed,
                diff=diff,
                exact_match=exact,
                within_rounding_tolerance=within_tol,
                passed=within_tol,
            ))
        i += 3


# ---------------------------------------------------------------------------
# Check 2 — Generalised subtotal roll-up (hierarchy_path based)
# ---------------------------------------------------------------------------

def _check_rollups(
    bs: ParsedBalanceSheet,
    report: VerificationReport,
) -> None:
    """
    Check every SUBTOTAL and GRAND_TOTAL against the sum of its child summands.
    Discovers summands dynamically from hierarchy_path:
    - If the section contains child SUBTOTALs, sum child SUBTOTALs at the shallowest level.
    - Otherwise, sum all LINE_ITEM and NET_ITEM rows in the section.
    """
    rows = bs.rows
    periods = bs.metadata.periods
    subtotals = [r for r in rows if r.role in (RowRole.SUBTOTAL, RowRole.GRAND_TOTAL)]

    for st_row in subtotals:
        parent_path = st_row.hierarchy_path[:-1]

        # Find any other subtotals strictly inside parent_path
        child_subs = [
            r for r in rows
            if r is not st_row
            and r.role in (RowRole.SUBTOTAL, RowRole.GRAND_TOTAL)
            and _path_prefix(r.hierarchy_path, parent_path)
            and len(r.hierarchy_path) > len(parent_path)
        ]

        if child_subs:
            # Use the shallowest level of child subtotals to avoid double-counting
            min_len = min(len(r.hierarchy_path) for r in child_subs)
            summand_rows = [r for r in child_subs if len(r.hierarchy_path) == min_len]
        else:
            # Leaf section: sum LINE_ITEM and NET_ITEM rows (ignores GROSS_ITEM / ACCUM_DEPR)
            summand_rows = [
                r for r in rows
                if r.role in (RowRole.LINE_ITEM, RowRole.NET_ITEM)
                and _path_prefix(r.hierarchy_path, parent_path)
            ]

        for period in periods:
            summand_values: list[int] = []
            labels_used: list[str] = []
            skip = False

            for sr in summand_rows:
                v = _ev(sr, period)
                if v is None:
                    report.structural_issues.append(StructuralIssue(
                        row_index=sr.row_index,
                        label=sr.label,
                        role=sr.role,
                        period=period,
                        issue=f"Missing value needed for '{st_row.label}' rollup check.",
                    ))
                    skip = True
                    break
                summand_values.append(v)
                labels_used.append(sr.label)

            if skip:
                continue

            st_val = _ev(st_row, period)
            if st_val is None:
                report.structural_issues.append(StructuralIssue(
                    row_index=st_row.row_index,
                    label=st_row.label,
                    role=st_row.role,
                    period=period,
                    issue="Subtotal cell is missing/nil — cannot verify rollup.",
                ))
                continue

            computed = sum(summand_values)
            diff = st_val - computed
            n_summands = len(summand_values)

            report.rollup_results.append(RollupResult(
                subtotal_label=st_row.label,
                period=period,
                summand_labels=labels_used,
                summand_count=n_summands,
                sum_computed=computed,
                sum_printed=st_val,
                diff=diff,
                exact_match=(diff == 0),
                within_rounding_tolerance=(abs(diff) <= n_summands),
            ))


# ---------------------------------------------------------------------------
# Check 3 — Structural completeness
# ---------------------------------------------------------------------------

def _check_structure(
    bs: ParsedBalanceSheet,
    report: VerificationReport,
) -> None:
    """
    - SECTION_HEADER rows must have empty values dict.
    - Every non-header row must have a valid CellValue for each declared period.
    """
    periods = bs.metadata.periods

    for row in bs.rows:
        if row.role == RowRole.SECTION_HEADER:
            if row.values:
                report.structural_issues.append(StructuralIssue(
                    row_index=row.row_index,
                    label=row.label,
                    role=row.role,
                    period=None,
                    issue="SECTION_HEADER row has non-empty values dict.",
                ))
        else:
            for period in periods:
                cell = row.values.get(period)
                if cell is None:
                    report.structural_issues.append(StructuralIssue(
                        row_index=row.row_index,
                        label=row.label,
                        role=row.role,
                        period=period,
                        issue=f"Missing CellValue for period '{period}'.",
                    ))
                elif cell.value is None and not cell.is_nil and not cell.is_negative_zero:
                    report.structural_issues.append(StructuralIssue(
                        row_index=row.row_index,
                        label=row.label,
                        role=row.role,
                        period=period,
                        issue="CellValue has value=None and is_nil=False and is_negative_zero=False — invalid for a non-header row.",
                    ))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def verify(bs: ParsedBalanceSheet) -> VerificationReport:
    """Run all three check families and return a VerificationReport."""
    report = VerificationReport()
    _check_triplets(bs, report)
    _check_rollups(bs, report)
    _check_structure(bs, report)
    return report
