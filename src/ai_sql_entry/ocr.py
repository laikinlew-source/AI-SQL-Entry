from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OcrResult:
    text: str
    page_paths: tuple[Path, ...]


def ocr_pdf(
    pdf_path: Path,
    work_dir: Path,
    *,
    pdftoppm_command: tuple[str, ...] = ("pdftoppm",),
    tesseract_command: tuple[str, ...] = ("tesseract",),
) -> OcrResult:
    """Render a PDF and OCR its pages locally."""
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF input: {pdf_path}")
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)

    pages_dir = work_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    output_prefix = pages_dir / "page"
    subprocess.run(
        [*pdftoppm_command, "-png", str(pdf_path), str(output_prefix)],
        check=True,
        capture_output=True,
        text=True,
    )

    rendered = sorted(
        pages_dir.glob("page-*.png"),
        key=lambda path: int(path.stem.rsplit("-", 1)[1]),
    )
    if not rendered:
        raise RuntimeError("PDF renderer produced no page images")

    page_paths = []
    for position, rendered_path in enumerate(rendered, start=1):
        normalized_path = pages_dir / f"page-{position:04d}.png"
        rendered_path.replace(normalized_path)
        page_paths.append(normalized_path)

    page_text = []
    for page_path in page_paths:
        completed = subprocess.run(
            [*tesseract_command, str(page_path), "stdout", "-l", "eng"],
            check=True,
            capture_output=True,
            text=True,
        )
        page_text.append(completed.stdout.strip())

    return OcrResult(text="\n\n".join(page_text), page_paths=tuple(page_paths))
