"""
inspect_pdf.py
--------------
Step-1 diagnostic for balance_sheet_after_correction.pdf.
Writes output directly to outputs/inspect_pdf_output.txt (UTF-8) so that
Japanese/CJK characters are preserved exactly — bypassing Windows cp1252
console encoding that broke the text when piped through PowerShell.

Usage:
    py scripts/inspect_pdf.py [path/to/file.pdf] [output/path.txt]
"""

import sys
import pathlib
import pymupdf as fitz  # pymupdf >= 2.0


PDF_PATH = pathlib.Path(
    sys.argv[1] if len(sys.argv) > 1
    else "data/balance_sheet_after_correction.pdf"
)
OUTPUT_PATH = pathlib.Path(
    sys.argv[2] if len(sys.argv) > 2
    else "outputs/inspect_pdf_output.txt"
)

SECTION = "\n" + "=" * 80 + "\n"


def codepoints(s: str) -> str:
    """Return a readable codepoint dump for each char in s."""
    return " ".join(f"U+{ord(c):04X}({c!r})" for c in s)


def special_chars_report(text: str, specials="\u25b3\uff0d\u3007") -> str:
    """If text contains any special chars, return a codepoint annotation."""
    found = [c for c in specials if c in text]
    if not found:
        return ""
    return "  <<< " + " | ".join(codepoints(c) for c in found)


def main(out):
    p = lambda *a, **k: print(*a, **k, file=out)  # noqa: E731

    if not PDF_PATH.exists():
        sys.exit(f"[ERROR] File not found: {PDF_PATH}")

    doc = fitz.open(str(PDF_PATH))
    p(f"PDF: {PDF_PATH}")
    p(f"Pages: {doc.page_count}  |  PDF format: {doc.metadata.get('format', '?')}")
    p(f"Is encrypted: {doc.is_encrypted}  |  Is PDF: {doc.is_pdf}")

    for page_no, page in enumerate(doc):
        rect = page.rect
        p(SECTION)
        p(f"PAGE {page_no + 1}  --  size: {rect.width:.1f} x {rect.height:.1f} pt")

        # -- 1. Images --------------------------------------------------------
        images = page.get_images(full=True)
        p(f"\n[Images] count = {len(images)}")
        for i, img in enumerate(images):
            xref, smask, w, h, bpc, cs, alt_cs, name, filt = img[:9]
            p(f"  img[{i}]: xref={xref}, size={w}x{h}, bpc={bpc}, cs={cs}, filter={filt}")

        # -- 2. Vector drawings (lines, rects, curves) ------------------------
        drawings = page.get_drawings()
        p(f"\n[Vector Drawings] count = {len(drawings)}")
        lines_d = [d for d in drawings if any(item[0] == "l" for item in d.get("items", []))]
        rects_d = [d for d in drawings if any(item[0] == "re" for item in d.get("items", []))]
        p(f"  Drawings with line items : {len(lines_d)}")
        p(f"  Drawings with rect items : {len(rects_d)}")

        # Classify by height: thin black = rule/underline, tall colored = shading
        BLACK = (0.0, 0.0, 0.0)
        BLUE  = (0.8, 0.933, 1.0)   # approx
        rules     = [d for d in drawings
                     if d.get("fill") == BLACK and (d["rect"].height < 3)]
        underlines = [d for d in drawings
                     if d.get("fill") == BLACK and (d["rect"].height < 1)]
        shade_rows = [d for d in drawings
                      if d.get("fill") is not None
                      and d.get("fill") != BLACK
                      and d.get("fill") != (1.0, 1.0, 1.0)]
        p(f"  Black rule rects (h<3pt)  : {len(rules)}")
        p(f"  Narrow underlines (h<1pt) : {len(underlines)}")
        p(f"  Colored shading rects     : {len(shade_rows)}")

        p("\n  All drawings sorted by y0 (bbox, fill, height):")
        sorted_drawings = sorted(drawings, key=lambda d: (d["rect"].y0, d["rect"].x0))
        for d in sorted_drawings:
            bbox  = d["rect"]
            fill  = d.get("fill")
            h     = round(bbox.height, 3)
            b     = (round(bbox.x0,2), round(bbox.y0,2), round(bbox.x1,2), round(bbox.y1,2))
            p(f"    {b}  fill={fill}  h={h}")

        # -- 3. Text blocks / lines -------------------------------------------
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        text_blocks = [b for b in blocks if b["type"] == 0]
        total_lines = sum(len(b["lines"]) for b in text_blocks)
        p(f"\n[Text] blocks={len(text_blocks)}  lines={total_lines}")

        # Gather all spans with bbox info
        span_rows = []
        for block in text_blocks:
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"]
                    bbox = span["bbox"]   # (x0, y0, x1, y1)
                    font = span["font"]
                    size = round(span["size"], 1)
                    span_rows.append((bbox[1], bbox[0], bbox[2], bbox[3], text, font, size))

        # Sort by (y0, x0)
        span_rows.sort(key=lambda r: (r[0], r[1]))

        p(f"\n[Text lines sorted by (y0, x0)] -- total spans: {len(span_rows)}")
        p(f"  {'y0':>7}  {'x0':>7}  {'x1':>7}  {'font':<32}  {'sz':>4}  text")
        p(f"  {'-'*7}  {'-'*7}  {'-'*7}  {'-'*32}  {'-'*4}  ----")
        for y0, x0, x1, y1, text, font, size in span_rows:
            note = special_chars_report(text)
            p(f"  {y0:>7.2f}  {x0:>7.2f}  {x1:>7.2f}  {font:<32}  {size:>4}  {text!r}{note}")

        # -- 4. Special-symbol codepoint summary ------------------------------
        all_text = "".join(r[4] for r in span_rows)
        specials_found: dict[str, int] = {}
        for ch in all_text:
            if ord(ch) > 0x2000:  # non-ASCII / CJK / special
                specials_found[ch] = specials_found.get(ch, 0) + 1

        if specials_found:
            p(f"\n[Non-ASCII / Special characters found on page {page_no + 1}]")
            for ch, cnt in sorted(specials_found.items(), key=lambda x: -x[1]):
                p(f"  U+{ord(ch):04X}  {ch!r}  count={cnt}")

        # -- 5. Native text check ---------------------------------------------
        raw_text = page.get_text("text").strip()
        if raw_text:
            p(f"\n[Native text layer DETECTED] ({len(raw_text)} chars)")
        else:
            p("\n[No native text layer -- likely raster/scanned image]")

    doc.close()
    p(SECTION)
    p("Inspection complete.")


if __name__ == "__main__":
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
        main(fh)
    # Also echo a summary to console (ASCII-safe)
    print(f"[inspect_pdf] Output written to {OUTPUT_PATH}")
