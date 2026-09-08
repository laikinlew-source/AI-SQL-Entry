from __future__ import annotations

import sys
from pathlib import Path


mode = sys.argv[1]
if mode == "render":
    if Path(sys.argv[-2]).name == "broken.pdf":
        raise SystemExit(2)
    output_prefix = Path(sys.argv[-1])
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    (output_prefix.parent / f"{output_prefix.name}-1.png").write_bytes(b"page one")
    (output_prefix.parent / f"{output_prefix.name}-2.png").write_bytes(b"page two")
elif mode == "ocr":
    page = Path(sys.argv[2])
    print(f"OCR text from {page.stem}")
elif mode == "invoice_ocr":
    page = Path(sys.argv[2])
    if page.stem == "page-0001":
        print((Path(__file__).parent / "invoice_ocr.txt").read_text(encoding="utf-8"))
else:
    raise SystemExit(f"Unknown mode: {mode}")
