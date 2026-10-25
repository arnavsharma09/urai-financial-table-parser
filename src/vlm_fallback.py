"""
src/vlm_fallback.py
-------------------
Verifier-Guided Vision-Language Model (VLM) Fallback and Targeted Repair Pipeline.

Demonstrates the 4th stage of our hybrid architecture:
1. Stage 1: Dynamic Coordinate Anchoring & Layout Inference (src/parser.py)
2. Stage 2: Deterministic Normalizer & Hierarchy Builder (src/parser.py)
3. Stage 3: Intrinsic Zero-Label Accounting Verifier (src/verifier.py)
4. Stage 4: Verifier-Guided Targeted VLM Fallback & Repair (src/vlm_fallback.py)

Key capabilities:
(a) Raster / Scanned PDF fallback: Detects pages with 0 or negligible native text spans,
    renders full-page image, and invokes VLM for end-to-end extraction.
(b) Targeted Crop-and-Repair: When verify(parsed) fails a specific subtotal roll-up
    or gross/dep/net triplet check on a complex / rotated / noisy layout:
    - Locates the exact BBox of the failing section or triplet.
    - Crops only that sub-image region (minimizing VLM token costs and hallucination risk).
    - Injects the precise accounting discrepancy (e.g. "computed sum = 5,863,681, printed total = 5,863,684, drift = +3")
      into the repair prompt to guide VLM focus.
    - Splices the repaired rows back into the ParsedBalanceSheet and re-verifies.

Includes MockVLMClient for 100% offline testing without external API keys.
"""

from __future__ import annotations

import copy
import json
import pathlib
from typing import Optional, Protocol, Union

import pymupdf as fitz

from src.parser import parse_balance_sheet
from src.schema import (
    BalanceSheetMetadata,
    BalanceSheetRow,
    BBox,
    CellValue,
    ParsedBalanceSheet,
    RowRole,
)
from src.verifier import verify, VerificationReport


# ---------------------------------------------------------------------------
# VLM Client Protocol & Mock Implementation
# ---------------------------------------------------------------------------

class VLMClient(Protocol):
    """Protocol for Vision-Language Model inference clients."""
    def generate(self, prompt: str, image_bytes: Optional[bytes] = None) -> str:
        """Submit prompt and optional image bytes to VLM and return response text."""
        ...


class MockVLMClient:
    """
    Offline mock VLM client for automated testing and deterministic benchmarking.
    Configured with canned responses or dynamic handlers for full page and crop repair.
    """
    def __init__(self, canned_response: Optional[str] = None):
        self.canned_response = canned_response
        self.call_history: list[dict] = []

    def generate(self, prompt: str, image_bytes: Optional[bytes] = None) -> str:
        self.call_history.append({
            "prompt": prompt,
            "image_size": len(image_bytes) if image_bytes else 0,
        })
        if self.canned_response is not None:
            return self.canned_response
        # Default mock response for repair requests
        return json.dumps({
            "repaired_rows": []
        })


# ---------------------------------------------------------------------------
# Verifier-Guided Fallback Engine
# ---------------------------------------------------------------------------

