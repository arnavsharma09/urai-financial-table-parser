"""
scripts/run_parse.py
--------------------
CLI runner to parse balance_sheet_after_correction.pdf, run the accounting
verification harness, print reports, and output structured JSON and Markdown.

Usage:
    py scripts/run_parse.py [path/to/balance_sheet.pdf]
"""

from __future__ import annotations

import pathlib
import sys

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure project root is on sys.path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.parser import parse_balance_sheet
from src.schema import ParsedBalanceSheet, RowRole
from src.verifier import verify, VerificationReport


def build_markdown_table(bs: ParsedBalanceSheet) -> str:
    """Format parsed balance sheet rows as a Markdown table."""
    p1, p2 = bs.metadata.periods[0], bs.metadata.periods[1]
    headers = [
        "Idx",
        "Role",
        "Indent",
        "Account Label",
        f"Prior ({p1})",
        f"Current ({p2})",
        "Hierarchy Path",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for r in bs.rows:
        c1 = r.values.get(p1)
        c2 = r.values.get(p2)

        def fmt_cell(c):
            if c is None:
                return "—"
            txt = c.raw_text
            if c.is_amended:
                txt = f"**{txt}** *(amended)*"
            elif c.is_negative_zero:
                txt = f"{txt} *(△0)*"
            elif c.is_nil:
                txt = f"{txt} *(nil)*"
            return txt

        v1_str = fmt_cell(c1)
        v2_str = fmt_cell(c2)
        indent_prefix = "&nbsp;&nbsp;" * r.indent_level
        display_label = f"{indent_prefix}{r.label}"
        path_str = " > ".join(r.hierarchy_path)

        row_cols = [
            str(r.row_index),
            r.role.value,
            str(r.indent_level),
            display_label,
            v1_str,
            v2_str,
            f"`{path_str}`",
        ]
        lines.append("| " + " | ".join(row_cols) + " |")

    return "\n".join(lines)


def main():
    pdf_path = pathlib.Path(
        sys.argv[1] if len(sys.argv) > 1
        else "data/balance_sheet_after_correction.pdf"
    )
    if not pdf_path.exists():
        print(f"[ERROR] PDF file not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing: {pdf_path} ...")
    bs = parse_balance_sheet(pdf_path)
    print(f"Parsed {len(bs.rows)} rows successfully.")

    # Run verification harness
    report: VerificationReport = verify(bs)
    print("\n" + report.summary())

    # Build Markdown table
    md_table = build_markdown_table(bs)
    print("\n=== Parsed Balance Sheet Table ===")
    print(md_table)

    # Save outputs
    outputs_dir = pathlib.Path("outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)

    json_path = outputs_dir / "parsed_balance_sheet.json"
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(bs.model_dump_json(indent=2))
    print(f"\n[Saved JSON] {json_path}")

    md_path = outputs_dir / "parsed_balance_sheet.md"
    full_md = (
        f"# {bs.metadata.title} (Parsed Output)\n\n"
        f"- **Unit**: {bs.metadata.unit}\n"
        f"- **Is Amended Filing**: {bs.metadata.is_amended_filing}\n"
        f"- **Periods**: {', '.join(bs.metadata.periods)}\n"
        f"- **Verification**: {'PASS' if report.passed else 'FAIL'}\n\n"
        f"## Verification Report\n\n```text\n{report.summary()}\n```\n\n"
        f"## Extracted Table\n\n{md_table}\n"
    )
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(full_md)
    print(f"[Saved Markdown] {md_path}")

    if not report.passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
