"""
src/schema.py
-------------
Pydantic v2 data model for a parsed J-GAAP Consolidated Balance Sheet
(連結貸借対照表).

Design notes:
- CellValue.is_nil (U+FF0D "－") and CellValue.is_negative_zero (△0) are
  kept as DISTINCT flags.  In J-GAAP 千円 filings:
    - is_nil  → no balance exists; treat as 0 only when summing.
    - is_negative_zero → an existing balance that rounds to zero at the 千円
      unit level; value=0 but the account is active.
- value is None only for SECTION_HEADER rows (no numeric cell at all).
- hierarchy_path provides the full ancestry list so that repeated labels
  (その他, リース資産, 減価償却累計額, etc.) are unambiguously identified.
- is_amended on CellValue is True when the PDF contains a narrow correction
  underline rect directly beneath that specific cell (as seen under 218,836
  and 1,123 on the 訂正後 page).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# BBox / CellValue
# ---------------------------------------------------------------------------

class BBox(BaseModel):
    """Bounding box in PDF user-space points (origin = top-left)."""
    x0: float
    y0: float
    x1: float
    y1: float


class CellValue(BaseModel):
    """
    A single numeric (or nil) cell in the balance sheet.

    Exactly one of the following states is canonical:
      - is_nil=True          : value must be None  (printed as "－")
      - is_negative_zero=True: value must be 0     (printed as "△0")
      - value is not None    : an actual integer (negative if △ prefix)
      - value is None and not is_nil : only valid for SECTION_HEADER rows
    """

    raw_text: str = Field(
        description=(
            "Verbatim text as extracted from the PDF span(s), "
            "e.g. '△2,979' or '－' or '218,836'."
        )
    )
    value: Optional[int] = Field(
        default=None,
        description=(
            "Parsed integer.  Negative for △ values.  "
            "None if nil (is_nil=True) or no cell (header)."
        ),
    )
    is_nil: bool = Field(
        default=False,
        description=(
            "True when the cell contains U+FF0D '－', meaning "
            "the account has no balance this period.  "
            "When summing, treat as 0."
        ),
    )
    is_negative_zero: bool = Field(
        default=False,
        description=(
            "True when the cell shows '△0': the account has an "
            "existing balance that rounds to zero at 千円 precision. "
            "value=0 but semantically different from is_nil."
        ),
    )
    is_amended: bool = Field(
        default=False,
        description=(
            "True when a narrow correction-underline rect sits "
            "directly beneath this cell in the PDF (訂正後 marking)."
        ),
    )
    bbox: Optional[BBox] = Field(
        default=None,
        description="Bounding box of the cell's text span(s) in PDF points.",
    )

    @model_validator(mode="after")
    def _check_consistency(self) -> "CellValue":
        if self.is_nil and self.value is not None:
            raise ValueError("is_nil=True requires value=None")
        if self.is_negative_zero and self.value != 0:
            raise ValueError("is_negative_zero=True requires value=0")
        if self.is_nil and self.is_negative_zero:
            raise ValueError("is_nil and is_negative_zero cannot both be True")
        return self

    def effective_value(self) -> int:
        """Return value suitable for arithmetic (nil -> 0, △0 -> 0)."""
        if self.is_nil:
            return 0
        return self.value if self.value is not None else 0


# ---------------------------------------------------------------------------
# RowRole
# ---------------------------------------------------------------------------

class RowRole(str, Enum):
    """
    Semantic role of a row in the balance sheet.

    Gross/depreciation/net triplets under 有形固定資産:
      GROSS_ITEM  - the pre-depreciation gross amount line
      ACCUM_DEPR  - 減価償却累計額 (negative; accumulated depreciation)
      NET_ITEM    - ...(純額) line; should equal GROSS_ITEM + ACCUM_DEPR

    Other roles:
      SECTION_HEADER - 資産の部 / 流動資産 / 固定資産 / 有形固定資産 etc.
                       (no numeric values)
      LINE_ITEM      - standard account line (e.g. 現金及び預金, 土地)
      SUBTOTAL       - ...合計 lines (流動資産合計, 有形固定資産合計, ...)
      GRAND_TOTAL    - 資産合計 (the final total)
    """

    SECTION_HEADER = "SECTION_HEADER"
    LINE_ITEM      = "LINE_ITEM"
    GROSS_ITEM     = "GROSS_ITEM"
    ACCUM_DEPR     = "ACCUM_DEPR"
    NET_ITEM       = "NET_ITEM"
    SUBTOTAL       = "SUBTOTAL"
    GRAND_TOTAL    = "GRAND_TOTAL"


# ---------------------------------------------------------------------------
# BalanceSheetRow
# ---------------------------------------------------------------------------

class BalanceSheetRow(BaseModel):
    """One row of the balance sheet."""

    row_index: int = Field(
        description="Zero-based parse order index (top-to-bottom on the page)."
    )
    label: str = Field(
        description="Account label exactly as extracted (e.g. '現金及び預金')."
    )
    indent_level: int = Field(
        ge=0,
        description=(
            "Visual indentation depth derived from x0 coordinate. "
            "0 = leftmost (資産の部), 1 = 流動資産/固定資産, "
            "2 = direct children, 3 = sub-items, 4 = gross/dep sub-rows."
        ),
    )
    hierarchy_path: list[str] = Field(
        description=(
            "Full ancestor chain including this row's own label, "
            "e.g. ['資産の部', '固定資産', '有形固定資産', '建物及び構築物', "
            "'減価償却累計額'].  Used to disambiguate repeated labels."
        )
    )
    role: RowRole = Field(
        description="Semantic role of this row (see RowRole enum)."
    )
    values: dict[str, CellValue] = Field(
        default_factory=dict,
        description=(
            "Mapping from period key to cell value.  "
            "Period keys are strings like '2025-03-31' or '前期'/'当期'. "
            "SECTION_HEADER rows must have an empty dict."
        ),
    )
    y_coord: float = Field(
        description="y0 coordinate of the row's text span on the PDF page."
    )

    @model_validator(mode="after")
    def _check_header_empty(self) -> "BalanceSheetRow":
        if self.role == RowRole.SECTION_HEADER and self.values:
            raise ValueError(
                f"SECTION_HEADER row '{self.label}' must have empty values dict."
            )
        return self

    @model_validator(mode="after")
    def _check_non_header_has_values(self) -> "BalanceSheetRow":
        if self.role != RowRole.SECTION_HEADER and not self.values:
            raise ValueError(
                f"Non-header row '{self.label}' (role={self.role}) "
                "must have at least one value."
            )
        return self


# ---------------------------------------------------------------------------
# ParsedBalanceSheet
# ---------------------------------------------------------------------------

class BalanceSheetMetadata(BaseModel):
    title: str = Field(
        description="Document title, e.g. '連結貸借対照表'."
    )
    is_amended_filing: bool = Field(
        default=False,
        description="True when this is a 訂正後 (post-correction) filing.",
    )
    unit: str = Field(
        default="千円",
        description="Reporting unit, e.g. '千円' or '百万円'.",
    )
    periods: list[str] = Field(
        description=(
            "Ordered list of period keys matching keys in "
            "BalanceSheetRow.values, e.g. ['2025-03-31', '2026-03-31']."
        )
    )


class ParsedBalanceSheet(BaseModel):
    """Top-level output of the balance sheet parser."""

    metadata: BalanceSheetMetadata
    rows: list[BalanceSheetRow] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def rows_by_role(self, role: RowRole) -> list[BalanceSheetRow]:
        """Return all rows with the given role."""
        return [r for r in self.rows if r.role == role]

    def row_by_path(self, *path_suffix: str) -> Optional[BalanceSheetRow]:
        """
        Find the first row whose hierarchy_path ends with *path_suffix.
        E.g. row_by_path('有形固定資産', '建物及び構築物', '減価償却累計額').
        """
        suffix = list(path_suffix)
        n = len(suffix)
        for row in self.rows:
            if row.hierarchy_path[-n:] == suffix:
                return row
        return None

    def get_value(self, row: BalanceSheetRow, period: str) -> Optional[CellValue]:
        """Return the CellValue for the given period, or None if absent."""
        return row.values.get(period)
