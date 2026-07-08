"""Audit the links of embedded papers as a regression guard.

Re-derives, from the source PDFs and the placement metadata, where every
embedded link *should* point, and checks the compiled document against it:

1. Faithfulness - every source link survived: the embedded page carries the same
   number of links as its source page.
2. Destination  - each internal link lands on the same content it does in the
   source paper. Because an embedded page is just the scaled source page, the
   text at the transformed destination must match the text at the source
   destination. This catches misplaced destinations (e.g. coordinate flips).
3. Cross-refs   - each "Figure N" / "Table N" link lands on the page that holds
   the matching caption (figures carry too little text for check 2).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from .embed import read_placements, remap_destination


@dataclass
class AuditResult:
    """Outcome of :func:`audit`."""

    faithfulness: int = 0
    destination: int = 0
    crossref: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zà-ÿ]{3,}", text.lower()))


def _window(page: pymupdf.Page, x: float, y_top: float) -> str:
    """Text just below-right of a destination point (a caption or entry start)."""
    return page.get_textbox(pymupdf.Rect(x - 6, y_top - 4, x + 360, y_top + 30))


def _caption_pages(doc: pymupdf.Document, label: str) -> dict[str, int]:
    """Map e.g. ``"Figure"`` 3 -> page index of the 'Figure 3:' caption."""
    pages: dict[str, int] = {}
    for i in range(len(doc)):
        for m in re.finditer(rf"{label}\s+(\d+):", doc[i].get_text()):
            pages.setdefault(m.group(1), i)
    return pages


def _check_faithfulness(place, src_page, thesis, result: AuditResult) -> None:
    n_src = len(src_page.get_links())
    n_out = len(thesis[place.page].get_links())
    if n_out == n_src:
        result.faithfulness += 1
    else:
        result.failures.append(("faithfulness", f"page {place.page}: {n_out} links, source has {n_src}"))


# Fraction of the smaller token set that must overlap for two destination
# windows to count as "the same content".
MATCH_RATIO = 0.6
MIN_TOKENS = 3  # windows with fewer tokens (e.g. figures) skip the text check


def _check_destination(link, place, by_source, source, thesis, result: AuditResult) -> None:
    if link["kind"] not in (pymupdf.LINK_GOTO, pymupdf.LINK_NAMED):
        return
    target = by_source.get((place.filename, link.get("page", -1)))
    if target is None:
        return
    src_dest = source(place.filename)[link["page"]]
    src_y = src_dest.rect.height - link["to"].y  # raw bottom-left -> from top
    src_tokens = _tokens(_window(src_dest, link["to"].x, src_y))
    pt = remap_destination(link, target, source(place.filename))
    out_tokens = _tokens(_window(thesis[target.page], pt.x, pt.y))
    if min(len(src_tokens), len(out_tokens)) < MIN_TOKENS:
        return  # too little text (figures) — covered by _check_crossrefs
    overlap = len(src_tokens & out_tokens) / min(len(src_tokens), len(out_tokens))
    if overlap >= MATCH_RATIO:
        result.destination += 1
    else:
        result.failures.append(
            (
                "destination",
                f"src p{place.src_page}: "
                f"{' '.join(sorted(src_tokens))[:40]!r} vs {' '.join(sorted(out_tokens))[:40]!r}",
            )
        )


def _check_crossrefs(place, thesis, fig_pages, tab_pages, result: AuditResult) -> None:
    for link in thesis[place.page].get_links():
        if link["kind"] != pymupdf.LINK_GOTO:
            continue
        text = thesis[place.page].get_textbox(link["from"]).replace("\n", " ").strip()
        m = re.search(r"\b(figure|fig|table)\s*\.?\s*(\d+)", text, re.I)
        if not m:
            continue
        pages = fig_pages if m.group(1).lower().startswith("fig") else tab_pages
        expected = pages.get(m.group(2))
        if expected is None or link["page"] == expected:
            result.crossref += 1
        else:
            result.failures.append(
                ("cross-ref", f"page {place.page}: {m.group(0)!r} -> p{link['page']}, caption on p{expected}")
            )


def audit(document: Path, document_dir: Path) -> AuditResult:
    """Audit the embedded-paper links of a compiled document."""
    pdf_path = document.with_suffix(".pdf")
    placements = read_placements(document, document_dir)
    result = AuditResult()
    by_source = {(p.filename, p.src_page): p for p in placements}
    thesis = pymupdf.open(pdf_path)
    sources: dict[str, pymupdf.Document] = {}

    def source(filename: str) -> pymupdf.Document:
        return sources.setdefault(filename, pymupdf.open(filename))

    fig_pages = _caption_pages(thesis, "Figure")
    tab_pages = _caption_pages(thesis, "Table")
    try:
        for place in placements:
            src_page = source(place.filename)[place.src_page]
            _check_faithfulness(place, src_page, thesis, result)
            for link in src_page.get_links():
                _check_destination(link, place, by_source, source, thesis, result)
            _check_crossrefs(place, thesis, fig_pages, tab_pages, result)
    finally:
        thesis.close()
        for src in sources.values():
            src.close()
    return result
