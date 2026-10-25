"""
tests/test_vlm_fallback.py
--------------------------
Unit tests for src/vlm_fallback.py using MockVLMClient (100% offline).
"""

from __future__ import annotations

import copy
import json
import pathlib
import pytest

from src.parser import parse_balance_sheet
from src.schema import BalanceSheetMetadata, BalanceSheetRow, CellValue, ParsedBalanceSheet, RowRole
from src.verifier import verify
from src.vlm_fallback import MockVLMClient, VerifierGuidedFallback


PDF_PATH = pathlib.Path("data/balance_sheet_after_correction.pdf")


def test_raster_detection():
    import pymupdf as fitz
    doc = fitz.open(str(PDF_PATH))
    page = doc[0]
    # Real PDF has text spans -> not raster
    assert VerifierGuidedFallback.is_raster_pdf(page) is False


def test_raster_fallback_with_mock_vlm():
    """Simulate raster PDF fallback returning a valid ParsedBalanceSheet via MockVLMClient."""
    mock_payload = {
        "metadata": {
            "title": "連結貸借対照表 (Raster Fallback)",
            "is_amended_filing": False,
            "unit": "千円",
            "periods": ["2025-03-31", "2026-03-31"],
        },
        "rows": [
            {
                "row_index": 0,
                "label": "資産の部",
                "indent_level": 0,
                "hierarchy_path": ["資産の部"],
                "role": "SECTION_HEADER",
                "values": {},
                "y_coord": 100.0,
            },
            {
                "row_index": 1,
                "label": "流動資産合計",
                "indent_level": 1,
                "hierarchy_path": ["資産の部", "流動資産合計"],
                "role": "SUBTOTAL",
                "values": {
                    "2025-03-31": {"raw_text": "1,000", "value": 1000},
                    "2026-03-31": {"raw_text": "2,000", "value": 2000},
                },
                "y_coord": 120.0,
            },
        ],
    }

    mock_client = MockVLMClient(canned_response=json.dumps(mock_payload))
    fallback = VerifierGuidedFallback(vlm_client=mock_client)

    bs = fallback.handle_raster_pdf(PDF_PATH)
    assert bs.metadata.title == "連結貸借対照表 (Raster Fallback)"
    assert len(bs.rows) == 2
    assert bs.rows[1].values["2025-03-31"].value == 1000
    assert len(mock_client.call_history) == 1
    assert "J-GAAP" in mock_client.call_history[0]["prompt"]


def test_targeted_crop_and_repair_on_discrepancy():
    """
    Simulate a balance sheet with an induced rollup error (e.g. OCR misread digit),
    and verify that VerifierGuidedFallback crops the section and repairs it.
    """
    clean_bs = parse_balance_sheet(PDF_PATH)

    # Induce an error in 流動資産: change 現金及び預金 from 2,002,429 to 2,002,400 (drift -29)
    corrupted_bs = copy.deepcopy(clean_bs)
    cash_row = next(r for r in corrupted_bs.rows if r.label == "現金及び預金")
    p1 = clean_bs.metadata.periods[0]
    cash_row.values[p1].value = 2_002_400

    report = verify(corrupted_bs)
    assert report.passed is False

    # Mock VLM returns the repaired section rows (restoring original cash row)
    repaired_section = [
        r.model_dump()
        for r in clean_bs.rows
        if r.hierarchy_path[:2] == ["資産の部", "流動資産"]
    ]
    mock_response = json.dumps({"repaired_rows": repaired_section})

    mock_client = MockVLMClient(canned_response=mock_response)
    fallback = VerifierGuidedFallback(vlm_client=mock_client)

    repaired_bs, success = fallback.repair_failing_section(
        bs=corrupted_bs,
        pdf_path=PDF_PATH,
        subtotal_label="流動資産合計",
        period=p1,
        discrepancy_str="Computed sum = 5,863,652, Printed = 5,863,684, Drift = -32",
    )

    assert success is True
    assert verify(repaired_bs).passed is True
    assert len(mock_client.call_history) == 1
    prompt_sent = mock_client.call_history[0]["prompt"]
    assert "Discrepancy Alert" in prompt_sent
    assert "流動資産合計" in prompt_sent
    # Image bytes were generated from crop
    assert mock_client.call_history[0]["image_size"] > 0