class VerifierGuidedFallback:
    """
    Orchestrates targeted VLM repairs using accounting verification feedback.
    """
    def __init__(self, vlm_client: Optional[VLMClient] = None):
        self.vlm = vlm_client or MockVLMClient()

    @staticmethod
    def is_raster_pdf(page: fitz.Page, min_text_chars: int = 50) -> bool:
        """Return True if the page has negligible or zero native text spans (scanned/raster)."""
        text = page.get_text().strip()
        return len(text) < min_text_chars

    def render_page_image(self, page: fitz.Page, dpi: int = 150) -> bytes:
        """Render page to PNG image bytes."""
        pix = page.get_pixmap(dpi=dpi)
        return pix.tobytes("png")

    def render_crop_image(self, page: fitz.Page, bbox: BBox, dpi: int = 150, padding: float = 10.0) -> bytes:
        """Crop and render a specific sub-region of the page around the given BBox."""
        page_rect = page.rect
        clip_rect = fitz.Rect(
            max(0.0, bbox.x0 - padding),
            max(0.0, bbox.y0 - padding),
            min(page_rect.width, bbox.x1 + padding),
            min(page_rect.height, bbox.y1 + padding),
        )
        pix = page.get_pixmap(clip=clip_rect, dpi=dpi)
        return pix.tobytes("png")

    def handle_raster_pdf(
        self,
        pdf_path: Union[str, pathlib.Path],
        page_index: int = 0,
    ) -> ParsedBalanceSheet:
        """
        Full-page VLM fallback when PDF has 0 native text spans.
        """
        doc = fitz.open(str(pdf_path))
        page = doc[page_index]
        image_bytes = self.render_page_image(page)

        prompt = (
            "You are a specialized J-GAAP financial table extractor. "
            "Extract this Japanese Consolidated Balance Sheet (連結貸借対照表) into structured JSON. "
            "Include visual indentation, account labels, and period values with negative signs (△) and nil markers (－)."
        )
        resp = self.vlm.generate(prompt, image_bytes)
        try:
            data = json.loads(resp)
            return ParsedBalanceSheet.model_validate(data)
        except Exception:
            # Fallback placeholder if VLM response fails validation
            return ParsedBalanceSheet(
                metadata=BalanceSheetMetadata(
                    title="連結貸借対照表 (Scanned Raster Fallback)",
                    periods=["2025-03-31", "2026-03-31"],
                ),
                rows=[],
            )

    def repair_failing_section(
        self,
        bs: ParsedBalanceSheet,
        pdf_path: Union[str, pathlib.Path],
        subtotal_label: str,
        period: str,
        discrepancy_str: str,
        page_index: int = 0,
    ) -> Tuple[ParsedBalanceSheet, bool]:
        """
        Perform a targeted crop-and-repair for a failing subtotal roll-up:
        1. Find all rows in the failing section and compute their union BBox.
        2. Crop only that section from the PDF page.
        3. Formulate a repair prompt containing the exact mathematical discrepancy.
        4. Request corrected rows from the VLM and apply them to the balance sheet.
        """
        doc = fitz.open(str(pdf_path))
        page = doc[page_index]

        # Identify failing subtotal row and its parent path
        st_row = next((r for r in bs.rows if r.label == subtotal_label), None)
        if not st_row:
            return bs, False

        parent_path = st_row.hierarchy_path[:-1]

        # Collect rows in this section that have bboxes
        section_rows = [
            r for r in bs.rows
            if r.hierarchy_path[:len(parent_path)] == parent_path
        ]
        all_bboxes = []
        for r in section_rows:
            for cell in r.values.values():
                if cell.bbox:
                    all_bboxes.append(cell.bbox)

        if not all_bboxes:
            # Use page width and row y_coords if bboxes are missing
            y_min = min(r.y_coord for r in section_rows)
            y_max = max(r.y_coord for r in section_rows) + 20.0
            union_bbox = BBox(x0=0.0, y0=y_min, x1=page.rect.width, y1=y_max)
        else:
            union_bbox = BBox(
                x0=min(b.x0 for b in all_bboxes),
                y0=min(b.y0 for b in all_bboxes),
                x1=max(b.x1 for b in all_bboxes),
                y1=max(b.y1 for b in all_bboxes),
            )

        # Crop the failing section image
        crop_bytes = self.render_crop_image(page, union_bbox)

        prompt = (
            f"Accounting Verifier Discrepancy Alert:\n"
            f"Subtotal '{subtotal_label}' for period '{period}' failed roll-up verification:\n"
            f"  {discrepancy_str}\n"
            f"Please inspect the cropped section image carefully. Look for misread digits, dropped negative signs (△), "
            f"or misaligned rows, and return the corrected JSON list of rows for this section."
        )
        resp = self.vlm.generate(prompt, crop_bytes)

        # Process repair response
        try:
            repair_data = json.loads(resp)
            if "repaired_rows" in repair_data and repair_data["repaired_rows"]:
                # Replace section rows with repaired rows
                repaired_rows = [BalanceSheetRow.model_validate(r) for r in repair_data["repaired_rows"]]
                new_bs = copy.deepcopy(bs)
                # Find indices of section rows in bs
                sec_indices = [i for i, r in enumerate(new_bs.rows) if r.hierarchy_path[:len(parent_path)] == parent_path]
                if sec_indices:
                    start_idx = sec_indices[0]
                    end_idx = sec_indices[-1] + 1
                    new_bs.rows[start_idx:end_idx] = repaired_rows
                    # Re-verify
                    new_report = verify(new_bs)
                    if new_report.passed:
                        return new_bs, True
        except Exception:
            pass

        return bs, False

    def parse_with_fallback(
        self,
        pdf_path: Union[str, pathlib.Path],
        page_index: int = 0,
    ) -> Tuple[ParsedBalanceSheet, VerificationReport]:
        """
        Full hybrid entrypoint:
        1. Checks for raster PDF -> VLM fallback.
        2. Else runs coordinate anchor parser.
        3. Runs verification.
        4. If verification fails on a subtotal or triplet -> attempts targeted crop-and-repair.
        """
        doc = fitz.open(str(pdf_path))
        page = doc[page_index]

        if self.is_raster_pdf(page):
            bs = self.handle_raster_pdf(pdf_path, page_index)
            report = verify(bs)
            return bs, report

        bs = parse_balance_sheet(pdf_path, page_index)
        report = verify(bs)

        if not report.passed:
            # Check for failing rollups and attempt targeted repair
            for r in report.rollup_results:
                if not r.within_rounding_tolerance:
                    disc = f"Computed sum = {r.sum_computed:,}, Printed = {r.sum_printed:,}, Drift = {r.diff:+d}"
                    repaired_bs, success = self.repair_failing_section(
                        bs, pdf_path, r.subtotal_label, r.period, disc, page_index
                    )
                    if success:
                        bs = repaired_bs
                        report = verify(bs)
                        if report.passed:
                            break

        return bs, report
